"""Public-platform control plane for identity, authorization, quotas, moderation, and operations.

This module intentionally contains no Telegram or browser imports. It provides small,
parameterized SQLite primitives that can be called from the bot and dashboard layers.
"""
from __future__ import annotations

import json
import os
import sqlite3
import secrets
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional


ROLE_USER = "user"
ROLE_ADMIN = "admin"
STATUS_ACTIVE = "active"
STATUS_LIMITED = "limited"
STATUS_SUSPENDED = "suspended"
STATUS_BANNED = "banned"
ALLOWED_ROLES = {ROLE_USER, ROLE_ADMIN}
ALLOWED_STATUSES = {STATUS_ACTIVE, STATUS_LIMITED, STATUS_SUSPENDED, STATUS_BANNED}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def db_path() -> str:
    return os.getenv("DB_PATH", "telescout.db")


def admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_TELEGRAM_IDS", os.getenv("ALLOWED_TELEGRAM_USERS", ""))
    return {int(value.strip()) for value in raw.split(",") if value.strip().isdigit()}


def public_mode() -> bool:
    return os.getenv("PUBLIC_MODE", "false").strip().lower() in {"1", "true", "yes", "on"}


def _connect() -> sqlite3.Connection:
    connection = sqlite3.connect(db_path(), timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 30000")
    return connection


def init_platform_db() -> None:
    with _connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_user_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'limited', 'suspended', 'banned')),
                plan TEXT NOT NULL DEFAULT 'free',
                quota_limit INTEGER NOT NULL DEFAULT 20,
                quota_used INTEGER NOT NULL DEFAULT 0,
                quota_reset_at TEXT,
                risk_score REAL NOT NULL DEFAULT 0,
                strike_count INTEGER NOT NULL DEFAULT 0,
                banned_until TEXT,
                status_reason TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
            CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

            CREATE TABLE IF NOT EXISTS operations (
                operation_id TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                chat_id INTEGER,
                kind TEXT NOT NULL,
                status TEXT NOT NULL,
                target_url TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                attempt_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_operations_user_time ON operations(telegram_user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_operations_status ON operations(status);

            CREATE TABLE IF NOT EXISTS reports (
                report_id TEXT PRIMARY KEY,
                reporter_user_id INTEGER NOT NULL,
                target_user_id INTEGER,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                assigned_admin_id INTEGER,
                resolution TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_reports_status ON reports(status, created_at DESC);

            CREATE TABLE IF NOT EXISTS appeals (
                appeal_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                related_report_id TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                assigned_admin_id INTEGER,
                resolution TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_appeals_status ON appeals(status, created_at DESC);

            CREATE TABLE IF NOT EXISTS risk_events (
                risk_event_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                operation_id TEXT,
                score REAL NOT NULL,
                confidence REAL NOT NULL,
                decision TEXT NOT NULL,
                evidence_json TEXT NOT NULL DEFAULT '{}',
                model_version TEXT,
                human_review_required INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_risk_user_time ON risk_events(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS payment_orders (
                order_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                external_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                UNIQUE(provider, external_id)
            );
            CREATE INDEX IF NOT EXISTS idx_payment_user ON payment_orders(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS entitlements (
                user_id INTEGER PRIMARY KEY,
                plan TEXT NOT NULL DEFAULT 'free',
                expires_at TEXT,
                source_order_id TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS dashboard_login_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_dashboard_token_expiry ON dashboard_login_tokens(expires_at);

            CREATE TABLE IF NOT EXISTS dashboard_sessions (
                session_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                csrf_token TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_dashboard_session_expiry ON dashboard_sessions(expires_at);

            CREATE TABLE IF NOT EXISTS admin_actions (
                action_id TEXT PRIMARY KEY,
                admin_user_id INTEGER NOT NULL,
                target_user_id INTEGER,
                action TEXT NOT NULL,
                reason TEXT,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_admin_actions_time ON admin_actions(created_at DESC);

            CREATE TABLE IF NOT EXISTS referral_codes (
                code TEXT PRIMARY KEY,
                referrer_user_id INTEGER NOT NULL UNIQUE,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_referral_codes_referrer ON referral_codes(referrer_user_id);

            CREATE TABLE IF NOT EXISTS referrals (
                referral_id TEXT PRIMARY KEY,
                code TEXT NOT NULL,
                referrer_user_id INTEGER NOT NULL,
                referred_user_id INTEGER NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'qualified', 'rejected')),
                source TEXT NOT NULL DEFAULT 'telegram_start',
                qualified_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_referrals_referrer ON referrals(referrer_user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_referrals_status ON referrals(status, created_at DESC);

            CREATE TABLE IF NOT EXISTS referral_rewards (
                reward_id TEXT PRIMARY KEY,
                referral_id TEXT NOT NULL,
                recipient_user_id INTEGER NOT NULL,
                reward_type TEXT NOT NULL,
                reward_units INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'granted',
                created_at TEXT NOT NULL,
                UNIQUE(referral_id, recipient_user_id, reward_type)
            );
            CREATE INDEX IF NOT EXISTS idx_referral_rewards_recipient ON referral_rewards(recipient_user_id, created_at DESC);
            """
        )
        connection.commit()


def ensure_user(user_id: int, username: Optional[str] = None, display_name: Optional[str] = None) -> sqlite3.Row:
    now = utc_now()
    role = ROLE_ADMIN if user_id in admin_ids() else ROLE_USER
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO users (telegram_user_id, username, display_name, role, created_at, last_seen_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                display_name = COALESCE(excluded.display_name, users.display_name),
                role = CASE WHEN users.role = 'admin' OR excluded.role = 'admin' THEN 'admin' ELSE users.role END,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (user_id, username, display_name, role, now, now, now),
        )
        connection.commit()
        row = connection.execute("SELECT * FROM users WHERE telegram_user_id = ?", (user_id,)).fetchone()
        if row is None:
            raise RuntimeError("user creation failed")
        return row


def get_user(user_id: int) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT * FROM users WHERE telegram_user_id = ?", (user_id,)).fetchone()


def is_admin(user_id: int) -> bool:
    user = get_user(user_id)
    return bool(user and user["role"] == ROLE_ADMIN and user["status"] != STATUS_BANNED)


def is_allowed_user(user_id: int) -> bool:
    user = ensure_user(user_id)
    if user["role"] == ROLE_ADMIN:
        return user["status"] != STATUS_BANNED
    if not public_mode() and user_id not in admin_ids():
        return False
    if user["status"] == STATUS_BANNED:
        return False
    if user["status"] == STATUS_SUSPENDED and user["banned_until"]:
        if user["banned_until"] <= utc_now():
            set_user_status(user_id, STATUS_ACTIVE, "suspension expired")
            return True
        return False
    return user["status"] in {STATUS_ACTIVE, STATUS_LIMITED}


def set_user_status(user_id: int, status: str, reason: str = "", until: Optional[str] = None) -> bool:
    if status not in ALLOWED_STATUSES:
        raise ValueError("invalid user status")
    now = utc_now()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE users SET status = ?, status_reason = ?, banned_until = ?, updated_at = ? WHERE telegram_user_id = ?",
            (status, reason[:500], until, now, user_id),
        )
        connection.commit()
        return cursor.rowcount == 1


def set_user_role(user_id: int, role: str) -> bool:
    if role not in ALLOWED_ROLES:
        raise ValueError("invalid user role")
    with _connect() as connection:
        cursor = connection.execute("UPDATE users SET role = ?, updated_at = ? WHERE telegram_user_id = ?", (role, utc_now(), user_id))
        connection.commit()
        return cursor.rowcount == 1


def search_users(query: str, limit: int = 25) -> List[sqlite3.Row]:
    query = (query or "").strip()[:100]
    try:
        numeric_id = int(query)
    except ValueError:
        numeric_id = -1
    with _connect() as connection:
        return connection.execute(
            """
            SELECT telegram_user_id, username, display_name, role, status, plan, quota_used, quota_limit, risk_score, strike_count, last_seen_at
            FROM users
            WHERE telegram_user_id = ? OR username LIKE ? OR display_name LIKE ?
            ORDER BY last_seen_at DESC LIMIT ?
            """,
            (numeric_id, f"%{query}%", f"%{query}%", max(1, min(limit, 100))),
        ).fetchall()


def consume_quota(user_id: int, units: int = 1) -> tuple[bool, int, int]:
    if units < 1 or units > 100:
        raise ValueError("invalid quota units")
    user = ensure_user(user_id)
    if user["role"] == ROLE_ADMIN:
        return True, user["quota_used"], user["quota_limit"]
    now = datetime.now(timezone.utc)
    reset_at = user["quota_reset_at"]
    if not reset_at or reset_at <= now.isoformat():
        reset_at = (now + timedelta(days=30)).replace(microsecond=0).isoformat()
        with _connect() as connection:
            connection.execute("UPDATE users SET quota_used = 0, quota_reset_at = ?, updated_at = ? WHERE telegram_user_id = ?", (reset_at, utc_now(), user_id))
            connection.commit()
        user = ensure_user(user_id)
    if user["quota_used"] + units > user["quota_limit"]:
        return False, user["quota_used"], user["quota_limit"]
    with _connect() as connection:
        connection.execute("UPDATE users SET quota_used = quota_used + ?, updated_at = ? WHERE telegram_user_id = ?", (units, utc_now(), user_id))
        connection.commit()
    return True, user["quota_used"] + units, user["quota_limit"]


def create_operation(operation_id: str, user_id: int, chat_id: Optional[int], kind: str, target_url: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> None:
    now = utc_now()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO operations (operation_id, telegram_user_id, chat_id, kind, status, target_url, metadata_json, created_at, updated_at) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?, ?)",
            (operation_id, user_id, chat_id, kind, target_url, json.dumps(metadata or {}, separators=(",", ":")), now, now),
        )
        connection.commit()


def update_operation(operation_id: str, status: str, attempt_count: Optional[int] = None) -> bool:
    with _connect() as connection:
        if attempt_count is None:
            cursor = connection.execute("UPDATE operations SET status = ?, updated_at = ? WHERE operation_id = ?", (status, utc_now(), operation_id))
        else:
            cursor = connection.execute("UPDATE operations SET status = ?, attempt_count = ?, updated_at = ? WHERE operation_id = ?", (status, attempt_count, utc_now(), operation_id))
        connection.commit()
        return cursor.rowcount == 1


def list_session_metadata(user_id: Optional[int] = None, limit: int = 100) -> List[sqlite3.Row]:
    with _connect() as connection:
        if user_id is None:
            return connection.execute("SELECT user_id, name, created_at FROM sessions ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return connection.execute("SELECT user_id, name, created_at FROM sessions WHERE user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, max(1, min(limit, 500)))).fetchall()


def list_operations(user_id: Optional[int] = None, limit: int = 100) -> List[sqlite3.Row]:
    with _connect() as connection:
        if user_id is None:
            return connection.execute("SELECT operation_id, telegram_user_id, chat_id, kind, status, target_url, attempt_count, created_at, updated_at FROM operations ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return connection.execute("SELECT operation_id, telegram_user_id, chat_id, kind, status, target_url, attempt_count, created_at, updated_at FROM operations WHERE telegram_user_id = ? ORDER BY created_at DESC LIMIT ?", (user_id, max(1, min(limit, 500)))).fetchall()


def create_report(reporter_user_id: int, category: str, description: str, target_user_id: Optional[int] = None) -> str:
    report_id = "rpt_" + secrets.token_urlsafe(8)
    now = utc_now()
    with _connect() as connection:
        connection.execute("INSERT INTO reports (report_id, reporter_user_id, target_user_id, category, description, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (report_id, reporter_user_id, target_user_id, category[:80], description[:4000], now, now))
        connection.commit()
    return report_id


def create_appeal(user_id: int, message: str, related_report_id: Optional[str] = None) -> str:
    appeal_id = "apl_" + secrets.token_urlsafe(8)
    now = utc_now()
    with _connect() as connection:
        connection.execute("INSERT INTO appeals (appeal_id, user_id, related_report_id, message, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)", (appeal_id, user_id, related_report_id, message[:4000], now, now))
        connection.commit()
    return appeal_id


def list_reports(status: str = "open", limit: int = 100) -> List[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT report_id, reporter_user_id, target_user_id, category, description, status, assigned_admin_id, resolution, created_at, updated_at FROM reports WHERE status = ? ORDER BY created_at ASC LIMIT ?", (status, max(1, min(limit, 500)))).fetchall()


def list_appeals(status: str = "open", limit: int = 100) -> List[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT appeal_id, user_id, related_report_id, message, status, assigned_admin_id, resolution, created_at, updated_at FROM appeals WHERE status = ? ORDER BY created_at ASC LIMIT ?", (status, max(1, min(limit, 500)))).fetchall()


def resolve_report(report_id: str, admin_user_id: int, status: str, resolution: str) -> bool:
    if status not in {"open", "reviewing", "resolved", "dismissed"}:
        raise ValueError("invalid report status")
    with _connect() as connection:
        cursor = connection.execute("UPDATE reports SET status = ?, assigned_admin_id = ?, resolution = ?, updated_at = ? WHERE report_id = ?", (status, admin_user_id, resolution[:4000], utc_now(), report_id))
        connection.commit()
        return cursor.rowcount == 1


def resolve_appeal(appeal_id: str, admin_user_id: int, status: str, resolution: str) -> bool:
    if status not in {"open", "reviewing", "resolved", "denied"}:
        raise ValueError("invalid appeal status")
    with _connect() as connection:
        cursor = connection.execute("UPDATE appeals SET status = ?, assigned_admin_id = ?, resolution = ?, updated_at = ? WHERE appeal_id = ?", (status, admin_user_id, resolution[:4000], utc_now(), appeal_id))
        connection.commit()
        return cursor.rowcount == 1


def get_payment_order_by_external_id(provider: str, external_id: str) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT * FROM payment_orders WHERE provider = ? AND external_id = ?", (provider, external_id)).fetchone()


def calibrate_risk_decision(score: float, confidence: float) -> str:
    """Conservative policy: low-confidence signals do nothing; strong signals request review only."""
    score = max(0.0, min(float(score), 1.0))
    confidence = max(0.0, min(float(confidence), 1.0))
    if confidence < 0.70 or score < 0.82:
        return "no_action"
    return "human_review"


def record_risk_event(user_id: int, operation_id: Optional[str], score: float, confidence: float, decision: str, evidence: Dict[str, Any], model_version: str, human_review_required: bool = True) -> str:
    event_id = "risk_" + secrets.token_urlsafe(8)
    with _connect() as connection:
        connection.execute("INSERT INTO risk_events (risk_event_id, user_id, operation_id, score, confidence, decision, evidence_json, model_version, human_review_required, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (event_id, user_id, operation_id, max(0.0, min(score, 1.0)), max(0.0, min(confidence, 1.0)), decision[:40], json.dumps(evidence or {}, separators=(",", ":")), model_version[:80], int(human_review_required), utc_now()))
        connection.commit()
    return event_id


def _token_hash(value: str) -> str:
    import hashlib
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def create_dashboard_login_token(user_id: int, ttl_minutes: int = 10) -> str:
    raw = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=max(1, min(ttl_minutes, 30)))).replace(microsecond=0).isoformat()
    with _connect() as connection:
        connection.execute("INSERT INTO dashboard_login_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)", (_token_hash(raw), user_id, expires))
        connection.commit()
    return raw


def exchange_dashboard_login_token(raw_token: str, ttl_hours: int = 24) -> Optional[Dict[str, str]]:
    if not raw_token or len(raw_token) > 200:
        return None
    now = utc_now()
    with _connect() as connection:
        row = connection.execute("SELECT user_id, expires_at, used_at FROM dashboard_login_tokens WHERE token_hash = ?", (_token_hash(raw_token),)).fetchone()
        if not row or row["used_at"] or row["expires_at"] <= now:
            return None
        session_raw = secrets.token_urlsafe(32)
        csrf_raw = secrets.token_urlsafe(24)
        expires = (datetime.now(timezone.utc) + timedelta(hours=max(1, min(ttl_hours, 72)))).replace(microsecond=0).isoformat()
        connection.execute("UPDATE dashboard_login_tokens SET used_at = ? WHERE token_hash = ?", (now, _token_hash(raw_token)))
        connection.execute("INSERT INTO dashboard_sessions (session_hash, user_id, csrf_token, expires_at, created_at) VALUES (?, ?, ?, ?, ?)", (_token_hash(session_raw), row["user_id"], csrf_raw, expires, now))
        connection.commit()
        return {"session": session_raw, "csrf": csrf_raw, "user_id": str(row["user_id"]), "expires_at": expires}


def get_dashboard_session(raw_session: str) -> Optional[sqlite3.Row]:
    if not raw_session or len(raw_session) > 200:
        return None
    with _connect() as connection:
        row = connection.execute("SELECT user_id, csrf_token, expires_at FROM dashboard_sessions WHERE session_hash = ?", (_token_hash(raw_session),)).fetchone()
        if not row or row["expires_at"] <= utc_now():
            return None
        return row


def revoke_dashboard_session(raw_session: str) -> None:
    with _connect() as connection:
        connection.execute("DELETE FROM dashboard_sessions WHERE session_hash = ?", (_token_hash(raw_session),))
        connection.commit()


def get_or_create_referral_code(user_id: int) -> str:
    ensure_user(user_id)
    with _connect() as connection:
        row = connection.execute("SELECT code FROM referral_codes WHERE referrer_user_id = ? AND active = 1", (user_id,)).fetchone()
        if row:
            return row["code"]
        code = "ref_" + secrets.token_urlsafe(9)
        connection.execute("INSERT INTO referral_codes (code, referrer_user_id, created_at) VALUES (?, ?, ?)", (code, user_id, utc_now()))
        connection.commit()
        return code


def attribute_referral(referred_user_id: int, code: str, source: str = "telegram_start") -> str:
    """Attribute once, reject self-referrals and never overwrite an existing attribution."""
    code = str(code or "").strip()[:120]
    if not code:
        return "invalid"
    ensure_user(referred_user_id)
    with _connect() as connection:
        referrer = connection.execute("SELECT referrer_user_id, active FROM referral_codes WHERE code = ?", (code,)).fetchone()
        if not referrer or not referrer["active"]:
            return "invalid"
        if referrer["referrer_user_id"] == referred_user_id:
            return "self"
        existing = connection.execute("SELECT status FROM referrals WHERE referred_user_id = ?", (referred_user_id,)).fetchone()
        if existing:
            return "already_attributed"
        referrer_user = connection.execute("SELECT status FROM users WHERE telegram_user_id = ?", (referrer["referrer_user_id"],)).fetchone()
        if not referrer_user or referrer_user["status"] == STATUS_BANNED:
            return "referrer_unavailable"
        now = utc_now()
        referral_id = "rfl_" + secrets.token_urlsafe(8)
        connection.execute("INSERT INTO referrals (referral_id, code, referrer_user_id, referred_user_id, source, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (referral_id, code, referrer["referrer_user_id"], referred_user_id, source[:80], now, now))
        connection.commit()
        return "attributed"


def get_referral_stats(user_id: int) -> Dict[str, Any]:
    with _connect() as connection:
        code = connection.execute("SELECT code FROM referral_codes WHERE referrer_user_id = ? AND active = 1", (user_id,)).fetchone()
        counts = connection.execute("SELECT status, COUNT(*) AS count FROM referrals WHERE referrer_user_id = ? GROUP BY status", (user_id,)).fetchall()
        rewards = connection.execute("SELECT COALESCE(SUM(reward_units), 0) AS total FROM referral_rewards WHERE recipient_user_id = ? AND status = 'granted'", (user_id,)).fetchone()
    return {"code": code["code"] if code else None, "counts": {row["status"]: row["count"] for row in counts}, "reward_units": int(rewards["total"] if rewards else 0)}


def qualify_referral(referred_user_id: int, source_event: str = "qualified_payment") -> Optional[str]:
    """Qualify exactly once and grant auditable quota bonuses to both participants."""
    bonus = max(1, int(os.getenv("REFERRER_BONUS_UNITS", "20")))
    referred_bonus = max(1, bonus // 2)
    with _connect() as connection:
        referral = connection.execute("SELECT * FROM referrals WHERE referred_user_id = ? AND status = 'pending'", (referred_user_id,)).fetchone()
        if not referral:
            return None
        now = utc_now()
        cursor = connection.execute("UPDATE referrals SET status = 'qualified', qualified_at = ?, updated_at = ? WHERE referral_id = ? AND status = 'pending'", (now, now, referral["referral_id"]))
        if cursor.rowcount != 1:
            return None
        rewards = [
            ("referrer_quota_bonus", referral["referrer_user_id"], bonus),
            ("referred_quota_bonus", referral["referred_user_id"], referred_bonus),
        ]
        for reward_type, recipient, units in rewards:
            reward_id = "rrw_" + secrets.token_urlsafe(8)
            connection.execute("INSERT OR IGNORE INTO referral_rewards (reward_id, referral_id, recipient_user_id, reward_type, reward_units, created_at) VALUES (?, ?, ?, ?, ?, ?)", (reward_id, referral["referral_id"], recipient, reward_type, units, now))
            connection.execute("UPDATE users SET quota_limit = quota_limit + ?, updated_at = ? WHERE telegram_user_id = ?", (units, now, recipient))
        connection.commit()
        return referral["referral_id"]


def list_referrals(status: Optional[str] = None, limit: int = 100) -> List[sqlite3.Row]:
    with _connect() as connection:
        if status:
            return connection.execute("SELECT referral_id, code, referrer_user_id, referred_user_id, status, source, qualified_at, created_at, updated_at FROM referrals WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, max(1, min(limit, 500)))).fetchall()
        return connection.execute("SELECT referral_id, code, referrer_user_id, referred_user_id, status, source, qualified_at, created_at, updated_at FROM referrals ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()


def record_admin_action(admin_user_id: int, action: str, target_user_id: Optional[int], reason: str = "", metadata: Optional[Dict[str, Any]] = None) -> str:
    action_id = "adm_" + secrets.token_urlsafe(8)
    with _connect() as connection:
        connection.execute("INSERT INTO admin_actions (action_id, admin_user_id, target_user_id, action, reason, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (action_id, admin_user_id, target_user_id, action[:80], reason[:500], json.dumps(metadata or {}, separators=(",", ":")), utc_now()))
        connection.commit()
    return action_id


def record_payment_order(user_id: int, provider: str, external_id: str, amount: int, currency: str, payload: Optional[Dict[str, Any]] = None) -> tuple[str, bool]:
    order_id = "ord_" + secrets.token_urlsafe(8)
    now = utc_now()
    with _connect() as connection:
        try:
            connection.execute("INSERT INTO payment_orders (order_id, user_id, provider, external_id, amount, currency, payload_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", (order_id, user_id, provider, external_id, amount, currency, json.dumps(payload or {}, separators=(",", ":")), now, now))
            connection.commit()
            return order_id, True
        except sqlite3.IntegrityError:
            row = connection.execute("SELECT order_id FROM payment_orders WHERE provider = ? AND external_id = ?", (provider, external_id)).fetchone()
            return (row[0] if row else order_id), False


def attach_payment_charge(order_id: str, charge_id: str) -> bool:
    if not charge_id or len(charge_id) > 300:
        return False
    with _connect() as connection:
        row = connection.execute("SELECT payload_json FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return False
        payload = json.loads(row[0] or "{}")
        payload["telegram_payment_charge_id"] = charge_id
        connection.execute("UPDATE payment_orders SET payload_json = ?, updated_at = ? WHERE order_id = ?", (json.dumps(payload, separators=(",", ":")), utc_now(), order_id))
        connection.commit()
        return True


def mark_payment_success(order_id: str, plan: str, expires_at: Optional[str] = None) -> bool:
    now = utc_now()
    with _connect() as connection:
        row = connection.execute("SELECT user_id, status FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row or row["status"] == "paid":
            return False
        connection.execute("UPDATE payment_orders SET status = 'paid', updated_at = ? WHERE order_id = ?", (now, order_id))
        connection.execute("INSERT INTO entitlements (user_id, plan, expires_at, source_order_id, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET plan = excluded.plan, expires_at = excluded.expires_at, source_order_id = excluded.source_order_id, updated_at = excluded.updated_at", (row["user_id"], plan, expires_at, order_id, now))
        connection.execute("UPDATE users SET plan = ?, quota_limit = CASE WHEN ? = 'pro' THEN 1000 ELSE quota_limit END, updated_at = ? WHERE telegram_user_id = ?", (plan, plan, now, row["user_id"]))
        connection.commit()
        return True

"""Public-platform control plane for identity, authorization, quotas, moderation, and operations.

This module intentionally contains no Telegram or browser imports. It provides small,
parameterized SQLite primitives that can be called from the bot and dashboard layers.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sqlite3
import secrets
from cryptography.fernet import Fernet, InvalidToken
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Iterable, List, Optional


ROLE_USER = "user"
ROLE_DEVELOPER = "developer"
ROLE_ADMIN = "admin"
STATUS_ACTIVE = "active"
STATUS_LIMITED = "limited"
STATUS_SUSPENDED = "suspended"
STATUS_BANNED = "banned"
ALLOWED_ROLES = {ROLE_USER, ROLE_DEVELOPER, ROLE_ADMIN}
API_KEY_SCOPES = {"check", "watch", "schedule", "sessions"}
ENABLED_API_KEY_SCOPES = {"check"}
DEFAULT_DEVELOPER_QUOTA = 250
DEFAULT_API_KEY_RATE_LIMIT = 30
MAX_API_KEY_RATE_LIMIT = 120
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
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'developer', 'admin')),
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

            CREATE TABLE IF NOT EXISTS developer_access_requests (
                request_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'approved', 'denied')),
                reviewed_by INTEGER,
                decision TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_developer_requests_status ON developer_access_requests(status, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_developer_requests_user ON developer_access_requests(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS api_keys (
                key_id TEXT PRIMARY KEY,
                key_hash TEXT NOT NULL UNIQUE,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                scopes_json TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
                rate_limit_per_minute INTEGER NOT NULL DEFAULT 30,
                last_used_at TEXT,
                created_at TEXT NOT NULL,
                revoked_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_api_keys_user_status ON api_keys(user_id, status, created_at DESC);

            CREATE TABLE IF NOT EXISTS api_key_usage (
                key_id TEXT NOT NULL,
                bucket_start TEXT NOT NULL,
                request_count INTEGER NOT NULL DEFAULT 0,
                last_used_at TEXT NOT NULL,
                PRIMARY KEY (key_id, bucket_start)
            );
            CREATE INDEX IF NOT EXISTS idx_api_key_usage_time ON api_key_usage(key_id, bucket_start DESC);

            CREATE TABLE IF NOT EXISTS developer_audit_events (
                event_id TEXT PRIMARY KEY,
                actor_user_id INTEGER,
                owner_user_id INTEGER,
                key_id TEXT,
                action TEXT NOT NULL,
                outcome TEXT NOT NULL,
                metadata_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_developer_audit_owner_time ON developer_audit_events(owner_user_id, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_developer_audit_key_time ON developer_audit_events(key_id, created_at DESC);

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

            CREATE TABLE IF NOT EXISTS user_notifications (
                notification_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'delivered', 'failed', 'dead_letter')),
                attempt_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                next_attempt_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                delivered_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_notifications_pending ON user_notifications(status, next_attempt_at, created_at);
            CREATE INDEX IF NOT EXISTS idx_notifications_user ON user_notifications(user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS admin_bulk_jobs (
                job_id TEXT PRIMARY KEY,
                admin_user_id INTEGER NOT NULL,
                action TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                target_ids_json TEXT NOT NULL DEFAULT '[]',
                confirmation_hash TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'preview' CHECK (status IN ('preview', 'confirmed', 'running', 'completed', 'failed', 'cancelled')),
                processed_count INTEGER NOT NULL DEFAULT 0,
                succeeded_count INTEGER NOT NULL DEFAULT 0,
                failed_count INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                confirmed_at TEXT,
                completed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_bulk_jobs_admin_time ON admin_bulk_jobs(admin_user_id, created_at DESC);

            CREATE TABLE IF NOT EXISTS developer_events (
                event_id TEXT PRIMARY KEY,
                owner_user_id INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_developer_events_owner_time ON developer_events(owner_user_id, created_at, event_id);

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
        _migrate_users_role_constraint(connection)
        try:
            connection.execute("ALTER TABLE dashboard_login_tokens ADD COLUMN session_secret TEXT")
        except sqlite3.OperationalError:
            pass
        connection.commit()


def _migrate_users_role_constraint(connection: sqlite3.Connection) -> None:
    """Expand the legacy users CHECK constraint without discarding existing rows."""
    row = connection.execute("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'users'").fetchone()
    schema = (row[0] if row else "").lower()
    if "'developer'" in schema:
        return
    connection.execute("PRAGMA foreign_keys = OFF")
    try:
        connection.execute("BEGIN")
        connection.execute(
            """
            CREATE TABLE users_migrating (
                telegram_user_id INTEGER PRIMARY KEY,
                username TEXT,
                display_name TEXT,
                role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'developer', 'admin')),
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
            )
            """
        )
        connection.execute("INSERT INTO users_migrating SELECT telegram_user_id, username, display_name, role, status, plan, quota_limit, quota_used, quota_reset_at, risk_score, strike_count, banned_until, status_reason, created_at, last_seen_at, updated_at FROM users")
        connection.execute("DROP TABLE users")
        connection.execute("ALTER TABLE users_migrating RENAME TO users")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.execute("PRAGMA foreign_keys = ON")


def _dashboard_cipher() -> Fernet:
    seed = (os.getenv("SESSION_ENCRYPTION_KEY") or os.getenv("TELEGRAM_BOT_TOKEN") or "dashboard-development-seed").encode("utf-8")
    key = base64.urlsafe_b64encode(seed.ljust(32, b"0")[:32])
    return Fernet(key)


def _protect_dashboard_session(value: str) -> str:
    return _dashboard_cipher().encrypt(value.encode("utf-8")).decode("utf-8")


def _unprotect_dashboard_session(value: str) -> Optional[str]:
    try:
        return _dashboard_cipher().decrypt(value.encode("utf-8"), ttl=259200).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return None


def developer_quota_limit() -> int:
    return max(1, int(os.getenv("DEVELOPER_QUOTA_LIMIT", str(DEFAULT_DEVELOPER_QUOTA))))


def ensure_user(user_id: int, username: Optional[str] = None, display_name: Optional[str] = None) -> sqlite3.Row:
    now = utc_now()
    role = ROLE_ADMIN if user_id in admin_ids() else ROLE_USER
    quota_limit = developer_quota_limit() if role == ROLE_DEVELOPER else 20
    with _connect() as connection:
        connection.execute(
            """
            INSERT INTO users (telegram_user_id, username, display_name, role, quota_limit, created_at, last_seen_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(telegram_user_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                display_name = COALESCE(excluded.display_name, users.display_name),
                role = CASE WHEN users.role = 'admin' OR excluded.role = 'admin' THEN 'admin' ELSE users.role END,
                last_seen_at = excluded.last_seen_at,
                updated_at = excluded.updated_at
            """,
            (user_id, username, display_name, role, quota_limit, now, now, now),
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


def is_developer(user_id: int) -> bool:
    """Return whether the account may use developer capabilities.

    Administrators retain their stored admin role and inherit developer capabilities;
    ordinary users must still receive the explicit developer role through approval.
    """
    user = get_user(user_id)
    return bool(user and user["role"] in {ROLE_DEVELOPER, ROLE_ADMIN} and user["status"] == STATUS_ACTIVE)


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
    now = utc_now()
    with _connect() as connection:
        if role == ROLE_DEVELOPER:
            cursor = connection.execute("UPDATE users SET role = ?, quota_limit = CASE WHEN quota_limit < ? THEN ? ELSE quota_limit END, updated_at = ? WHERE telegram_user_id = ?", (role, developer_quota_limit(), developer_quota_limit(), now, user_id))
        else:
            cursor = connection.execute("UPDATE users SET role = ?, updated_at = ? WHERE telegram_user_id = ?", (role, now, user_id))
        connection.commit()
        return cursor.rowcount == 1


def create_developer_access_request(user_id: int, message: str) -> tuple[str, bool]:
    ensure_user(user_id)
    bounded_message = str(message or "").strip()[:2000]
    if not bounded_message:
        raise ValueError("developer request message is required")
    now = utc_now()
    with _connect() as connection:
        existing = connection.execute("SELECT request_id FROM developer_access_requests WHERE user_id = ? AND status = 'open' ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
        if existing:
            return existing["request_id"], False
        request_id = "devreq_" + secrets.token_urlsafe(8)
        connection.execute("INSERT INTO developer_access_requests (request_id, user_id, message, created_at, updated_at) VALUES (?, ?, ?, ?, ?)", (request_id, user_id, bounded_message, now, now))
        connection.commit()
    record_developer_audit(None, user_id, None, "developer_request", "created", {"request_id": request_id})
    return request_id, True


def list_developer_access_requests(status: str = "open", limit: int = 100) -> List[sqlite3.Row]:
    if status not in {"open", "approved", "denied", "all"}:
        raise ValueError("invalid developer request status")
    with _connect() as connection:
        if status == "all":
            return connection.execute("SELECT request_id, user_id, message, status, reviewed_by, decision, created_at, updated_at FROM developer_access_requests ORDER BY created_at DESC LIMIT ?", (max(1, min(limit, 500)),)).fetchall()
        return connection.execute("SELECT request_id, user_id, message, status, reviewed_by, decision, created_at, updated_at FROM developer_access_requests WHERE status = ? ORDER BY created_at DESC LIMIT ?", (status, max(1, min(limit, 500)))).fetchall()


def resolve_developer_access_request(request_id: str, admin_user_id: int, status: str, decision: str = "") -> bool:
    if status not in {"approved", "denied"}:
        raise ValueError("invalid developer request decision")
    with _connect() as connection:
        cursor = connection.execute("UPDATE developer_access_requests SET status = ?, reviewed_by = ?, decision = ?, updated_at = ? WHERE request_id = ? AND status = 'open'", (status, admin_user_id, str(decision or "")[:1000], utc_now(), str(request_id)[:100]))
        connection.commit()
        changed = cursor.rowcount == 1
    if changed:
        record_developer_audit(admin_user_id, None, None, "developer_request_review", status, {"request_id": request_id})
    return changed


def _api_key_hash_secret() -> bytes:
    configured = os.getenv("API_KEY_HASH_SECRET")
    if public_mode() and not configured:
        raise RuntimeError("API_KEY_HASH_SECRET is required when PUBLIC_MODE is enabled")
    raw = configured or os.getenv("SESSION_ENCRYPTION_KEY") or os.getenv("TELEGRAM_BOT_TOKEN") or "developer-local-secret"
    return raw.encode("utf-8")


def _api_key_hash(raw_key: str) -> str:
    return hmac.new(_api_key_hash_secret(), raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _api_key_scopes(row: sqlite3.Row) -> List[str]:
    try:
        scopes = json.loads(row["scopes_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        scopes = []
    return sorted({str(scope) for scope in scopes if str(scope) in API_KEY_SCOPES})


def record_developer_audit(actor_user_id: Optional[int], owner_user_id: Optional[int], key_id: Optional[str], action: str, outcome: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    event_id = "dev_audit_" + secrets.token_urlsafe(8)
    with _connect() as connection:
        connection.execute("INSERT INTO developer_audit_events (event_id, actor_user_id, owner_user_id, key_id, action, outcome, metadata_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (event_id, actor_user_id, owner_user_id, key_id, str(action)[:80], str(outcome)[:80], json.dumps(metadata or {}, separators=(",", ":")), utc_now()))
        connection.commit()
    return event_id


def create_api_key(user_id: int, name: str, scopes: Iterable[str], rate_limit_per_minute: int = DEFAULT_API_KEY_RATE_LIMIT) -> Dict[str, Any]:
    user = get_user(user_id)
    if not user or user["role"] not in {ROLE_DEVELOPER, ROLE_ADMIN} or user["status"] != STATUS_ACTIVE:
        raise PermissionError("active developer capability required")
    clean_name = str(name or "").strip()[:80]
    if not clean_name:
        raise ValueError("API key name is required")
    clean_scopes = sorted({str(scope).strip().lower() for scope in scopes if str(scope).strip()})
    if not clean_scopes or not set(clean_scopes).issubset(ENABLED_API_KEY_SCOPES):
        raise ValueError("unsupported API key scope")
    limit = max(1, min(int(rate_limit_per_minute), MAX_API_KEY_RATE_LIMIT))
    key_id = "key_" + secrets.token_urlsafe(8)
    raw_key = f"gai_live.{key_id}.{secrets.token_urlsafe(32)}"
    now = utc_now()
    with _connect() as connection:
        connection.execute("INSERT INTO api_keys (key_id, key_hash, user_id, name, scopes_json, rate_limit_per_minute, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (key_id, _api_key_hash(raw_key), user_id, clean_name, json.dumps(clean_scopes, separators=(",", ":")), limit, now))
        connection.commit()
    record_developer_audit(user_id, user_id, key_id, "api_key_created", "success", {"name": clean_name, "scopes": clean_scopes, "rate_limit_per_minute": limit})
    return {"key_id": key_id, "key": raw_key, "name": clean_name, "scopes": clean_scopes, "rate_limit_per_minute": limit, "created_at": now}


def list_api_keys(user_id: int) -> List[Dict[str, Any]]:
    with _connect() as connection:
        rows = connection.execute("SELECT key_id, user_id, name, scopes_json, status, rate_limit_per_minute, last_used_at, created_at, revoked_at FROM api_keys WHERE user_id = ? ORDER BY created_at DESC LIMIT 100", (user_id,)).fetchall()
    return [{"key_id": row["key_id"], "user_id": row["user_id"], "name": row["name"], "scopes": _api_key_scopes(row), "status": row["status"], "rate_limit_per_minute": row["rate_limit_per_minute"], "last_used_at": row["last_used_at"], "created_at": row["created_at"], "revoked_at": row["revoked_at"]} for row in rows]


def revoke_all_api_keys_for_user(user_id: int, actor_user_id: int) -> int:
    now = utc_now()
    with _connect() as connection:
        rows = connection.execute("SELECT key_id FROM api_keys WHERE user_id = ? AND status = 'active'", (user_id,)).fetchall()
        if rows:
            connection.execute("UPDATE api_keys SET status = 'revoked', revoked_at = ? WHERE user_id = ? AND status = 'active'", (now, user_id))
        connection.commit()
    for row in rows:
        record_developer_audit(actor_user_id, user_id, row["key_id"], "api_key_revoked", "developer_role_revoked", {})
    return len(rows)


def revoke_api_key(key_id: str, requester_user_id: int, is_requester_admin: bool = False) -> bool:
    with _connect() as connection:
        row = connection.execute("SELECT user_id, status FROM api_keys WHERE key_id = ?", (str(key_id)[:100],)).fetchone()
        if not row or (row["user_id"] != requester_user_id and not is_requester_admin):
            record_developer_audit(requester_user_id, row["user_id"] if row else None, key_id, "api_key_revoke", "denied", {})
            return False
        if row["status"] == "revoked":
            return True
        now = utc_now()
        connection.execute("UPDATE api_keys SET status = 'revoked', revoked_at = ? WHERE key_id = ?", (now, key_id))
        connection.commit()
    record_developer_audit(requester_user_id, row["user_id"], key_id, "api_key_revoked", "success", {})
    return True


def authenticate_api_key(raw_key: str, required_scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
    raw_key = str(raw_key or "")
    parts = raw_key.split(".")
    if len(parts) != 3 or parts[0] != "gai_live" or len(raw_key) > 300:
        return None
    key_id = parts[1]
    with _connect() as connection:
        row = connection.execute("SELECT * FROM api_keys WHERE key_id = ?", (key_id,)).fetchone()
    try:
        expected_hash = _api_key_hash(raw_key)
    except RuntimeError:
        return None
    if not row or row["status"] != "active" or not hmac.compare_digest(row["key_hash"], expected_hash):
        if row:
            record_developer_audit(None, row["user_id"], row["key_id"], "api_key_authentication", "denied", {"reason": "invalid_or_revoked"})
        return None
    user = get_user(row["user_id"])
    scopes = _api_key_scopes(row)
    if not user or user["role"] not in {ROLE_DEVELOPER, ROLE_ADMIN} or user["status"] != STATUS_ACTIVE:
        record_developer_audit(None, row["user_id"], row["key_id"], "api_key_authentication", "denied", {"reason": "developer_inactive"})
        return None
    if required_scope and required_scope not in scopes:
        record_developer_audit(None, row["user_id"], row["key_id"], "api_scope_check", "denied", {"scope": required_scope})
        return None
    return {"key_id": row["key_id"], "user_id": row["user_id"], "name": row["name"], "scopes": scopes, "rate_limit_per_minute": row["rate_limit_per_minute"]}


def check_api_key_rate_limit(key_id: str, user_id: int, limit: int) -> tuple[bool, int, int]:
    now = utc_now()
    bucket = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M")
    bounded_limit = max(1, min(int(limit), MAX_API_KEY_RATE_LIMIT))
    with _connect() as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT request_count FROM api_key_usage WHERE key_id = ? AND bucket_start = ?", (key_id, bucket)).fetchone()
        current = int(row["request_count"] if row else 0)
        if current >= bounded_limit:
            connection.commit()
            record_developer_audit(None, user_id, key_id, "api_key_rate_limit", "denied", {"limit": bounded_limit, "used": current})
            return False, current, bounded_limit
        if row:
            connection.execute("UPDATE api_key_usage SET request_count = request_count + 1, last_used_at = ? WHERE key_id = ? AND bucket_start = ?", (now, key_id, bucket))
        else:
            connection.execute("INSERT INTO api_key_usage (key_id, bucket_start, request_count, last_used_at) VALUES (?, ?, 1, ?)", (key_id, bucket, now))
        connection.execute("UPDATE api_keys SET last_used_at = ? WHERE key_id = ? AND status = 'active'", (now, key_id))
        connection.execute("DELETE FROM api_key_usage WHERE key_id = ? AND bucket_start < ?", (key_id, (datetime.now(timezone.utc) - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")))
        connection.commit()
    record_developer_audit(None, user_id, key_id, "api_key_use", "allowed", {"limit": bounded_limit, "used": current + 1})
    return True, current + 1, bounded_limit


def get_developer_stats(user_id: int) -> Dict[str, Any]:
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M")
    with _connect() as connection:
        active = connection.execute("SELECT COUNT(*) AS count FROM api_keys WHERE user_id = ? AND status = 'active'", (user_id,)).fetchone()["count"]
        total = connection.execute("SELECT COUNT(*) AS count FROM developer_audit_events WHERE owner_user_id = ? AND action = 'api_key_use' AND created_at >= ?", (user_id, since)).fetchone()["count"]
        denied = connection.execute("SELECT COUNT(*) AS count FROM developer_audit_events WHERE owner_user_id = ? AND outcome = 'denied' AND created_at >= ?", (user_id, since)).fetchone()["count"]
    return {"active_keys": int(active), "requests_last_24h": int(total), "denied_events_last_24h": int(denied)}


def list_users_by_status(status: Optional[str] = None, limit: int = 200) -> List[sqlite3.Row]:
    if status is not None and status not in ALLOWED_STATUSES:
        raise ValueError("invalid user status")
    with _connect() as connection:
        if status:
            return connection.execute("SELECT telegram_user_id, username, display_name, role, status, plan, quota_used, quota_limit, risk_score, strike_count, last_seen_at FROM users WHERE status = ? ORDER BY last_seen_at DESC LIMIT ?", (status, max(1, min(int(limit), 500)))).fetchall()
        return connection.execute("SELECT telegram_user_id, username, display_name, role, status, plan, quota_used, quota_limit, risk_score, strike_count, last_seen_at FROM users WHERE status != 'banned' ORDER BY last_seen_at DESC LIMIT ?", (max(1, min(int(limit), 500)),)).fetchall()


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


def get_report(report_id: str) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT report_id, reporter_user_id, target_user_id, category, description, status, resolution FROM reports WHERE report_id = ?", (str(report_id)[:100],)).fetchone()


def get_appeal(appeal_id: str) -> Optional[sqlite3.Row]:
    with _connect() as connection:
        return connection.execute("SELECT appeal_id, user_id, related_report_id, message, status, resolution FROM appeals WHERE appeal_id = ?", (str(appeal_id)[:100],)).fetchone()


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


def enqueue_user_notification(user_id: int, kind: str, title: str, body: str, idempotency_key: str) -> tuple[str, bool]:
    notification_id = "ntf_" + secrets.token_urlsafe(8)
    now = utc_now()
    clean_kind = str(kind or "system")[:80]
    clean_title = str(title or "GreyAI update")[:200]
    clean_body = str(body or "")[:4000]
    clean_key = str(idempotency_key or "")[:200]
    if not clean_key or not clean_body:
        raise ValueError("notification body and idempotency key are required")
    with _connect() as connection:
        try:
            connection.execute(
                "INSERT INTO user_notifications (notification_id, user_id, kind, title, body, idempotency_key, next_attempt_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (notification_id, user_id, clean_kind, clean_title, clean_body, clean_key, now, now, now),
            )
            connection.commit()
            return notification_id, True
        except sqlite3.IntegrityError:
            row = connection.execute("SELECT notification_id FROM user_notifications WHERE idempotency_key = ?", (clean_key,)).fetchone()
            return (row["notification_id"] if row else notification_id), False


NOTIFICATION_LEASE_SECONDS = 900
MAX_NOTIFICATION_ATTEMPTS = 5


def list_pending_notifications(limit: int = 50) -> List[sqlite3.Row]:
    now = utc_now()
    lease_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=NOTIFICATION_LEASE_SECONDS)).replace(microsecond=0).isoformat()
    with _connect() as connection:
        return connection.execute(
            "SELECT * FROM user_notifications WHERE (((status = 'pending') OR (status = 'failed' AND attempt_count < ?)) AND (next_attempt_at IS NULL OR next_attempt_at <= ?) OR (status = 'sending' AND updated_at <= ?)) ORDER BY created_at LIMIT ?",
            (MAX_NOTIFICATION_ATTEMPTS, now, lease_cutoff, max(1, min(int(limit), 200))),
        ).fetchall()


def mark_notification_sending(notification_id: str) -> bool:
    now = utc_now()
    lease_cutoff = (datetime.now(timezone.utc) - timedelta(seconds=NOTIFICATION_LEASE_SECONDS)).replace(microsecond=0).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE user_notifications SET status = 'sending', attempt_count = attempt_count + 1, updated_at = ? WHERE notification_id = ? AND (status IN ('pending', 'failed') OR (status = 'sending' AND updated_at <= ?))",
            (now, str(notification_id)[:100], lease_cutoff),
        )
        connection.commit()
        return cursor.rowcount == 1


def mark_notification_delivered(notification_id: str) -> bool:
    now = utc_now()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE user_notifications SET status = 'delivered', delivered_at = ?, updated_at = ?, last_error = NULL WHERE notification_id = ? AND status IN ('sending', 'pending', 'failed')",
            (now, now, str(notification_id)[:100]),
        )
        connection.commit()
        return cursor.rowcount == 1


def mark_notification_failed(notification_id: str, error: str, retry_after_seconds: int = 300) -> bool:
    now = datetime.now(timezone.utc)
    next_attempt = (now + timedelta(seconds=max(30, min(int(retry_after_seconds), 86400)))).replace(microsecond=0).isoformat()
    with _connect() as connection:
        cursor = connection.execute(
            "UPDATE user_notifications SET status = CASE WHEN attempt_count >= ? THEN 'dead_letter' ELSE 'failed' END, last_error = ?, next_attempt_at = CASE WHEN attempt_count >= ? THEN NULL ELSE ? END, updated_at = ? WHERE notification_id = ? AND status IN ('sending', 'pending', 'failed')",
            (MAX_NOTIFICATION_ATTEMPTS, str(error or "delivery failed")[:500], MAX_NOTIFICATION_ATTEMPTS, next_attempt, utc_now(), str(notification_id)[:100]),
        )
        connection.commit()
        return cursor.rowcount == 1


def create_bulk_job(admin_user_id: int, action: str, payload: Dict[str, Any], target_ids: Iterable[Any], ttl_minutes: int = 10) -> Dict[str, Any]:
    allowed_actions = {"announce", "mass_dm", "mass_ban", "mass_unban", "mass_appeal"}
    clean_action = str(action or "").strip()[:40]
    if clean_action not in allowed_actions:
        raise ValueError("unsupported bulk action")
    clean_targets = sorted({str(value).strip()[:100] for value in target_ids if str(value).strip()})
    if len(clean_targets) > 500:
        raise ValueError("bulk target limit exceeded")
    job_id = "bulk_" + secrets.token_urlsafe(8)
    token = secrets.token_urlsafe(10)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=max(1, min(int(ttl_minutes), 15)))).replace(microsecond=0).isoformat()
    with _connect() as connection:
        connection.execute(
            "INSERT INTO admin_bulk_jobs (job_id, admin_user_id, action, payload_json, target_ids_json, confirmation_hash, expires_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (job_id, admin_user_id, clean_action, json.dumps(payload or {}, separators=(",", ":")), json.dumps(clean_targets), _token_hash(token), expires, utc_now()),
        )
        connection.commit()
    return {"job_id": job_id, "confirmation_token": token, "action": clean_action, "target_count": len(clean_targets), "expires_at": expires, "status": "preview"}


def confirm_bulk_job(job_id: str, confirmation_token: str, admin_user_id: int) -> Optional[Dict[str, Any]]:
    now = utc_now()
    with _connect() as connection:
        row = connection.execute("SELECT * FROM admin_bulk_jobs WHERE job_id = ? AND admin_user_id = ? AND status = 'preview'", (str(job_id)[:100], admin_user_id)).fetchone()
        if not row or row["expires_at"] <= now or not hmac.compare_digest(row["confirmation_hash"], _token_hash(str(confirmation_token or ""))):
            return None
        connection.execute("UPDATE admin_bulk_jobs SET status = 'confirmed', confirmed_at = ? WHERE job_id = ? AND status = 'preview'", (now, row["job_id"]))
        connection.commit()
        confirmed = dict(row)
        confirmed["status"] = "confirmed"
        confirmed["confirmed_at"] = now
        return confirmed


def get_admin_analytics(limit: int = 25) -> Dict[str, Any]:
    bounded = max(1, min(int(limit), 100))
    with _connect() as connection:
        banned = connection.execute("SELECT telegram_user_id, username, display_name, status_reason, banned_until, updated_at FROM users WHERE status = 'banned' ORDER BY updated_at DESC LIMIT ?", (bounded,)).fetchall()
        suspicious = connection.execute("SELECT u.telegram_user_id, u.username, u.display_name, MAX(r.score) AS risk_score, MAX(r.confidence) AS confidence, COUNT(r.risk_event_id) AS event_count FROM risk_events r JOIN users u ON u.telegram_user_id = r.user_id WHERE r.human_review_required = 1 AND r.decision = 'human_review' GROUP BY u.telegram_user_id ORDER BY risk_score DESC, confidence DESC LIMIT ?", (bounded,)).fetchall()
        top_users = connection.execute("SELECT u.telegram_user_id, u.username, u.display_name, COUNT(o.operation_id) AS operation_count FROM operations o JOIN users u ON u.telegram_user_id = o.telegram_user_id GROUP BY u.telegram_user_id ORDER BY operation_count DESC, u.telegram_user_id LIMIT ?", (bounded,)).fetchall()
        top_referrers = connection.execute("SELECT u.telegram_user_id, u.username, u.display_name, COUNT(r.referral_id) AS referral_count, SUM(CASE WHEN r.status = 'qualified' THEN 1 ELSE 0 END) AS qualified_count FROM referrals r JOIN users u ON u.telegram_user_id = r.referrer_user_id GROUP BY u.telegram_user_id ORDER BY referral_count DESC, qualified_count DESC LIMIT ?", (bounded,)).fetchall()
        most_risky = connection.execute("SELECT u.telegram_user_id, u.username, u.display_name, u.risk_score, u.strike_count, u.status FROM users u ORDER BY u.risk_score DESC, u.strike_count DESC LIMIT ?", (bounded,)).fetchall()
    def rows(result):
        return [dict(row) for row in result]
    return {"banned_users": rows(banned), "suspicious_users": rows(suspicious), "top_users": rows(top_users), "top_referrers": rows(top_referrers), "most_risky_users": rows(most_risky)}


def record_developer_event(owner_user_id: int, event_type: str, payload: Dict[str, Any]) -> str:
    event_id = "evt_" + secrets.token_urlsafe(8)
    safe_payload = json.dumps(payload or {}, separators=(",", ":"))[:4000]
    with _connect() as connection:
        connection.execute("INSERT INTO developer_events (event_id, owner_user_id, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)", (event_id, owner_user_id, str(event_type or "event")[:80], safe_payload, utc_now()))
        connection.commit()
    return event_id


def list_developer_events(owner_user_id: int, after_event_id: Optional[str] = None, limit: int = 50) -> List[sqlite3.Row]:
    with _connect() as connection:
        if after_event_id:
            return connection.execute("SELECT event_id, event_type, payload_json, created_at FROM developer_events WHERE owner_user_id = ? AND created_at > COALESCE((SELECT created_at FROM developer_events WHERE event_id = ? AND owner_user_id = ?), '') ORDER BY created_at, event_id LIMIT ?", (owner_user_id, str(after_event_id)[:100], owner_user_id, max(1, min(int(limit), 200)))).fetchall()
        return connection.execute("SELECT event_id, event_type, payload_json, created_at FROM developer_events WHERE owner_user_id = ? ORDER BY created_at, event_id LIMIT ?", (owner_user_id, max(1, min(int(limit), 200)))).fetchall()


def update_bulk_job_counts(job_id: str, processed: int, succeeded: int, failed: int, status: str = "completed") -> bool:
    if status not in {"running", "completed", "failed", "cancelled"}:
        raise ValueError("invalid bulk job status")
    with _connect() as connection:
        cursor = connection.execute("UPDATE admin_bulk_jobs SET status = ?, processed_count = ?, succeeded_count = ?, failed_count = ?, completed_at = CASE WHEN ? IN ('completed', 'failed', 'cancelled') THEN ? ELSE completed_at END WHERE job_id = ?", (status, max(0, int(processed)), max(0, int(succeeded)), max(0, int(failed)), status, utc_now(), str(job_id)[:100]))
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


def create_dashboard_login_token(user_id: int, ttl_minutes: int = 30) -> str:
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
        row = connection.execute("SELECT user_id, expires_at, used_at, session_secret FROM dashboard_login_tokens WHERE token_hash = ?", (_token_hash(raw_token),)).fetchone()
        if not row or row["expires_at"] <= now:
            return None
        if row["used_at"] and row["session_secret"]:
            session_raw = _unprotect_dashboard_session(row["session_secret"])
            if session_raw:
                existing = connection.execute("SELECT user_id, csrf_token, expires_at FROM dashboard_sessions WHERE session_hash = ? AND expires_at > ?", (_token_hash(session_raw), now)).fetchone()
                if existing:
                    return {"session": session_raw, "csrf": existing["csrf_token"], "user_id": str(existing["user_id"]), "expires_at": existing["expires_at"]}
            return None
        session_raw = secrets.token_urlsafe(32)
        csrf_raw = secrets.token_urlsafe(24)
        expires = (datetime.now(timezone.utc) + timedelta(hours=max(1, min(ttl_hours, 72)))).replace(microsecond=0).isoformat()
        connection.execute("UPDATE dashboard_login_tokens SET used_at = ?, session_secret = ? WHERE token_hash = ?", (now, _protect_dashboard_session(session_raw), _token_hash(raw_token)))
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
    if plan not in {"pro", "max"}:
        raise ValueError("invalid entitlement plan")
    quota_limit = int(os.getenv("PRO_PLAN_QUOTA", "1000")) if plan == "pro" else int(os.getenv("MAX_PLAN_QUOTA", "5000"))
    now = utc_now()
    with _connect() as connection:
        row = connection.execute("SELECT user_id, status FROM payment_orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row or row["status"] == "paid":
            return False
        connection.execute("UPDATE payment_orders SET status = 'paid', updated_at = ? WHERE order_id = ?", (now, order_id))
        connection.execute("INSERT INTO entitlements (user_id, plan, expires_at, source_order_id, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET plan = excluded.plan, expires_at = excluded.expires_at, source_order_id = excluded.source_order_id, updated_at = excluded.updated_at", (row["user_id"], plan, expires_at, order_id, now))
        connection.execute("UPDATE users SET plan = ?, quota_limit = ?, updated_at = ? WHERE telegram_user_id = ?", (plan, quota_limit, now, row["user_id"]))
        connection.commit()
        return True

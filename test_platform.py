import os
import sqlite3

import pytest

import control_plane as cp


@pytest.fixture
def platform_db(tmp_path, monkeypatch):
    path = tmp_path / "platform.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "platform-test-secret")
    cp.init_platform_db()
    return path


def test_roles_public_access_and_ban_lifecycle(platform_db):
    admin = cp.ensure_user(9001, "admin", "Admin")
    user = cp.ensure_user(42, "alice", "Alice")

    assert admin["role"] == "admin"
    assert user["role"] == "user"
    assert cp.is_admin(9001) is True
    assert cp.is_allowed_user(42) is True

    assert cp.set_user_status(42, cp.STATUS_BANNED, "abuse") is True
    assert cp.is_allowed_user(42) is False
    assert cp.set_user_status(42, cp.STATUS_ACTIVE, "appeal accepted") is True
    assert cp.is_allowed_user(42) is True


def test_private_mode_is_admin_only(monkeypatch, platform_db):
    monkeypatch.setenv("PUBLIC_MODE", "false")
    assert cp.is_allowed_user(42) is False
    assert cp.is_allowed_user(9001) is True


def test_quota_is_enforced_server_side(platform_db):
    cp.ensure_user(42)
    with sqlite3.connect(platform_db) as connection:
        connection.execute("UPDATE users SET quota_limit = 2 WHERE telegram_user_id = 42")
        connection.commit()

    assert cp.consume_quota(42)[0] is True
    assert cp.consume_quota(42)[0] is True
    allowed, used, limit = cp.consume_quota(42)
    assert (allowed, used, limit) == (False, 2, 2)


def test_reports_appeals_and_operations_are_durable(platform_db):
    cp.ensure_user(42)
    report_id = cp.create_report(42, "support", "The browser task failed repeatedly")
    appeal_id = cp.create_appeal(42, "Please review my account limitation")
    cp.create_operation("op_1", 42, 42, "check", "https://example.com")
    cp.update_operation("op_1", "succeeded", 1)

    assert cp.list_reports()[0]["report_id"] == report_id
    assert cp.list_appeals()[0]["appeal_id"] == appeal_id
    assert cp.list_operations(42)[0]["status"] == "succeeded"


def test_risk_calibration_is_conservative():
    assert cp.calibrate_risk_decision(0.99, 0.20) == "no_action"
    assert cp.calibrate_risk_decision(0.60, 0.99) == "no_action"
    assert cp.calibrate_risk_decision(0.90, 0.90) == "human_review"
    assert cp.calibrate_risk_decision(0.99, 0.99) not in {"ban", "suspend", "limit"}


def test_dashboard_login_tokens_replay_the_same_active_session(platform_db):
    cp.ensure_user(42)
    token = cp.create_dashboard_login_token(42)
    first = cp.exchange_dashboard_login_token(token)
    assert first is not None
    second = cp.exchange_dashboard_login_token(token)
    assert second is not None
    assert second["session"] == first["session"]
    assert second["csrf"] == first["csrf"]
    cp.revoke_dashboard_session(first["session"])
    assert cp.exchange_dashboard_login_token(token) is None


def test_dashboard_login_tokens_are_single_use_after_session_revocation(platform_db):
    cp.ensure_user(42)
    token = cp.create_dashboard_login_token(42)
    session = cp.exchange_dashboard_login_token(token)
    assert session is not None
    cp.revoke_dashboard_session(session["session"])
    assert cp.get_dashboard_session(session["session"]) is None
    assert cp.exchange_dashboard_login_token(token) is None


def test_referrals_attribute_once_and_qualify_with_audited_rewards(platform_db, monkeypatch):
    monkeypatch.setenv("REFERRER_BONUS_UNITS", "20")
    cp.ensure_user(100, "referrer", "Referrer")
    cp.ensure_user(200, "referred", "Referred")
    code = cp.get_or_create_referral_code(100)
    assert code == cp.get_or_create_referral_code(100)
    assert cp.attribute_referral(100, code) == "self"
    assert cp.attribute_referral(200, code) == "attributed"
    assert cp.attribute_referral(200, code) == "already_attributed"
    referral_id = cp.qualify_referral(200, "test_payment")
    assert referral_id is not None
    assert cp.qualify_referral(200, "test_payment") is None
    stats = cp.get_referral_stats(100)
    assert stats["counts"]["qualified"] == 1
    assert stats["reward_units"] == 20
    assert cp.get_referral_stats(200)["reward_units"] == 10
    assert cp.list_referrals("qualified")[0]["referral_id"] == referral_id


def test_payment_order_is_idempotent_and_grants_entitlement(platform_db, monkeypatch):
    monkeypatch.setenv("PRO_PLAN_QUOTA", "1000")
    monkeypatch.setenv("MAX_PLAN_QUOTA", "5000")
    cp.ensure_user(42)
    first_id, first_created = cp.record_payment_order(42, "telegram_stars", "charge_1", 100, "XTR", {"plan": "pro"})
    second_id, second_created = cp.record_payment_order(42, "telegram_stars", "charge_1", 100, "XTR", {"plan": "pro"})

    assert first_created is True
    assert second_created is False
    assert second_id == first_id
    assert cp.mark_payment_success(first_id, "pro") is True
    assert cp.mark_payment_success(first_id, "pro") is False
    assert cp.get_user(42)["plan"] == "pro"
    max_id, max_created = cp.record_payment_order(42, "telegram_stars", "charge_max", 1000, "XTR", {"plan": "max"})
    assert max_created is True
    assert cp.mark_payment_success(max_id, "max") is True
    assert cp.get_user(42)["plan"] == "max"
    assert cp.get_user(42)["quota_limit"] == 5000


def test_legacy_users_table_migrates_to_include_developer_role(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    monkeypatch.setenv("DB_PATH", str(path))
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE users (telegram_user_id INTEGER PRIMARY KEY, username TEXT, display_name TEXT, role TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')), status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'limited', 'suspended', 'banned')), plan TEXT NOT NULL DEFAULT 'free', quota_limit INTEGER NOT NULL DEFAULT 20, quota_used INTEGER NOT NULL DEFAULT 0, quota_reset_at TEXT, risk_score REAL NOT NULL DEFAULT 0, strike_count INTEGER NOT NULL DEFAULT 0, banned_until TEXT, status_reason TEXT, created_at TEXT NOT NULL, last_seen_at TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute("INSERT INTO users VALUES (42, 'alice', 'Alice', 'user', 'active', 'free', 20, 0, NULL, 0, 0, NULL, NULL, 'now', 'now', 'now')")
        connection.commit()
    cp.init_platform_db()
    assert cp.set_user_role(42, cp.ROLE_DEVELOPER) is True
    assert cp.is_developer(42) is True
    assert cp.get_user(42)["quota_limit"] == cp.developer_quota_limit()


def test_developer_request_is_idempotent_and_admin_reviewable(platform_db):
    cp.ensure_user(42)
    first_id, first_created = cp.create_developer_access_request(42, "I need a scoped check API for my Telegram bot")
    second_id, second_created = cp.create_developer_access_request(42, "duplicate request")
    assert (first_id, first_created) == (second_id, True)
    assert second_created is False
    assert cp.resolve_developer_access_request(first_id, 9001, "approved", "approved after review") is True
    assert cp.resolve_developer_access_request(first_id, 9001, "approved", "duplicate") is False
    assert cp.list_developer_access_requests("approved")[0]["request_id"] == first_id


def test_api_key_is_shown_once_scoped_owned_and_revocable(platform_db, monkeypatch):
    monkeypatch.setenv("API_KEY_HASH_SECRET", "test-api-key-secret")
    cp.ensure_user(42)
    cp.set_user_role(42, cp.ROLE_DEVELOPER)
    created = cp.create_api_key(42, "telegram bot", ["check"], rate_limit_per_minute=2)
    assert created["key"].startswith("gai_live.")
    assert created["key"] not in str(cp.list_api_keys(42))
    assert cp.authenticate_api_key(created["key"])["key_id"] == created["key_id"]
    assert cp.authenticate_api_key(created["key"], "watch") is None
    assert cp.revoke_api_key(created["key_id"], 9001) is False
    assert cp.revoke_api_key(created["key_id"], 42) is True
    assert cp.authenticate_api_key(created["key"]) is None


def test_api_key_rate_limit_is_atomic_and_bounded(platform_db, monkeypatch):
    monkeypatch.setenv("API_KEY_HASH_SECRET", "test-api-key-secret")
    cp.ensure_user(42)
    cp.set_user_role(42, cp.ROLE_DEVELOPER)
    created = cp.create_api_key(42, "limited bot", ["check"], rate_limit_per_minute=2)
    principal = cp.authenticate_api_key(created["key"])
    assert principal is not None
    assert cp.check_api_key_rate_limit(principal["key_id"], 42, principal["rate_limit_per_minute"])[0] is True
    assert cp.check_api_key_rate_limit(principal["key_id"], 42, principal["rate_limit_per_minute"])[0] is True
    allowed, used, limit = cp.check_api_key_rate_limit(principal["key_id"], 42, principal["rate_limit_per_minute"])
    assert (allowed, used, limit) == (False, 2, 2)
    assert cp.get_developer_stats(42)["denied_events_last_24h"] >= 1


def test_revoking_developer_role_revokes_all_active_keys(platform_db):
    cp.ensure_user(42)
    cp.set_user_role(42, cp.ROLE_DEVELOPER)
    first = cp.create_api_key(42, "one", ["check"])
    second = cp.create_api_key(42, "two", ["check"])
    assert cp.revoke_all_api_keys_for_user(42, 9001) == 2
    assert all(item["status"] == "revoked" for item in cp.list_api_keys(42))
    assert cp.authenticate_api_key(first["key"]) is None
    assert cp.authenticate_api_key(second["key"]) is None

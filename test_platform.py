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


def test_dashboard_login_tokens_are_single_use_and_revocable(platform_db):
    cp.ensure_user(42)
    token = cp.create_dashboard_login_token(42)
    session = cp.exchange_dashboard_login_token(token)
    assert session is not None
    assert cp.exchange_dashboard_login_token(token) is None
    assert cp.get_dashboard_session(session["session"]) is not None
    cp.revoke_dashboard_session(session["session"])
    assert cp.get_dashboard_session(session["session"]) is None


def test_payment_order_is_idempotent_and_grants_entitlement(platform_db):
    cp.ensure_user(42)
    first_id, first_created = cp.record_payment_order(42, "telegram_stars", "charge_1", 100, "XTR", {"plan": "pro"})
    second_id, second_created = cp.record_payment_order(42, "telegram_stars", "charge_1", 100, "XTR", {"plan": "pro"})

    assert first_created is True
    assert second_created is False
    assert second_id == first_id
    assert cp.mark_payment_success(first_id, "pro") is True
    assert cp.mark_payment_success(first_id, "pro") is False
    assert cp.get_user(42)["plan"] == "pro"

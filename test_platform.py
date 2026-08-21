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


def test_notification_outbox_is_idempotent_and_retryable(platform_db):
    cp.ensure_user(42)
    first_id, first_created = cp.enqueue_user_notification(42, "moderation", "Account update", "Your account was reviewed.", "moderation:42:appeal_1")
    second_id, second_created = cp.enqueue_user_notification(42, "moderation", "Duplicate", "Should not create another row.", "moderation:42:appeal_1")

    assert first_created is True
    assert (second_id, second_created) == (first_id, False)
    pending = cp.list_pending_notifications(10)
    assert len(pending) == 1
    assert cp.mark_notification_failed(first_id, "temporary delivery error") is True
    assert cp.mark_notification_delivered(first_id) is True
    assert cp.list_pending_notifications(10) == []


def test_notification_retry_cap_dead_letters_permanent_failures(platform_db):
    cp.ensure_user(42)
    notification_id, _ = cp.enqueue_user_notification(42, "system", "Update", "Please review this update.", "retry-cap:42")
    for _ in range(cp.MAX_NOTIFICATION_ATTEMPTS):
        assert cp.mark_notification_sending(notification_id) is True
        assert cp.mark_notification_failed(notification_id, "permanent delivery failure") is True
    with sqlite3.connect(platform_db) as connection:
        status = connection.execute("SELECT status, attempt_count FROM user_notifications WHERE notification_id = ?", (notification_id,)).fetchone()
    assert status == ("dead_letter", cp.MAX_NOTIFICATION_ATTEMPTS)
    assert cp.list_pending_notifications(10) == []


def test_bulk_job_requires_short_lived_confirmation(platform_db):
    cp.ensure_user(9001)
    job = cp.create_bulk_job(9001, "mass_ban", {"reason": "abuse"}, [42, 43], ttl_minutes=5)
    assert job["status"] == "preview"
    assert cp.confirm_bulk_job(job["job_id"], "wrong-token", 9001) is None
    confirmed = cp.confirm_bulk_job(job["job_id"], job["confirmation_token"], 9001)
    assert confirmed is not None
    assert confirmed["status"] == "confirmed"
    assert cp.confirm_bulk_job(job["job_id"], job["confirmation_token"], 9001) is None


def test_admin_analytics_cover_banned_suspicious_top_users_and_referrers(platform_db):
    cp.ensure_user(9001)
    for user_id in (42, 43, 44):
        cp.ensure_user(user_id)
    cp.set_user_status(44, cp.STATUS_BANNED, "policy violation")
    cp.create_operation("op_42", 42, 42, "check", "https://example.com")
    cp.create_operation("op_42_2", 42, 42, "check", "https://example.com")
    cp.create_operation("op_43", 43, 43, "check", "https://example.com")
    cp.record_risk_event(43, None, 0.95, 0.95, "human_review", {"reason": "repeat suspicious pattern"}, "test", True)
    code = cp.get_or_create_referral_code(42)
    cp.attribute_referral(43, code)
    analytics = cp.get_admin_analytics(10)

    assert analytics["banned_users"][0]["telegram_user_id"] == 44
    assert analytics["suspicious_users"][0]["telegram_user_id"] == 43
    assert analytics["top_users"][0]["telegram_user_id"] == 42
    assert analytics["top_referrers"][0]["telegram_user_id"] == 42


def test_developer_event_feed_is_owner_scoped_and_cursorable(platform_db):
    cp.ensure_user(42)
    cp.ensure_user(43)
    first = cp.record_developer_event(42, "watcher_alert", {"watcher_id": "w1", "summary": "new post"})
    cp.record_developer_event(43, "watcher_alert", {"watcher_id": "w2", "summary": "other"})
    events = cp.list_developer_events(42, limit=10)
    assert [row["event_id"] for row in events] == [first]
    assert cp.list_developer_events(42, after_event_id=first, limit=10) == []


def test_role_audience_excludes_banned_users_and_is_role_scoped(platform_db):
    cp.ensure_user(9001)
    cp.ensure_user(42)
    cp.ensure_user(43)
    cp.set_user_role(43, cp.ROLE_DEVELOPER)
    cp.set_user_status(42, cp.STATUS_BANNED, "test")
    assert [row["telegram_user_id"] for row in cp.list_users_by_role(cp.ROLE_DEVELOPER)] == [43]
    assert [row["telegram_user_id"] for row in cp.list_users_by_role(cp.ROLE_USER)] == []


def test_maintenance_history_snapshot_and_queue_lifecycle_are_durable(platform_db):
    state = cp.set_maintenance_state("scheduled", "Planned update", "database migration", 9001, incident_id="inc_test")
    assert state["mode"] == "scheduled"
    assert state["started_at"] is None
    assert cp.list_maintenance_events(5)[0]["reason"] == "database migration"
    snapshot_id = cp.save_runtime_snapshot("crash", {"api_key": "must not be logged", "queue": {"queued": 2}}, "inc_test")
    assert snapshot_id.startswith("snp_")
    assert cp.get_latest_runtime_snapshot("crash")["snapshot_id"] == snapshot_id
    assert cp.create_queue_entry("op_queue", 42, 42, "check", 10, 15) is True
    assert cp.create_queue_entry("op_queue", 42, 42, "check", 10, 15) is False
    assert cp.claim_queue_entry("op_queue") is True
    assert cp.claim_queue_entry("op_queue") is False
    assert cp.update_queue_entry("op_queue", "succeeded") is True
    assert cp.get_queue_stats()["counts"]["succeeded"] == 1


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


def test_configured_admin_inherits_developer_capabilities_and_can_create_key(platform_db, monkeypatch):
    monkeypatch.setenv("API_KEY_HASH_SECRET", "test-api-key-secret")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    admin = cp.ensure_user(9001)

    assert admin["role"] == cp.ROLE_ADMIN
    assert cp.is_admin(9001) is True
    assert cp.is_developer(9001) is True
    created = cp.create_api_key(9001, "admin relay", ["check"])
    assert cp.authenticate_api_key(created["key"])["user_id"] == 9001


def test_non_admin_still_cannot_create_developer_key_without_approval(platform_db, monkeypatch):
    monkeypatch.setenv("API_KEY_HASH_SECRET", "test-api-key-secret")
    cp.ensure_user(42)

    assert cp.is_developer(42) is False
    with pytest.raises(PermissionError):
        cp.create_api_key(42, "blocked", ["check"])


def test_automatic_recovery_requires_stability_window_and_preserves_source(platform_db):
    incident_id = "inc_auto_test"
    state = cp.set_maintenance_state(
        "hard_maintenance",
        "Temporary outage",
        "An unexpected runtime failure triggered the automatic safety stop.",
        incident_id=incident_id,
        metadata={"source": "automatic_failsafe", "consecutive_healthy_checks": 0},
    )
    assert state["mode"] == "hard_maintenance"
    assert cp.recover_automatic_maintenance(incident_id, 3) is None
    assert cp.update_maintenance_recovery_progress(incident_id, 2, cp.utc_now(), "healthy") is True
    assert cp.recover_automatic_maintenance(incident_id, 3) is None
    assert cp.update_maintenance_recovery_progress(incident_id, 3, cp.utc_now(), "healthy") is True
    recovered = cp.recover_automatic_maintenance(incident_id, 3)
    assert recovered["mode"] == "operational"
    assert recovered["metadata"]["recovery_state"] == "recovered"
    assert cp.recover_automatic_maintenance(incident_id, 3) is None


def test_automatic_recovery_does_not_clear_manual_or_scheduled_maintenance(platform_db):
    manual = cp.set_maintenance_state(
        "hard_maintenance", "Manual hold", "Administrator maintenance", 9001,
        incident_id="inc_manual", metadata={"source": "telegram_command", "consecutive_healthy_checks": 5},
    )
    assert cp.update_maintenance_recovery_progress("inc_manual", 6, cp.utc_now(), "healthy") is False
    assert cp.recover_automatic_maintenance("inc_manual", 3) is None
    assert cp.get_maintenance_state()["mode"] == manual["mode"]

    scheduled = cp.set_maintenance_state(
        "hard_maintenance", "Scheduled hold", "Scheduled maintenance", 9001,
        incident_id="inc_scheduled", metadata={"source": "scheduled_maintenance_worker", "consecutive_healthy_checks": 5},
    )
    assert cp.update_maintenance_recovery_progress("inc_scheduled", 6, cp.utc_now(), "healthy") is False
    assert cp.recover_automatic_maintenance("inc_scheduled", 3) is None
    assert cp.get_maintenance_state()["mode"] == scheduled["mode"]


def test_ad_campaign_permission_loss_circuit_breaker_pauses_at_distinct_target_threshold(platform_db):
    cp.ensure_user(9001)
    campaign = cp.create_ad_campaign(9001, "GreyAI", "Permission-safe ad", [-1001, -1002], 1, 3600)
    confirmed = cp.confirm_ad_campaign(campaign["campaign_id"], campaign["confirmation_token"], 9001)
    assert confirmed["status"] == "active"
    cp.ensure_ad_delivery_rows(campaign["campaign_id"], 1, [-1001, -1002])

    cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:-1001", "permission_loss:bot removed from target chat")
    assert cp.count_ad_permission_loss_targets(campaign["campaign_id"]) == 1
    assert cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2) is None
    assert cp.get_ad_campaign(campaign["campaign_id"])["status"] == "active"

    cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:-1002", "permission_loss:group sending permission lost")
    paused = cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2)
    assert paused["permission_loss_count"] == 2
    stored = cp.get_ad_campaign(campaign["campaign_id"])
    assert stored["status"] == "paused"
    assert stored["pause_reason"]
    assert stored["paused_at"]


def test_ad_campaign_resume_resets_only_permission_loss_dead_letters(platform_db):
    cp.ensure_user(9001)
    campaign = cp.create_ad_campaign(9001, "GreyAI", "Retryable ad", [-1001, -1002], 1, 3600)
    cp.confirm_ad_campaign(campaign["campaign_id"], campaign["confirmation_token"], 9001)
    cp.ensure_ad_delivery_rows(campaign["campaign_id"], 1, [-1001, -1002])
    cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:-1001", "permission_loss:bot removed from target chat")
    cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:-1002", "permission_loss:channel posting permission lost")
    assert cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2)

    resumed = cp.resume_ad_campaign(campaign["campaign_id"], 9001)
    assert resumed["status"] == "active"
    assert resumed["next_occurrence"] == 1
    assert resumed["pause_reason"] is None
    pending = cp.list_pending_ad_deliveries(campaign["campaign_id"], 1, 10)
    assert {row["target_chat_id"] for row in pending} == {-1001, -1002}
    assert all(row["status"] == "pending" and row["attempt_count"] == 0 for row in pending)


def test_ad_campaign_permission_loss_pause_requires_distinct_targets(platform_db):
    cp.ensure_user(9001)
    campaign = cp.create_ad_campaign(9001, "GreyAI", "Distinct targets only", [-1001], 1, 3600)
    cp.confirm_ad_campaign(campaign["campaign_id"], campaign["confirmation_token"], 9001)
    cp.ensure_ad_delivery_rows(campaign["campaign_id"], 1, [-1001])
    cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:-1001", "permission_loss:bot removed from target chat")
    assert cp.count_ad_permission_loss_targets(campaign["campaign_id"]) == 1
    assert cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2) is None
    assert cp.get_ad_campaign(campaign["campaign_id"])["status"] == "active"


def test_ad_campaign_resume_is_owner_scoped(platform_db):
    cp.ensure_user(9001)
    cp.ensure_user(9002)
    campaign = cp.create_ad_campaign(9001, "GreyAI", "Owner scoped", [-1001, -1002], 1, 3600)
    cp.confirm_ad_campaign(campaign["campaign_id"], campaign["confirmation_token"], 9001)
    cp.ensure_ad_delivery_rows(campaign["campaign_id"], 1, [-1001, -1002])
    for target in (-1001, -1002):
        cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:{target}", "permission_loss:bot removed from target chat")
    cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2)
    assert cp.resume_ad_campaign(campaign["campaign_id"], 9002) is None
    assert cp.get_ad_campaign(campaign["campaign_id"])["status"] == "paused"


def test_ad_campaign_listing_includes_pause_metadata(platform_db):
    cp.ensure_user(9001)
    campaign = cp.create_ad_campaign(9001, "GreyAI", "Listable", [-1001, -1002], 1, 3600)
    cp.confirm_ad_campaign(campaign["campaign_id"], campaign["confirmation_token"], 9001)
    cp.ensure_ad_delivery_rows(campaign["campaign_id"], 1, [-1001, -1002])
    for target in (-1001, -1002):
        cp.mark_ad_delivery_dead_letter(f"{campaign['campaign_id']}:1:{target}", "permission_loss:bot removed from target chat")
    cp.pause_ad_campaign_for_permission_loss(campaign["campaign_id"], 2)
    listed = cp.list_ad_campaigns_for_admin(9001, 10)
    assert listed[0]["pause_reason"]
    assert listed[0]["paused_at"]


def test_ad_campaign_threshold_zero_is_explicitly_disabled_in_bot(monkeypatch):
    import bot
    monkeypatch.setattr(bot, "AD_CAMPAIGN_PERMISSION_LOSS_PAUSE_THRESHOLD", 0)
    monkeypatch.setattr(bot, "pause_ad_campaign_for_permission_loss", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("disabled circuit breaker must not call persistence")))
    assert bot.maybe_pause_ad_campaign_for_permission_loss("ad_disabled") is False


def test_ad_campaign_pause_alert_is_idempotent_keyed(monkeypatch):
    import bot
    captured = []
    monkeypatch.setattr(bot, "AD_CAMPAIGN_PERMISSION_LOSS_PAUSE_THRESHOLD", 2)
    monkeypatch.setattr(bot, "pause_ad_campaign_for_permission_loss", lambda *args, **kwargs: {"campaign_id": "ad_alert", "permission_loss_count": 2, "threshold": 2})
    monkeypatch.setattr(bot, "admin_ids", lambda: {9001})
    monkeypatch.setattr(bot, "enqueue_safe_user_notification", lambda *args: captured.append(args))
    assert bot.maybe_pause_ad_campaign_for_permission_loss("ad_alert") is True
    assert captured[0][4] == "ad-campaign-paused:ad_alert"
    assert "2 distinct targets" in captured[0][3]
    assert "TELEGRAM_BOT_TOKEN" not in captured[0][3]

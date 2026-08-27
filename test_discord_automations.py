import base64
import sqlite3

import pytest

import control_plane as cp


@pytest.fixture
def platform_db(tmp_path, monkeypatch):
    path = tmp_path / "discord-automations.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "automation-test-secret")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"automation-test-session-secret-32"[:32]).decode())
    cp.init_platform_db()
    import bot

    bot.init_db()
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS domain_policies (pattern TEXT PRIMARY KEY, effect TEXT NOT NULL, created_by_user_id INTEGER NOT NULL, created_at TEXT, updated_at TEXT)")
        connection.commit()
    return path


def test_discord_watcher_persistence_is_owner_and_channel_scoped(platform_db):
    watcher_id = cp.create_discord_watcher(
        owner_user_id=42,
        guild_id=100,
        channel_id=200,
        url="https://example.com",
        actions=["condition_contains:Stock"],
        interval_seconds=60,
    )

    rows = cp.list_discord_watchers(42)
    assert len(rows) == 1
    assert rows[0]["watcher_id"] == watcher_id
    assert rows[0]["guild_id"] == 100
    assert rows[0]["channel_id"] == 200
    assert cp.list_discord_watchers(99) == []
    assert cp.deactivate_discord_watcher(watcher_id, 99) is False
    assert cp.deactivate_discord_watcher(watcher_id, 42) is True
    assert cp.list_discord_watchers(42) == []


def test_discord_schedule_persistence_round_trips_config_and_ownership(platform_db):
    schedule_id = cp.create_discord_schedule(
        owner_user_id=42,
        guild_id=None,
        channel_id=300,
        config={"schedule_time": "08:00", "timezone": "UTC", "urls": ["https://example.com"]},
        next_run_at="2026-08-28T08:00:00+00:00",
    )

    rows = cp.list_discord_schedules(42)
    assert rows[0]["schedule_id"] == schedule_id
    assert rows[0]["guild_id"] is None
    assert rows[0]["channel_id"] == 300
    assert rows[0]["config"]["timezone"] == "UTC"
    assert cp.deactivate_discord_schedule(schedule_id, 99) is False
    assert cp.deactivate_discord_schedule(schedule_id, 42) is True
    assert cp.list_discord_schedules(42) == []


def test_discord_watcher_and_schedule_parsers_validate_bounded_inputs(monkeypatch):
    import bot
    import discord_bot

    monkeypatch.setattr(bot, "is_domain_allowed", lambda url: url == "https://example.com")
    monkeypatch.setattr(bot, "ALLOWED_DOMAINS", ["example.com"])
    monkeypatch.setattr(bot, "list_domain_policies", lambda: [])
    watcher = discord_bot.parse_discord_watch_spec("https://example.com", 60, "condition_contains:Stock")
    assert watcher["url"] == "https://example.com"
    assert watcher["interval_seconds"] == 60
    assert watcher["actions"] == ["condition_contains:Stock"]
    assert discord_bot.parse_discord_watch_spec("https://blocked.example", 60, "") is None

    schedule = discord_bot.parse_discord_schedule_spec("08:00", "UTC", "weekdays", "https://example.com", "Summarize")
    assert schedule["config"]["timezone"] == "UTC"
    assert schedule["config"]["days"] == [0, 1, 2, 3, 4]
    assert schedule["config"]["urls"] == ["https://example.com"]
    assert discord_bot.parse_discord_schedule_spec("25:00", "UTC", "daily", "https://example.com", "Summarize") is None


def test_discord_command_registry_includes_monitoring_surfaces(platform_db):
    import discord_bot

    client = discord_bot.create_discord_bot()
    names = {command.name for command in client.tree.get_commands()}
    assert {"watch", "watchers", "stopwatch", "schedule", "schedules", "unschedule"} <= names


def test_discord_command_registry_includes_fetch(platform_db):
    import discord_bot

    client = discord_bot.create_discord_bot()
    assert "fetch" in {command.name for command in client.tree.get_commands()}


def test_discord_download_policy_message_is_redacted_and_plan_gated(monkeypatch):
    import discord_bot

    monkeypatch.setattr(discord_bot.grey, "download_policy_for_user", lambda _owner: {"allowed": False, "reason": "free_plan"})
    assert "Free plan" in discord_bot.discord_download_policy_message(42)
    assert "token" not in discord_bot.discord_download_policy_message(42).lower()

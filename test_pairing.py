import base64
import sqlite3

import pytest

import control_plane as cp


@pytest.fixture
def platform_db(tmp_path, monkeypatch):
    path = tmp_path / "pairing.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "pairing-test-secret")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"pairing-test-session-secret-32bytes"[:32]).decode())
    cp.init_platform_db()
    return path


def test_pairing_challenge_is_single_use_and_binds_the_authenticated_telegram_user(platform_db):
    telegram_user_id = 6411860985
    discord_user_id = "discord-1001"
    cp.ensure_user(telegram_user_id, "telegram_user", "Telegram User")
    cp.ensure_platform_identity("discord", discord_user_id, "discord_user", "Discord User")

    code = cp.create_account_pairing_challenge(discord_user_id, ttl_seconds=600)
    pairing = cp.consume_account_pairing_challenge(code, telegram_user_id)

    assert pairing is not None
    assert pairing["telegram_user_id"] == telegram_user_id
    assert pairing["discord_user_id"] == discord_user_id
    assert cp.get_discord_pairing(discord_user_id)["telegram_user_id"] == telegram_user_id
    assert cp.consume_account_pairing_challenge(code, telegram_user_id) is None


def test_pairing_rejects_invalid_codes_and_consumes_a_valid_private_confirmation(platform_db):
    cp.ensure_user(202)
    cp.ensure_platform_identity("discord", "discord-202")
    code = cp.create_account_pairing_challenge("discord-202", ttl_seconds=600)

    assert cp.consume_account_pairing_challenge("not-a-real-code", 202) is None
    pairing = cp.consume_account_pairing_challenge(code, 202)
    assert pairing is not None
    assert cp.get_discord_pairing("discord-202")["telegram_user_id"] == 202


def test_pairing_rejects_replacing_an_active_identity_without_unpairing(platform_db):
    cp.ensure_user(101)
    cp.ensure_user(202)
    cp.ensure_platform_identity("discord", "discord-202")
    first_code = cp.create_account_pairing_challenge("discord-202", ttl_seconds=600)
    assert cp.consume_account_pairing_challenge(first_code, 101) is not None

    with pytest.raises(ValueError, match="discord_identity_already_paired"):
        cp.create_account_pairing_challenge("discord-202", ttl_seconds=600)
    assert cp.get_discord_pairing("discord-202")["telegram_user_id"] == 101


def test_pairing_expiry_and_revoke_are_durable(platform_db):
    cp.ensure_user(101)
    cp.ensure_platform_identity("discord", "discord-101")
    code = cp.create_account_pairing_challenge("discord-101", ttl_seconds=600)
    with sqlite3.connect(platform_db) as connection:
        connection.execute("UPDATE account_pairing_challenges SET expires_at = '2000-01-01T00:00:00+00:00'")
        connection.commit()
    assert cp.consume_account_pairing_challenge(code, 101) is None

    fresh_code = cp.create_account_pairing_challenge("discord-101", ttl_seconds=600)
    assert cp.consume_account_pairing_challenge(fresh_code, 101) is not None
    assert cp.revoke_account_pairing("discord-101") is True
    assert cp.get_discord_pairing("discord-101") is None


def test_discord_server_access_is_closed_by_default(platform_db):
    import discord_bot

    class Guild:
        id = 123456789

    assert discord_bot.guild_is_enabled(None) is True
    assert discord_bot.guild_is_enabled(Guild()) is False


def test_discord_client_registers_native_pairing_commands(platform_db):
    import discord_bot

    client = discord_bot.create_discord_bot()
    assert {command.name for command in client.tree.get_commands()} >= {"pair", "unpair", "help"}


def test_discord_canonical_identity_requires_a_pairing(platform_db):
    import discord_bot

    cp.ensure_user(101)
    assert discord_bot.canonical_telegram_user_id("discord-unpaired") is None
    cp.ensure_platform_identity("discord", "discord-101")
    code = cp.create_account_pairing_challenge("discord-101")
    assert cp.consume_account_pairing_challenge(code, 101) is not None
    assert discord_bot.canonical_telegram_user_id("discord-101") == 101

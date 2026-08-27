import base64
import sqlite3
from types import SimpleNamespace

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


def test_legacy_pairing_constraints_migrate_without_dropping_history(tmp_path, monkeypatch):
    path = tmp_path / "legacy-pairing.db"
    monkeypatch.setenv("DB_PATH", str(path))
    monkeypatch.setenv("PUBLIC_MODE", "true")
    monkeypatch.setenv("ADMIN_TELEGRAM_IDS", "9001")
    monkeypatch.setenv("API_KEY_HASH_SECRET", "pairing-test-secret")
    monkeypatch.setenv("SESSION_ENCRYPTION_KEY", base64.urlsafe_b64encode(b"pairing-test-session-secret-32bytes"[:32]).decode())
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE account_pairings (
                pairing_id TEXT PRIMARY KEY,
                telegram_user_id INTEGER NOT NULL,
                discord_user_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'revoked')),
                created_at TEXT NOT NULL,
                last_confirmed_at TEXT NOT NULL,
                revoked_at TEXT,
                UNIQUE(telegram_user_id, status),
                UNIQUE(discord_user_id, status)
            )
            """
        )
        connection.execute(
            "INSERT INTO account_pairings VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("legacy-revoked", 101, "legacy-discord", "revoked", "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00", "2026-01-02T00:00:00+00:00"),
        )
        connection.commit()

    cp.init_platform_db()

    with sqlite3.connect(path) as connection:
        row = connection.execute("SELECT pairing_id, status FROM account_pairings WHERE pairing_id = ?", ("legacy-revoked",)).fetchone()
        indexes = connection.execute("PRAGMA index_list(account_pairings)").fetchall()
    assert row == ("legacy-revoked", "revoked")
    assert any("active_telegram" in index[1] and index[2] for index in indexes)
    assert any("active_discord" in index[1] and index[2] for index in indexes)


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


def test_pairing_challenge_issuance_is_rate_limited_and_replaces_stale_pending_codes(platform_db, monkeypatch):
    monkeypatch.setenv("PAIRING_CHALLENGE_COOLDOWN_SECONDS", "5")
    first = cp.create_account_pairing_challenge("discord-throttle")
    with pytest.raises(ValueError, match="pairing_challenge_rate_limited"):
        cp.create_account_pairing_challenge("discord-throttle")

    with sqlite3.connect(platform_db) as connection:
        connection.execute(
            "UPDATE account_pairing_challenges SET created_at = '2000-01-01T00:00:00+00:00' WHERE requested_platform_user_id = ?",
            ("discord-throttle",),
        )
        connection.commit()
    second = cp.create_account_pairing_challenge("discord-throttle")
    assert cp.consume_account_pairing_challenge(first, 401) is None
    assert cp.consume_account_pairing_challenge(second, 401) is not None


def test_concurrent_pairing_confirmation_has_one_winner_and_no_database_error(platform_db):
    from concurrent.futures import ThreadPoolExecutor

    cp.ensure_platform_identity("discord", "discord-race")
    code = cp.create_account_pairing_challenge("discord-race")

    def consume(user_id):
        try:
            return ("ok", cp.consume_account_pairing_challenge(code, user_id))
        except Exception as exc:  # the security contract forbids leaking a DB race
            return ("error", type(exc).__name__)

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(consume, (401, 402)))

    assert all(kind == "ok" for kind, _ in outcomes)
    assert sum(result is not None for _, result in outcomes) == 1
    assert cp.get_discord_pairing("discord-race") is not None


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


def test_telegram_pair_command_rejects_non_private_chat(monkeypatch):
    import asyncio

    import bot

    replies = []

    class Message:
        async def reply_text(self, text, **kwargs):
            replies.append(text)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=101, username="telegram-user", full_name="Telegram User"),
        effective_chat=SimpleNamespace(type="group"),
        message=Message(),
    )
    context = SimpleNamespace(args=["pairing-code"])
    monkeypatch.setattr(bot, "ensure_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "is_allowed_user", lambda user_id: True)
    monkeypatch.setattr(bot, "consume_account_pairing_challenge", lambda *args, **kwargs: pytest.fail("group chat must not consume a pairing code"))

    asyncio.run(bot.pair_command(update, context))

    assert replies == ["For security, Discord pairing can only be confirmed in GreyAI’s private Telegram chat."]


def test_telegram_pair_command_consumes_code_only_after_private_chat_check(monkeypatch):
    import asyncio

    import bot

    replies = []

    class Message:
        async def reply_text(self, text, **kwargs):
            replies.append(text)

    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=101, username="telegram-user", full_name="Telegram User"),
        effective_chat=SimpleNamespace(type="private"),
        message=Message(),
    )
    context = SimpleNamespace(args=["pairing-code"])
    monkeypatch.setattr(bot, "ensure_user", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot, "is_allowed_user", lambda user_id: True)
    monkeypatch.setattr(bot, "consume_account_pairing_challenge", lambda code, user_id: {"discord_user_id": "discord-101"})
    monkeypatch.setattr(bot, "log_audit", lambda *args, **kwargs: None)

    asyncio.run(bot.pair_command(update, context))

    assert replies[0].startswith("✅ Telegram and Discord are now paired.")


def test_discord_runtime_resolver_prefers_running_main_module(monkeypatch):
    import sys
    import types

    import discord_bot

    running_bot = types.ModuleType("__main__")
    running_bot.run_browser_request = object()
    imported_bot = types.ModuleType("bot")
    imported_bot.run_browser_request = object()
    monkeypatch.setitem(sys.modules, "__main__", running_bot)
    monkeypatch.setitem(sys.modules, "bot", imported_bot)

    assert discord_bot._grey_runtime_module() is running_bot


def test_discord_server_access_is_closed_by_default(platform_db):
    import discord_bot

    class Guild:
        id = 123456789

    assert discord_bot.guild_is_enabled(None) is True
    assert discord_bot.guild_is_enabled(Guild()) is False


def test_discord_guild_scope_requires_an_explicit_channel_allowlist(monkeypatch):
    import discord_bot

    class Guild:
        id = 123456789

    monkeypatch.setattr(discord_bot, "DISCORD_ALLOWED_GUILD_IDS", {123456789})
    monkeypatch.setattr(discord_bot, "DISCORD_ALLOWED_CHANNEL_IDS", set())
    assert discord_bot.discord_context_is_enabled(Guild(), 987) is False

    monkeypatch.setattr(discord_bot, "DISCORD_ALLOWED_CHANNEL_IDS", {987})
    assert discord_bot.discord_context_is_enabled(Guild(), 987) is True
    assert discord_bot.discord_context_is_enabled(Guild(), 988) is False
    assert discord_bot.discord_context_is_enabled(None, 988) is True


def test_discord_pairing_issuance_audits_without_storing_the_code(platform_db):
    import asyncio

    import discord_bot

    class Response:
        def __init__(self):
            self.messages = []

        async def send_message(self, content, **kwargs):
            self.messages.append((content, kwargs))

    interaction = SimpleNamespace(
        guild=None,
        user=SimpleNamespace(id=4555, name="pairer", display_name="Pairer"),
        response=Response(),
    )
    asyncio.run(discord_bot.start_pairing(interaction))

    content = interaction.response.messages[0][0]
    assert "/pair " in content
    code = content.split("/pair ", 1)[1].split("`", 1)[0].strip()
    with sqlite3.connect(platform_db) as connection:
        challenge = connection.execute("SELECT code_hash FROM account_pairing_challenges WHERE requested_platform_user_id = ?", ("4555",)).fetchone()
        audit = connection.execute(
            "SELECT action, outcome, metadata_json FROM security_audit_events WHERE actor_platform = 'discord' AND actor_id = ? ORDER BY created_at DESC LIMIT 1",
            ("4555",),
        ).fetchone()
    assert challenge is not None and challenge[0] != code
    assert audit == ("pairing_challenge_issuance", "success", '{"ttl_seconds":"600"}')
    assert code not in audit[2]


def test_discord_client_registers_native_pairing_commands(platform_db):
    import discord_bot

    client = discord_bot.create_discord_bot()
    assert {command.name for command in client.tree.get_commands()} >= {"pair", "unpair", "start", "help", "ask", "check", "status", "health", "settings", "grey", "sessions", "support", "paysupport", "terms", "crypto", "upgrade", "referral", "dashboard", "report", "appeal"}


def test_discord_unpair_confirmation_is_owner_bound_and_audited(monkeypatch):
    import asyncio

    import discord_bot

    events = []
    monkeypatch.setattr(discord_bot, "revoke_account_pairing", lambda discord_id: True)
    monkeypatch.setattr(discord_bot, "record_security_audit", lambda *args, **kwargs: events.append((args, kwargs)))

    class Response:
        def __init__(self):
            self.edits = []

        async def edit_message(self, **kwargs):
            self.edits.append(kwargs)

        async def send_message(self, *args, **kwargs):
            raise AssertionError("a paired owner should not receive a denial")

    view = discord_bot.UnpairConfirmationView("discord-owner")
    interaction = SimpleNamespace(user=SimpleNamespace(id="discord-owner"), response=Response())
    asyncio.run(view.children[0].callback(interaction))

    assert interaction.response.edits == [{"content": "The Telegram↔Discord pairing was revoked.", "view": None}]
    assert events == [(('discord', 'discord-owner', 'pairing_revocation', 'success'), {})]


def test_discord_account_and_sessions_summaries_are_scoped_to_shared_user(monkeypatch):
    import discord_bot

    monkeypatch.setattr(discord_bot, "get_user", lambda user_id: {"plan": "pro", "role": "developer", "status": "active"})
    monkeypatch.setattr(discord_bot.grey, "list_user_sessions", lambda user_id: ["example.com", "news.example"])

    account = discord_bot._account_summary(101)
    sessions = discord_bot._sessions_summary(101)

    assert "Plan:** PRO" in account
    assert "Role:** DEVELOPER" in account
    assert "Status:** ACTIVE" in account
    assert "example.com" in sessions
    assert "news.example" in sessions


def test_discord_settings_summary_uses_shared_account_state(monkeypatch):
    import discord_bot

    monkeypatch.setattr(discord_bot.grey, "get_user_settings", lambda user_id: {
        "persistent_login_enabled": True,
        "auto_save_sessions_enabled": True,
        "challenge_handoff_enabled": False,
    })
    monkeypatch.setattr(discord_bot.grey, "list_user_sessions", lambda user_id: ["example.com"])
    monkeypatch.setattr(discord_bot.grey, "manual_challenges", {"handoff": {"user_id": 101}})

    summary = discord_bot._settings_summary(101)

    assert "Persistent login + automatic session save:** ON" in summary
    assert "Manual challenge handoff:** OFF" in summary
    assert "Saved encrypted sessions:** 1" in summary
    assert "Active manual handoffs:** 1" in summary


def test_discord_handoff_view_accepts_only_safe_url_buttons(platform_db):
    import discord_bot

    markup = SimpleNamespace(inline_keyboard=[[SimpleNamespace(text="Open handoff", url="https://example.test/challenge/abc"), SimpleNamespace(text="Unsafe", url="javascript:alert(1)")]])
    view = discord_bot._discord_view_from_telegram_markup(markup)
    assert view is not None
    assert len(view.children) == 1
    assert view.children[0].url == "https://example.test/challenge/abc"


def test_repair_after_discord_unpair_creates_a_new_active_link(platform_db):
    cp.ensure_user(101)
    cp.ensure_user(202)
    cp.ensure_platform_identity("discord", "discord-repair")

    first_code = cp.create_account_pairing_challenge("discord-repair")
    assert cp.consume_account_pairing_challenge(first_code, 101) is not None
    assert cp.revoke_account_pairing("discord-repair") is True

    second_code = cp.create_account_pairing_challenge("discord-repair")
    second_pairing = cp.consume_account_pairing_challenge(second_code, 202)

    assert second_pairing is not None
    assert second_pairing["telegram_user_id"] == 202
    assert cp.get_discord_pairing("discord-repair")["telegram_user_id"] == 202


def test_pairing_can_be_revoked_and_repaired_repeatedly_without_losing_history(platform_db):
    cp.ensure_user(101)
    cp.ensure_user(202)
    cp.ensure_user(303)
    cp.ensure_platform_identity("discord", "discord-repeat")

    first = cp.create_account_pairing_challenge("discord-repeat")
    assert cp.consume_account_pairing_challenge(first, 101) is not None
    assert cp.revoke_account_pairing("discord-repeat") is True

    second = cp.create_account_pairing_challenge("discord-repeat")
    assert cp.consume_account_pairing_challenge(second, 202) is not None
    assert cp.revoke_account_pairing("discord-repeat") is True

    third = cp.create_account_pairing_challenge("discord-repeat")
    assert cp.consume_account_pairing_challenge(third, 303) is not None
    with sqlite3.connect(platform_db) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM account_pairings WHERE discord_user_id = ? AND status = 'revoked'",
            ("discord-repeat",),
        ).fetchone()[0]
    assert count == 2


def test_discord_account_commands_create_owner_scoped_report_and_appeal(platform_db, monkeypatch):
    import asyncio

    import discord_bot

    monkeypatch.setattr(discord_bot, "_authenticate_interaction", lambda interaction: asyncio.sleep(0, result=42))

    class Response:
        def __init__(self):
            self.messages = []

        async def send_message(self, content, **kwargs):
            self.messages.append((content, kwargs))

    report_interaction = SimpleNamespace(response=Response())
    asyncio.run(discord_bot.report_command(report_interaction, "The check result was stale."))
    assert report_interaction.response.messages[0][0].startswith("Report opened:")
    assert cp.list_reports("open", 10)

    appeal_interaction = SimpleNamespace(response=Response())
    asyncio.run(discord_bot.appeal_command(appeal_interaction, "Please review my account status."))
    assert appeal_interaction.response.messages[0][0].startswith("Appeal opened:")
    assert cp.list_appeals("open", 10)


def test_discord_account_command_helpers_keep_payment_and_secret_boundaries(platform_db, monkeypatch):
    import discord_bot

    monkeypatch.delenv("CRYPTO_CHECKOUT_URL", raising=False)
    assert "not enabled" in discord_bot.crypto_account_text().lower()
    assert "Telegram Stars" in discord_bot.upgrade_account_text()
    assert "secret" not in discord_bot.referral_account_text(42).lower()


def test_discord_private_dm_uses_canonical_telegram_conversation_scope():
    import discord_bot

    message = SimpleNamespace(guild=None, channel=SimpleNamespace(id=987654321))

    assert discord_bot.discord_conversation_id(message, owner_id=101) == 101
    assert discord_bot.discord_conversation_id(message) == 987654321


def test_unpaired_discord_message_never_reaches_interpreter(platform_db, monkeypatch):
    import asyncio

    import discord_bot

    replies = []

    class Author:
        bot = False
        id = 7001
        name = "unpaired"
        display_name = "Unpaired"

    class Message:
        id = 9001
        content = "Please browse this"
        guild = None
        author = Author()
        channel = SimpleNamespace(id=9901)
        reference = None

        async def reply(self, text, **kwargs):
            replies.append(text)

    monkeypatch.setattr(discord_bot, "canonical_user_id", lambda _: None)
    monkeypatch.setattr(discord_bot.grey, "parse_natural_language_intent", lambda *args, **kwargs: pytest.fail("unpaired input must not reach the interpreter"))

    asyncio.run(discord_bot.handle_discord_message(Message()))

    assert replies == ["Use `/pair` in a private Discord context, then confirm the code in GreyAI’s private Telegram chat."]


def test_discord_slash_chat_defers_then_edits_without_double_response(monkeypatch):
    import asyncio

    import discord_bot

    class Response:
        def __init__(self):
            self.deferred = 0
            self.sent = []

        def is_done(self):
            return self.deferred > 0 or bool(self.sent)

        async def defer(self, **kwargs):
            self.deferred += 1

        async def send_message(self, *args, **kwargs):
            self.sent.append((args, kwargs))

    class Interaction:
        guild = None
        channel_id = 8801
        user = SimpleNamespace(id=7001, name="paired", display_name="Paired")

        def __init__(self):
            self.response = Response()
            self.edits = []

        async def edit_original_response(self, **kwargs):
            self.edits.append(kwargs)

    interaction = Interaction()
    monkeypatch.setattr(discord_bot, "_authenticate_interaction", lambda _: asyncio.sleep(0, result=7001))
    monkeypatch.setattr(discord_bot.grey, "load_chat_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(discord_bot.grey, "build_native_grey_context", lambda *args, **kwargs: {})
    monkeypatch.setattr(discord_bot.grey, "parse_natural_language_intent", lambda *args, **kwargs: asyncio.sleep(0, result=None))
    monkeypatch.setattr(discord_bot.grey, "classify_message_route", lambda *args, **kwargs: "chat")
    monkeypatch.setattr(discord_bot.grey, "decide_message_route", lambda *args, **kwargs: "chat")
    monkeypatch.setattr(discord_bot.grey, "generate_chat_reply", lambda *args, **kwargs: asyncio.sleep(0, result="chat response"))
    monkeypatch.setattr(discord_bot.grey, "remember_chat_turn", lambda *args, **kwargs: None)

    asyncio.run(discord_bot.handle_discord_interaction(interaction, "hello"))

    assert interaction.response.deferred == 1
    assert interaction.response.sent == []
    assert interaction.edits == [{"content": "chat response"}]


def test_discord_status_facade_preserves_safe_handoff_view_for_message_updates():
    import asyncio

    import discord_bot

    markup = SimpleNamespace(inline_keyboard=[[SimpleNamespace(text="Open handoff", url="https://example.test/challenge/abc")]])

    class Message:
        def __init__(self):
            self.edits = []

        async def edit(self, **kwargs):
            self.edits.append(kwargs)

    message = Message()
    asyncio.run(discord_bot.DiscordStatusMessage(discord_bot._InteractionMessageShim(message)).edit_text("Paused", reply_markup=markup))

    assert message.edits[0]["content"] == "Paused"
    assert len(message.edits[0]["view"].children) == 1
    assert message.edits[0]["view"].children[0].url == "https://example.test/challenge/abc"


def test_guild_check_results_are_delivered_by_private_dm(platform_db, tmp_path):
    import asyncio

    import discord_bot

    screenshot = tmp_path / "result.png"
    screenshot.write_bytes(b"png")

    class Author:
        def __init__(self):
            self.sent = []

        async def send(self, content=None, file=None):
            self.sent.append({"content": content, "file": file})

    class Status:
        def __init__(self):
            self.edits = []

        async def edit(self, **kwargs):
            self.edits.append(kwargs)

    author = Author()
    status = Status()
    message = SimpleNamespace(guild=SimpleNamespace(id=123), author=author, channel=SimpleNamespace())
    result = {"title": "Private result", "extracted": ["Sensitive extracted text"], "screenshot": str(screenshot)}

    asyncio.run(discord_bot._deliver_check_result(message, status, result))

    assert len(author.sent) == 1
    assert "Sensitive extracted text" in author.sent[0]["content"]
    assert author.sent[0]["file"] is not None
    assert status.edits == [{"content": "The check completed. I sent the result to you in a private DM."}]
    assert not screenshot.exists()


def test_discord_canonical_identity_requires_a_pairing(platform_db):
    import discord_bot

    cp.ensure_user(101)
    assert discord_bot.canonical_telegram_user_id("discord-unpaired") is None
    cp.ensure_platform_identity("discord", "discord-101")
    code = cp.create_account_pairing_challenge("discord-101")
    assert cp.consume_account_pairing_challenge(code, 101) is not None
    assert discord_bot.canonical_telegram_user_id("discord-101") == 101

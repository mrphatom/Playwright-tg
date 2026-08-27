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


def test_discord_client_registers_native_pairing_commands(platform_db):
    import discord_bot

    client = discord_bot.create_discord_bot()
    assert {command.name for command in client.tree.get_commands()} >= {"pair", "unpair", "help", "ask", "check", "status", "settings", "grey", "sessions"}


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

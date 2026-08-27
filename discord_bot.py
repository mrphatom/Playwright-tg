"""Discord adapter for GreyAI.

Platform I/O lives here; GreyAI policy, persistence, queue, browser, and model
logic remain in the existing modules. The adapter is disabled unless a token is
configured, so adding the dependency cannot change Telegram-only deployments.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import discord
from discord import app_commands
from discord.ext import commands


def _grey_runtime_module():
    """Resolve GreyAI's live runtime without creating a duplicate module namespace.

    Production starts with ``python bot.py``, which executes the file as
    ``__main__``. Importing ``bot`` from this adapter would otherwise create a
    second set of queues, registries, and in-memory handoff state.
    """
    running_main = sys.modules.get("__main__")
    if running_main is not None and hasattr(running_main, "run_browser_request"):
        return running_main
    bot_module = sys.modules.get("bot")
    if bot_module is not None:
        return bot_module
    return importlib.import_module("bot")


class _GreyRuntimeProxy:
    def __getattr__(self, name: str):
        return getattr(_grey_runtime_module(), name)


grey = _GreyRuntimeProxy()


from control_plane import (
    canonical_telegram_user_id_for_discord,
    consume_account_pairing_challenge,
    create_account_pairing_challenge,
    ensure_platform_identity,
    get_discord_pairing,
    get_user,
    is_allowed_user,
    record_contact_log,
    revoke_account_pairing,
)

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "").strip()
DISCORD_ENABLED = os.getenv("DISCORD_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
DISCORD_ALLOWED_GUILD_IDS = {
    int(value.strip())
    for value in os.getenv("DISCORD_ALLOWED_GUILD_IDS", "").split(",")
    if value.strip().isdigit()
}
DISCORD_MESSAGE_LIMIT = 1900


def discord_conversation_id(message: discord.Message) -> int:
    """Use the Discord channel Snowflake as the durable conversation scope."""
    return int(message.channel.id)


def canonical_telegram_user_id(discord_user_id: str | int) -> int | None:
    """Resolve a paired Discord identity to the canonical GreyAI Telegram account."""
    return canonical_telegram_user_id_for_discord(str(discord_user_id))


def canonical_user_id(discord_user_id: str | int) -> int | None:
    return canonical_telegram_user_id(discord_user_id)


def guild_is_enabled(guild: discord.Guild | None) -> bool:
    """Allow DMs by default; guilds require an explicit allowlist entry."""
    return guild is None or int(guild.id) in DISCORD_ALLOWED_GUILD_IDS


def _safe_text(value: Any, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
    return str(value or "").strip()[:limit]


def _pairing_instructions(code: str) -> str:
    return (
        "Your private GreyAI pairing code is below. Open GreyAI in Telegram and send this in the bot’s private chat:\n\n"
        f"`/pair {code}`\n\n"
        "This code expires soon, works once, and does not grant access until Telegram confirms it. Do not share it in a server channel."
    )


def _format_result(result: dict[str, Any]) -> str:
    title = _safe_text(result.get("title"), 300) or "Untitled page"
    source = _safe_text(result.get("source_url") or result.get("final_url"), 500)
    extracted = [str(item).strip() for item in result.get("extracted", []) if str(item).strip()]
    body = "\n\n".join(extracted[:8]) or "The page completed without extractable text."
    return _safe_text(f"**{title}**\n{source}\n\n{body}")


def _discord_view_from_telegram_markup(markup: Any) -> discord.ui.View | None:
    """Translate only safe URL buttons from shared Telegram status markup."""
    if not markup or not getattr(markup, "inline_keyboard", None):
        return None
    view = discord.ui.View(timeout=900)
    for row in markup.inline_keyboard:
        for button in row:
            url = str(getattr(button, "url", "") or "").strip()
            label = _safe_text(getattr(button, "text", "Open GreyAI handoff"), 80)
            if url.startswith(("https://", "http://")) and len(url) <= 2048:
                view.add_item(discord.ui.Button(label=label or "Open GreyAI handoff", url=url))
    return view if view.children else None


class DiscordStatusMessage:
    """Small edit_text-compatible facade used by the existing browser queue."""

    def __init__(self, interaction: Any):
        self.interaction = interaction

    async def edit_text(self, text: str, **kwargs: Any) -> None:
        view = _discord_view_from_telegram_markup(kwargs.get("reply_markup"))
        await self.interaction.edit_original_response(content=_safe_text(text), view=view)


async def start_pairing(interaction: discord.Interaction) -> None:
    if interaction.guild is not None:
        await interaction.response.send_message("For security, start pairing from a private Discord DM with GreyAI.", ephemeral=True)
        return
    discord_id = str(interaction.user.id)
    ensure_platform_identity("discord", discord_id, interaction.user.name, interaction.user.display_name)
    if get_discord_pairing(discord_id):
        await interaction.response.send_message("This Discord account is already paired. Use `/unpair` first if you want to replace it.", ephemeral=True)
        return
    try:
        code = create_account_pairing_challenge(discord_id, ttl_seconds=600)
    except ValueError as exc:
        if str(exc) == "discord_identity_already_paired":
            message = "This Discord account is already paired. Use `/unpair` first if you want to replace it."
        else:
            message = "I could not create a pairing challenge. Please try again shortly."
        await interaction.response.send_message(message, ephemeral=True)
        return
    await interaction.response.send_message(_pairing_instructions(code), ephemeral=True)


async def unpair_account(interaction: discord.Interaction) -> None:
    if interaction.guild is not None:
        await interaction.response.send_message("For security, manage pairing from a private Discord DM with GreyAI.", ephemeral=True)
        return
    if not get_discord_pairing(str(interaction.user.id)):
        await interaction.response.send_message("This Discord account is not currently paired.", ephemeral=True)
        return
    await interaction.response.send_message(
        "This will revoke the Telegram↔Discord link without deleting either account’s history. Press the confirmation button to continue.",
        ephemeral=True,
        view=UnpairConfirmationView(str(interaction.user.id)),
    )


class UnpairConfirmationView(discord.ui.View):
    def __init__(self, discord_user_id: str):
        super().__init__(timeout=60)
        self.discord_user_id = discord_user_id

    @discord.ui.button(label="Confirm unpair", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if str(interaction.user.id) != self.discord_user_id:
            await interaction.response.send_message("Only the Discord account owner can confirm this action.", ephemeral=True)
            return
        revoked = revoke_account_pairing(self.discord_user_id)
        await interaction.response.edit_message(content="The Telegram↔Discord pairing was revoked." if revoked else "The pairing was already revoked.", view=None)
        self.stop()

    @discord.ui.button(label="Keep pairing", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if str(interaction.user.id) != self.discord_user_id:
            await interaction.response.send_message("Only the Discord account owner can use this control.", ephemeral=True)
            return
        await interaction.response.edit_message(content="Pairing kept.", view=None)
        self.stop()


async def confirm_pairing_code(telegram_user_id: int, code: str) -> dict[str, Any] | None:
    """Telegram-side bridge used by the Telegram adapter; no Discord API call is needed."""
    return consume_account_pairing_challenge(code, int(telegram_user_id))


async def handle_discord_message(message: discord.Message) -> None:
    if message.author.bot or not guild_is_enabled(message.guild):
        return
    text = _safe_text(message.content, 4000)
    if not text:
        return
    discord_id = str(message.author.id)
    ensure_platform_identity("discord", discord_id, message.author.name, message.author.display_name)
    owner_id = canonical_user_id(discord_id)
    if owner_id is None:
        await message.reply("Use `/pair` in a private Discord context, then confirm the code in GreyAI’s private Telegram chat.", mention_author=False)
        return
    user = get_user(owner_id)
    if not user or not is_allowed_user(owner_id):
        await message.reply("Your paired GreyAI account is not currently permitted to use the service.", mention_author=False)
        return

    chat_id = discord_conversation_id(message)
    record_contact_log(owner_id, chat_id, "discord_message", text, int(message.id), getattr(message.reference, "message_id", None), metadata={"source": "discord", "guild_id": str(message.guild.id) if message.guild else None})
    reply_context = None
    referenced = getattr(message.reference, "resolved", None)
    if referenced is not None and getattr(referenced, "content", ""):
        reply_context = {"message_id": getattr(referenced, "id", None), "text": _safe_text(referenced.content, 4000), "author": str(getattr(referenced.author, "display_name", "Discord user")), "is_bot": bool(getattr(referenced.author, "bot", False)), "source": "discord_reply"}

    micro_reply = grey.private_chat_micro_reply(text) if message.guild is None else None
    if micro_reply:
        sent = await message.reply(_safe_text(micro_reply), mention_author=False)
        grey.remember_chat_turn(chat_id, text, micro_reply, owner_id, int(message.id), reply_context.get("message_id") if reply_context else None, assistant_message_id=int(sent.id))
        return

    status = await message.reply("GreyAI is thinking…", mention_author=False)
    try:
        history = grey.load_chat_history(owner_id, chat_id)
        plan = await grey.parse_natural_language_intent(text, chat_history=history, private_chat=message.guild is None, user_id=owner_id, reply_context=reply_context, native_context=grey.build_native_grey_context(owner_id, chat_id, "interpreter", request_text=text, chat_history=history, reply_context=reply_context, chat_type="private" if message.guild is None else "guild"))
        route = grey.decide_message_route(text, plan, grey.classify_message_route(text), reply_context)
        if route == "chat" or not plan:
            reply = await grey.generate_chat_reply(chat_id, text, private_chat=message.guild is None, owner_user_id=owner_id, reply_context=reply_context)
            await status.edit(content=_safe_text(reply))
            grey.remember_chat_turn(chat_id, text, reply, owner_id, int(message.id), reply_context.get("message_id") if reply_context else None, assistant_message_id=int(status.id))
            return
        if plan.get("mode") != "check":
            await status.edit(content="This Discord adapter slice currently supports paired chat and read-only web checks. The remaining GreyAI modes are being connected to the same shared service boundary.")
            return
        await _run_check(message, status, owner_id, chat_id, text, plan)
    except grey.TextProviderUnavailable:
        await status.edit(content="GreyAI’s language providers are temporarily unavailable. No browser action was executed.")
    except grey.QueueRejected:
        await status.edit(content="GreyAI is at capacity. Your request was not admitted; please try again shortly.")
    except grey.QueueUnavailable:
        await status.edit(content="GreyAI browser work is temporarily paused. No browser action was executed.")
    except asyncio.TimeoutError:
        await status.edit(content="The browser check timed out. No unsafe fallback was attempted.")
    except Exception:
        grey.logger.exception("discord_request_failed")
        await status.edit(content="GreyAI could not complete that request. No unsafe action was executed.")


async def _deliver_check_result(message: discord.Message, status: Any, result: dict[str, Any]) -> None:
    """Deliver check output privately when the originating context is a guild."""
    formatted = _format_result(result)
    screenshot = result.get("screenshot")
    screenshot_path = Path(screenshot) if screenshot else None
    try:
        if message.guild is not None:
            dm_kwargs: dict[str, Any] = {"content": formatted}
            if screenshot_path and screenshot_path.exists():
                dm_kwargs["file"] = discord.File(str(screenshot_path), filename="greyai-result.png")
            await message.author.send(**dm_kwargs)
            await status.edit(content="The check completed. I sent the result to you in a private DM.")
            return

        await status.edit(content=formatted)
        if screenshot_path and screenshot_path.exists():
            await message.channel.send(file=discord.File(str(screenshot_path), filename="greyai-result.png"), reference=message)
    finally:
        if screenshot_path:
            screenshot_path.unlink(missing_ok=True)


async def _run_check(message: discord.Message, status: discord.Message, owner_id: int, chat_id: int, text: str, plan: dict[str, Any]) -> None:
    allowed, used, limit = grey.consume_quota(owner_id)
    if not allowed:
        await status.edit(content=f"Your GreyAI quota is exhausted ({used}/{limit}).")
        return
    url = str(plan.get("url") or "").strip()
    candidates = grey.source_candidates_for_request(text, url, user_id=owner_id) if url else []
    candidates = list(dict.fromkeys([url, *candidates]))
    if not candidates:
        await status.edit(content="I could not identify an approved web source for that request.")
        return
    operation_id = uuid.uuid4().hex[:12]
    grey.create_operation(operation_id, owner_id, chat_id, "discord_check", url)
    status_facade = DiscordStatusMessage(_InteractionMessageShim(status))
    result = await grey.run_browser_request(operation_id, owner_id, chat_id, "discord_check", lambda: grey.run_browser_task_with_source_fallback(candidates, plan.get("actions", []), owner_id, operation_id, status_msg=status_facade, native_context=grey.build_native_grey_context(owner_id, chat_id, "agent", request_text=text, operation_id=operation_id), screenshot_requested=bool(plan.get("screenshot_requested"))), status_msg=status_facade)
    await _deliver_check_result(message, status, result)
    grey.update_operation(operation_id, "succeeded")


class _InteractionMessageShim:
    def __init__(self, message: discord.Message):
        self.message = message

    async def edit_original_response(self, content: str, view: discord.ui.View | None = None) -> None:
        await self.message.edit(content=content, view=view)


class _InteractionResponseShim:
    def __init__(self, interaction: discord.Interaction):
        self.interaction = interaction

    async def edit_original_response(self, content: str, view: discord.ui.View | None = None) -> None:
        await self.interaction.edit_original_response(content=content, view=view)


async def _authenticate_interaction(interaction: discord.Interaction) -> int | None:
    if not guild_is_enabled(interaction.guild):
        await interaction.response.send_message("GreyAI is not enabled in this server. An administrator must add its server ID to the GreyAI guild allowlist.", ephemeral=True)
        return None
    ensure_platform_identity("discord", str(interaction.user.id), interaction.user.name, interaction.user.display_name)
    owner_id = canonical_user_id(interaction.user.id)
    if owner_id is None:
        await interaction.response.send_message("Use `/pair` in a private Discord DM, then confirm the code in GreyAI’s private Telegram chat.", ephemeral=True)
        return None
    if not get_user(owner_id) or not is_allowed_user(owner_id):
        await interaction.response.send_message("Your paired GreyAI account is not currently permitted to use the service.", ephemeral=True)
        return None
    return owner_id


async def _run_interaction_check(interaction: discord.Interaction, owner_id: int, text: str, plan: dict[str, Any]) -> None:
    allowed, used, limit = grey.consume_quota(owner_id)
    if not allowed:
        await interaction.edit_original_response(content=f"Your GreyAI quota is exhausted ({used}/{limit}).")
        return
    url = str(plan.get("url") or "").strip()
    chat_id = int(interaction.channel_id or interaction.user.id)
    candidates = grey.source_candidates_for_request(text, url, user_id=owner_id) if url else []
    candidates = list(dict.fromkeys([url, *candidates]))
    if not candidates:
        await interaction.edit_original_response(content="I could not identify an approved web source for that request.")
        return
    operation_id = uuid.uuid4().hex[:12]
    grey.create_operation(operation_id, owner_id, chat_id, "discord_check", url)
    status_facade = DiscordStatusMessage(_InteractionResponseShim(interaction))
    result = await grey.run_browser_request(operation_id, owner_id, chat_id, "discord_check", lambda: grey.run_browser_task_with_source_fallback(candidates, plan.get("actions", []), owner_id, operation_id, status_msg=status_facade, native_context=grey.build_native_grey_context(owner_id, chat_id, "agent", request_text=text, operation_id=operation_id), screenshot_requested=bool(plan.get("screenshot_requested"))), status_msg=status_facade)
    await interaction.edit_original_response(content=_format_result(result))
    screenshot = result.get("screenshot")
    if screenshot and Path(screenshot).exists():
        try:
            await interaction.followup.send(file=discord.File(screenshot, filename="greyai-result.png"), ephemeral=interaction.guild is not None)
        finally:
            Path(screenshot).unlink(missing_ok=True)
    grey.update_operation(operation_id, "succeeded")


async def handle_discord_interaction(interaction: discord.Interaction, text: str) -> None:
    owner_id = await _authenticate_interaction(interaction)
    if owner_id is None:
        return
    text = _safe_text(text, 4000)
    if not text:
        await interaction.response.send_message("Tell GreyAI what you want to ask or check.", ephemeral=True)
        return
    chat_id = int(interaction.channel_id or interaction.user.id)
    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True, ephemeral=interaction.guild is not None)
    try:
        history = grey.load_chat_history(owner_id, chat_id)
        native_context = grey.build_native_grey_context(owner_id, chat_id, "interpreter", request_text=text, chat_history=history, chat_type="private" if interaction.guild is None else "guild")
        plan = await grey.parse_natural_language_intent(text, chat_history=history, private_chat=interaction.guild is None, user_id=owner_id, native_context=native_context)
        route = grey.decide_message_route(text, plan, grey.classify_message_route(text), None)
        if route == "chat" or not plan:
            reply = await grey.generate_chat_reply(chat_id, text, private_chat=interaction.guild is None, owner_user_id=owner_id)
            await interaction.edit_original_response(content=_safe_text(reply))
            grey.remember_chat_turn(chat_id, text, reply, owner_id, None, assistant_message_id=None)
            return
        if plan.get("mode") == "check":
            await _run_interaction_check(interaction, owner_id, text, plan)
            return
        await interaction.edit_original_response(content="That GreyAI mode is not yet exposed through this Discord interaction. Use a normal Discord message for the same request while the remaining platform adapters are connected.")
    except grey.TextProviderUnavailable:
        await interaction.edit_original_response(content="GreyAI’s language providers are temporarily unavailable. No browser action was executed.")
    except grey.QueueRejected:
        await interaction.edit_original_response(content="GreyAI is at capacity. Your request was not admitted; please try again shortly.")
    except grey.QueueUnavailable:
        await interaction.edit_original_response(content="GreyAI browser work is temporarily paused. No browser action was executed.")
    except asyncio.TimeoutError:
        await interaction.edit_original_response(content="The browser check timed out. No unsafe fallback was attempted.")
    except Exception:
        grey.logger.exception("discord_interaction_failed")
        await interaction.edit_original_response(content="GreyAI could not complete that request. No unsafe action was executed.")


def _row_value(row: Any, key: str, default: Any = "") -> Any:
    try:
        if isinstance(row, dict):
            return row.get(key, default)
        keys = row.keys() if hasattr(row, "keys") else ()
        return row[key] if key in keys else default
    except (KeyError, TypeError, IndexError):
        return default


def _account_summary(owner_id: int) -> str:
    user = get_user(owner_id)
    if user is None:
        return "**GreyAI account**\n\nYour paired GreyAI account could not be found."
    plan = str(_row_value(user, "plan", "free") or "free").upper()
    role = str(_row_value(user, "role", "user") or "user").upper()
    status = str(_row_value(user, "status", "active") or "active").upper()
    return f"**GreyAI account**\n\n**Plan:** {plan}\n**Role:** {role}\n**Status:** {status}\n\nPlans and permissions remain controlled by your canonical Telegram GreyAI account."


def _sessions_summary(owner_id: int) -> str:
    sessions = list(grey.list_user_sessions(owner_id))
    if not sessions:
        return "**Saved GreyAI sessions**\n\nNo encrypted browser sessions are saved for this account."
    names = "\n".join(f"• `{_safe_text(name, 120)}`" for name in sessions[:10])
    suffix = "\nOnly the first 10 sessions are shown here." if len(sessions) > 10 else ""
    return f"**Saved GreyAI sessions**\n\n{names}{suffix}\n\nSession contents and cookies are never displayed in Discord."


class DiscordSessionsView(discord.ui.View):
    def __init__(self, owner_id: int, sessions: list[str] | None = None):
        super().__init__(timeout=900)
        self.owner_id = int(owner_id)
        for session_name in list(sessions if sessions is not None else grey.list_user_sessions(self.owner_id))[:10]:
            button = discord.ui.Button(label=f"Delete {str(session_name)[:70]}", style=discord.ButtonStyle.danger)

            async def delete_session(interaction: discord.Interaction, name: str = str(session_name)) -> None:
                if int(interaction.user.id) != self.owner_id:
                    await interaction.response.send_message("Only the paired account owner can delete these sessions.", ephemeral=True)
                    return
                grey.delete_user_session(self.owner_id, name)
                await interaction.response.edit_message(content=_sessions_summary(self.owner_id), view=DiscordSessionsView(self.owner_id))

            button.callback = delete_session
            self.add_item(button)


def _settings_summary(owner_id: int) -> str:
    settings = grey.get_user_settings(owner_id)
    sessions = list(grey.list_user_sessions(owner_id))
    active_handoffs = sum(1 for record in grey.manual_challenges.values() if int(record.get("user_id", -1)) == int(owner_id))
    persistent = "ON" if settings.get("persistent_login_enabled") else "OFF"
    challenge = "ON" if settings.get("challenge_handoff_enabled", True) else "OFF"
    return (
        "**GreyAI settings**\n\n"
        f"**Persistent login + automatic session save:** {persistent}\n"
        "These protections are paired and use GreyAI’s encrypted session store.\n\n"
        f"**Manual challenge handoff:** {challenge}\n"
        "When enabled, GreyAI pauses for you to complete the site’s own challenge; it never solves or bypasses it.\n\n"
        f"**Saved encrypted sessions:** {len(sessions)}\n"
        f"**Active manual handoffs:** {active_handoffs}"
    )


class DiscordSettingsView(discord.ui.View):
    def __init__(self, owner_id: int):
        super().__init__(timeout=900)
        self.owner_id = int(owner_id)

    async def _is_owner(self, interaction: discord.Interaction) -> bool:
        if int(interaction.user.id) == self.owner_id:
            return True
        await interaction.response.send_message("Only the paired account owner can use these settings controls.", ephemeral=True)
        return False

    async def _refresh(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(content=_settings_summary(self.owner_id), view=self)

    @discord.ui.button(label="Toggle persistent login + auto-save", style=discord.ButtonStyle.secondary)
    async def toggle_persistent(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if await self._is_owner(interaction):
            grey.toggle_persistent_login_setting(self.owner_id)
            await self._refresh(interaction)

    @discord.ui.button(label="Toggle challenge handoff", style=discord.ButtonStyle.secondary)
    async def toggle_challenge(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if await self._is_owner(interaction):
            grey.toggle_challenge_handoff_setting(self.owner_id)
            await self._refresh(interaction)

    @discord.ui.button(label="Cancel active handoffs", style=discord.ButtonStyle.danger)
    async def cancel_handoffs(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if not await self._is_owner(interaction):
            return
        tokens = [token for token, record in grey.manual_challenges.items() if int(record.get("user_id", -1)) == self.owner_id]
        for token in tokens:
            await grey.cancel_manual_challenge(token)
        await self._refresh(interaction)

    @discord.ui.button(label="Saved sessions", style=discord.ButtonStyle.primary)
    async def saved_sessions(self, interaction: discord.Interaction, _: discord.ui.Button) -> None:
        if await self._is_owner(interaction):
            await interaction.response.edit_message(content=_sessions_summary(self.owner_id), view=DiscordSessionsView(self.owner_id))


def create_discord_bot() -> commands.Bot:
    intents = discord.Intents.default()
    intents.message_content = True
    client = commands.Bot(command_prefix=commands.when_mentioned, intents=intents)

    @client.tree.command(name="pair", description="Pair this Discord account with your GreyAI Telegram account")
    async def pair_command(interaction: discord.Interaction) -> None:
        await start_pairing(interaction)

    @client.tree.command(name="unpair", description="Revoke the current Telegram↔Discord pairing")
    async def unpair_command(interaction: discord.Interaction) -> None:
        await unpair_account(interaction)

    @client.tree.command(name="help", description="Show GreyAI Discord capabilities")
    async def help_command(interaction: discord.Interaction) -> None:
        await interaction.response.send_message("GreyAI supports paired chat, read-only web checks, and more shared capabilities as they are enabled. Use `/pair` to connect your Telegram account.", ephemeral=True)

    @client.tree.command(name="settings", description="Manage GreyAI account settings with private buttons")
    async def settings_command(interaction: discord.Interaction) -> None:
        owner_id = await _authenticate_interaction(interaction)
        if owner_id is not None:
            await interaction.response.send_message(_settings_summary(owner_id), ephemeral=True, view=DiscordSettingsView(owner_id))

    @client.tree.command(name="grey", description="Show your paired GreyAI account state")
    async def grey_command(interaction: discord.Interaction) -> None:
        owner_id = await _authenticate_interaction(interaction)
        if owner_id is not None:
            await interaction.response.send_message(_account_summary(owner_id), ephemeral=True)

    @client.tree.command(name="sessions", description="Manage your encrypted GreyAI browser sessions")
    async def sessions_command(interaction: discord.Interaction) -> None:
        owner_id = await _authenticate_interaction(interaction)
        if owner_id is not None:
            await interaction.response.send_message(_sessions_summary(owner_id), ephemeral=True, view=DiscordSessionsView(owner_id))

    @client.tree.command(name="status", description="Show GreyAI service health")
    async def status_command(interaction: discord.Interaction) -> None:
        owner_id = await _authenticate_interaction(interaction)
        if owner_id is not None:
            await interaction.response.send_message(_safe_text(grey.build_health_report()), ephemeral=True)

    @client.tree.command(name="ask", description="Ask GreyAI a question or start an authorized task")
    @app_commands.describe(prompt="Your natural-language question or task")
    async def ask_command(interaction: discord.Interaction, prompt: str) -> None:
        await handle_discord_interaction(interaction, prompt)

    @client.tree.command(name="check", description="Run an authorized read-only web check")
    @app_commands.describe(url="Approved HTTPS URL", extract="What GreyAI should extract")
    async def check_command(interaction: discord.Interaction, url: str, extract: str = "Summarize the important facts on this page.") -> None:
        await handle_discord_interaction(interaction, f"Check {url} and {extract}")

    @client.event
    async def on_ready() -> None:
        if not getattr(client, "_grey_synced", False):
            await client.tree.sync()
            client._grey_synced = True
        grey.logger.info("GreyAI Discord adapter ready as %s", client.user)

    @client.event
    async def on_message(message: discord.Message) -> None:
        await handle_discord_message(message)

    return client


async def run_discord_bot() -> None:
    if not DISCORD_ENABLED or not DISCORD_BOT_TOKEN:
        grey.logger.info("Discord adapter disabled; set DISCORD_ENABLED=true and DISCORD_BOT_TOKEN to enable it.")
        return
    client = create_discord_bot()
    try:
        await client.start(DISCORD_BOT_TOKEN)
    finally:
        await client.close()

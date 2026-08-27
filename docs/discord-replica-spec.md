# GreyAI Discord Replica and Telegram Pairing

## Status

Draft for user review before implementation. This specification extends the existing `Playwright-tg` application; it does not replace the Telegram bot or create a separate disconnected demo.

## Assumptions I am making

1. Telegram remains the source of the existing GreyAI account, plan, role, and moderation model.
2. Discord is an additional platform adapter that reuses GreyAI’s shared routing, browser, queue, persistence, billing, moderation, and monitoring services.
3. Discord and Telegram will run in the same deployment process or coordinated worker group, but Discord will have its own bot token and platform-specific event adapter.
4. A paired account means one Telegram user explicitly authorizes one Discord user through a short-lived, single-use pairing challenge. A Discord user cannot claim a Telegram account by supplying an ID or username.
5. The existing SQLite control plane remains the initial persistence layer. Pairing data will be added through an additive migration and will not change the meaning of existing Telegram IDs.
6. The existing aiohttp dashboard is the “custom webpage” to update. It will receive cross-platform identity and pairing status surfaces; the generated landing-page template will also be revised to present GreyAI as a Telegram-and-Discord product.
7. Live Discord validation requires a Discord application token and a test server or DM. Until those are supplied, implementation and local integration tests can proceed without connecting to Discord.

## Objective

Build a production-grade Discord replica of GreyAI that supports natural-language chat and Agentic requests, browser tasks, schedules, watchers, downloads, plans, developer access, administration, monitoring, and manual challenge handoffs through Discord-native interactions. Add a secure account-pairing flow so an authorized user can use the same GreyAI identity, plan, role, and durable context across Telegram and Discord without exposing credentials or trusting user-supplied identity claims.

The Discord surface should feel native rather than Telegram-shaped. It should use slash commands for discoverability, normal message handling for natural language, buttons and modals for confirmation/settings/pairing, ephemeral responses for sensitive data, threads or DMs for long-running task updates, and Discord file attachments for permitted artifacts.

## Capability contract

The platform-neutral service layer must expose typed operations for:

| Capability | Required behavior | Discord presentation |
|---|---|---|
| Chat | Use GreyAI’s existing context, micro-replies, provider failover, and durable history. | Message reply or thread reply. |
| Agentic task | Parse and validate a task before browser execution; preserve queue, plan, operation, and result semantics. | Deferred response followed by progress edits and final result. |
| Manual handoff | Keep the live page in the existing in-memory operation registry; issue a private, expiring URL; never solve CAPTCHA/MFA. | Ephemeral button or DM containing the private handoff link. |
| Watchers and schedules | Reuse durable watcher/schedule records and owner scoping. | Slash-command setup plus private confirmation and status messages. |
| Downloads | Reuse bounded retrieval, validation, cleanup, and plan limits. | Discord attachment only when size and policy permit; otherwise a safe result message. |
| Roles and plans | Resolve authorization from the paired canonical GreyAI account. | Discord permissions may restrict server use, but cannot elevate GreyAI role or plan. |
| Admin/developer features | Reuse server-authoritative checks and audit records. | Admin/developer commands only in approved owner DM or configured admin channel. |
| Monitoring | Reuse operations, queue, provider, maintenance, and audit data. | Status commands, progress updates, and dashboard cross-platform views. |

## Pairing protocol

The pairing flow must be explicit, short-lived, single-use, and server-authoritative. The recommended flow is:

1. A user starts `/pair` in Discord. GreyAI creates a cryptographically random pairing nonce, stores only a hash plus expiry and attempt metadata, and returns a short code or private link that contains no Telegram identity.
2. The user opens GreyAI’s Telegram bot and starts `/pair <code>` in a private chat. The Telegram handler verifies the code, the Telegram account, expiry, attempt limit, and unused state.
3. Telegram confirms the pairing to the Telegram user. Discord receives a confirmation message only after the server commits the link.
4. The link is stored as a unique Discord-user-to-Telegram-user relationship with timestamps, source platform, and revocation state. Re-pairing requires explicit unlink/replacement behavior.
5. `/unpair` requires confirmation and revokes the relationship without deleting either platform’s account history.

Pairing must never accept a raw Telegram ID as proof of identity. Codes must expire quickly, be rate-limited, be invalid after one successful use, and produce generic failure messages that do not reveal whether a code or account exists. Pairing, unlinking, failed attempts, and permission changes must be auditable without logging codes or tokens.

## Identity and data model

Additive control-plane structures should preserve the existing Telegram-centric schema while introducing platform-neutral linkage:

```text
platform_identities
- identity_id
- platform: telegram | discord
- platform_user_id
- username/display_name (non-authoritative metadata)
- canonical_telegram_user_id (nullable until paired)
- status
- created_at / last_seen_at / updated_at

account_pairing_challenges
- challenge_id
- code_hash
- requested_platform
- requested_platform_user_id
- expires_at
- attempt_count
- consumed_at
- created_at

account_pairings
- pairing_id
- telegram_user_id
- discord_user_id
- status: active | revoked
- created_at / last_confirmed_at / revoked_at
```

The first implementation may use a compatibility layer that maps a Discord request to the paired Telegram user ID when calling existing Telegram-keyed service functions. New code must not silently use a Discord Snowflake as a Telegram account ID, because that could create an unintended second account and bypass existing limits or permissions.

Conversation and contact records should gain additive platform metadata and platform message IDs. Existing Telegram columns remain intact for backward compatibility. Shared history must be scoped to the canonical GreyAI account plus a conversation scope, not merely to a platform user ID.

## Discord adapter contract

Create a separate adapter module, preferably `discord_bot.py`, with no duplicated browser or policy logic. The adapter should:

- Validate Discord event payloads at the boundary.
- Resolve the authenticated Discord principal and canonical paired account.
- Call shared service functions for route classification, chat, tasks, schedules, watchers, downloads, handoffs, and administration.
- Defer Discord interactions before long-running work and keep progress updates bounded.
- Use stable structured error categories such as `NOT_PAIRED`, `PERMISSION_DENIED`, `RATE_LIMITED`, `NEEDS_CONFIRMATION`, `NOT_FOUND`, `TRANSIENT`, and `FAILED`.
- Avoid sending private tokens, raw database rows, credentials, cookies, browser session material, or user histories into public channels.
- Use idempotency keys for side-effecting Discord commands such as pairing, unpairing, scheduling, campaign creation, and moderation actions.

Initial Discord command set:

```text
/grey                     Show GreyAI capabilities and current account state
/pair                     Start Telegram↔Discord pairing
/unpair                   Revoke the current pairing after confirmation
/settings                 Open button/modal settings
/help                    Show plan-aware Discord help
/status                  Show service and current operation status
/upgrade                 Show available plans and benefits
/watch                   Create or manage a watcher
/schedule                Create or manage a schedule
/sessions                List or delete permitted browser sessions
/developer               Open developer/API tools when authorized
/admin                   Open administrator tools when authorized
```

Natural-language messages must remain supported where the Discord server/channel policy allows them. In public servers, GreyAI must require an explicit server enablement and channel scope; in DMs, normal account authorization and pairing checks apply.

## Permissions and server policy

Discord server membership is not equivalent to a GreyAI role. The adapter must separately enforce:

- Discord permission to use the bot in that server/channel.
- GreyAI account status, plan, and role.
- Whether the server/channel has been explicitly enabled.
- Whether the requested capability is allowed in that context.
- Whether a response must be private, ephemeral, or sent in a DM.

Public channels must never receive pairing codes, dashboard bearer links, API secrets, saved-session details, private history, or sensitive downloads. Destructive administrator actions require explicit confirmation and an audit record.

## Custom webpage update

The existing dashboard will be updated with a cross-platform “Connections” or “Pairing” area that shows:

- Paired Telegram and Discord display metadata, without exposing tokens.
- Pairing status, created time, last confirmed time, and revoke control.
- A secure one-time pairing initiation action.
- Platform-aware operations and activity summaries.
- Clear private-link and data-retention guidance.

The generated landing-page template will be revised to describe GreyAI as a Telegram-and-Discord AI operations assistant and include a safe “Connect Telegram” / “Connect Discord” call to action. No credentials will be embedded in generated pages.

## Commands and verification

Existing repository commands remain the baseline:

```bash
cd /home/ubuntu/playwright-tg
.venv/bin/pytest -q
python -m py_compile bot.py control_plane.py dashboard.py discord_bot.py
```

Additional checks for the adapter will be added only if needed:

```bash
.venv/bin/pytest -q test_discord.py test_pairing.py
ruff check bot.py control_plane.py dashboard.py discord_bot.py test_discord.py test_pairing.py
```

A live Discord smoke test will be performed only after the user supplies a Discord bot token and authorizes a test server or DM. It will not use the production Telegram account without explicit pairing confirmation.

## Project structure

```text
bot.py                 Existing Telegram adapter and shared runtime during migration
control_plane.py       Shared SQLite persistence, authorization, plans, audit, and pairing primitives
discord_bot.py         Discord adapter, events, slash commands, buttons, modals, and response mapping
discord_contract.py    Typed Discord-facing command/result/error contracts if needed
dashboard.py           Existing dashboard plus cross-platform pairing/status UI
starter_templates.py   Telegram-and-Discord product landing-page template

 test_discord.py       Discord adapter unit/integration tests with fake Discord objects
 test_pairing.py       Pairing lifecycle, expiry, replay, rate-limit, unlink, and ownership tests
 test_bot.py           Existing Telegram/shared-service regression suite
 test_dashboard.py     Dashboard and pairing API/UI regressions
 test_platform.py      Existing platform persistence and authorization tests

docs/discord-replica-spec.md
```

## Code style

Shared services should accept an explicit canonical account and platform context rather than infer identity from an arbitrary integer:

```python
request = PlatformRequest(
    platform="discord",
    platform_user_id=discord_user_id,
    canonical_user_id=paired_telegram_user_id,
    conversation_id=f"discord:{guild_id}:{channel_id}",
    message_id=str(discord_message_id),
    text=request_text,
)
result = await grey_service.handle(request)
await discord_responder.send(result)
```

The adapter must keep platform I/O at the edge. Shared results should be structured and platform-neutral:

```python
AgentResult(
    status="completed",
    operation_id=operation_id,
    text=summary,
    attachments=attachments,
    private_only=False,
)
```

## Testing strategy

Tests must follow the existing pytest setup and use real shared logic where possible. New coverage must include:

- Pairing happy path from Discord challenge creation through Telegram confirmation.
- Expired, replayed, guessed, rate-limited, and cross-account pairing attempts.
- Unpairing and re-pairing behavior.
- Paired Discord requests inheriting the canonical Telegram role, plan, quota, and history.
- Unpaired Discord users receiving a safe pairing prompt and no task execution.
- DM versus public-server/channel policy enforcement.
- Natural-language chat and Agentic routing through the same shared path.
- Deferred responses and progress updates for long-running tasks.
- Manual handoff delivery as a private Discord response with the existing expiring URL.
- Sensitive output redaction and attachment size/policy enforcement.
- Admin/developer permission boundaries and idempotent mutations.
- Dashboard pairing status, revoke behavior, and CSRF protection.
- Existing Telegram regression suite remaining green.

## Boundaries

### Always do

- Run tests before commits and after every behavior change.
- Keep production secrets out of source, logs, generated archives, Discord messages, and dashboard HTML.
- Validate Discord event data and third-party responses at the boundary.
- Resolve permissions server-side using the canonical GreyAI account.
- Make pairing codes single-use, expiring, hashed at rest, and rate-limited.
- Use private or ephemeral Discord delivery for sensitive information.
- Keep CAPTCHA/MFA handling user-controlled and never bypass security checks.

### Ask first

- Adding a new runtime dependency such as `discord.py`.
- Changing Fly process topology or CI/deployment configuration.
- Introducing a schema migration that alters existing columns.
- Connecting a live Discord bot token or inviting the bot to a real server.
- Enabling billing, public-server operation, or broad download/API scopes for external users.

### Never do

- Never treat a Discord user ID as proof of a Telegram identity.
- Never expose production Telegram/Gemini/Fly/GitHub secrets to a pilot customer or Discord user.
- Never place pairing codes, bearer URLs, API keys, cookies, or saved-session details in public channels.
- Never grant GreyAI roles or plans from Discord display names, model output, or user-provided claims.
- Never copy live browser pages, Playwright handles, or session cookies into SQLite for cross-process sharing.
- Never solve or bypass CAPTCHA, MFA, anti-bot, paywall, DRM, or access-control challenges.

## Success criteria

The implementation is complete when:

1. A Discord user can install/use GreyAI in an authorized DM or enabled server context.
2. An unpaired user cannot execute protected GreyAI tasks.
3. A Telegram user can explicitly pair one Discord identity using a single-use expiring challenge.
4. The paired Discord identity inherits the canonical account’s plan, role, quota, moderation status, and durable context without duplicating the account.
5. Replayed, expired, cross-user, and rate-limited pairing attempts are rejected safely and audited.
6. Discord chat, Agentic routing, browser tasks, schedules, watchers, downloads, settings, and relevant admin/developer features reuse shared GreyAI behavior.
7. Manual handoffs are delivered privately with bounded expiry and user-controlled challenge completion.
8. The updated dashboard and landing-page template present Telegram and Discord coherently without secrets.
9. Focused adapter/pairing tests and the full existing suite pass with no disabled regressions.
10. Deployment configuration can run without a Discord token, and live Discord testing is explicitly gated on the user providing that token and a test destination.

## Open questions for approval

1. Should Discord run in the same Fly app as Telegram, or should the code support both same-app and separate-app deployment from the start?
2. Should the first release support Discord DMs only, or DMs plus explicitly enabled servers/channels?
3. Should pairing share the existing durable conversation history by default, or should users choose whether to merge or keep platform-specific histories?
4. Which Discord library and version should be approved for the runtime? The current repository has no Discord dependency.
5. Should the webpage update be limited to the existing authenticated dashboard and generated landing-page template, or should a separate public marketing site be added?
6. What Discord application token and test server/DM may be used for live validation? Do not send the token in chat; it should be added through the deployment secret store.

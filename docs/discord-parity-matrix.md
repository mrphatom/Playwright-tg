# Discord parity matrix

This matrix is the working contract for the Discord counterpart. Telegram remains the canonical implementation and account authority. A Discord command is considered complete only when it preserves the Telegram feature’s authorization, plan gate, quota, audit, confirmation, privacy, and durable-state behavior through a Discord-native response.

| Capability group | Telegram commands / surface | Current Discord state | Required Discord delivery |
|---|---|---|---|
| Account and pairing | `/start`, `/pair`, `/help`, `/grey`, `/unpair` | Partial: pairing, `/grey`, `/help`, `/unpair` exist; `/start` equivalent is not registered | Slash commands, private responses, canonical Telegram owner mapping |
| Personal controls | `/settings`, `/sessions`, `/deletesession`, `/dashboard` | Partial: settings and session summary/delete exist; dashboard link and complete session semantics remain | Buttons/modals where settings are interactive; private URLs only |
| Chat and agent | natural-language messages, `/ask`, `/check`, `/fetch` | Partial: paired chat and read-only checks; no complete fetch/file delivery | Shared request/result service, deferred responses, private sensitive output, attachments |
| Monitoring | `/watch`, `/watchers`, `/stopwatch` | Not implemented | Platform-tagged durable watcher rows, owner/channel delivery adapter, private failure/result routing |
| Schedules | `/schedule`, `/schedules`, `/unschedule` | Not implemented | Platform-tagged durable schedule rows, timezone validation, owner/channel delivery adapter |
| Shared status | `/health`, `/status`, `/maintenance_log` | Partial: `/status` exists; health and maintenance history are not exposed | Ephemeral or DM status views; no hidden admin diagnostics for ordinary users |
| Plans and support | `/upgrade`, `/crypto`, `/terms`, `/support`, `/paysupport`, `/referral` | Not implemented | Read-only plan/support/referral views; Telegram Stars checkout remains Telegram-owned unless separately specified |
| Developer | `/devrequest`, `/devrequests`, `/grantdeveloper`, `/denydeveloper`, `/revokedeveloper`, `/newkey`, `/devkeys`, `/revokekey`, `/developerstats`, `/devevents` | Not implemented | Role-gated ephemeral views, one-time secrets only in private DM, server-side ownership and audit checks |
| Administration | `/admin`, `/admin_user`, `/grantadmin`, `/revokeadmin`, `/ban`, `/unban`, `/banned`, `/analytics` | Not implemented | Administrator-only commands, scoped target checks, confirmation for bulk/destructive operations, audit and notification delivery |
| Reports and appeals | `/report`, `/reports`, `/review`, `/appeal`, `/appeals`, `/resolveappeal`, `/massappeals` | Not implemented | User-private reports/appeals; admin review controls with explicit resolution confirmation |
| Messaging | `/announce`, `/dm`, `/massdm`, `/massrole`, `/massmessage`, `/confirmbulk` | Not implemented | Preview-first, single-use confirmation, bounded recipients, Discord permission checks, audit receipts |
| Maintenance | `/maintenance`, `/maintenance_log`, `/status` | Not implemented beyond read-only status | Admin-only preview/confirmation; scheduled activation and safe notifications |
| Domain and channel policy | `/allowchannel`, `/disallowchannel`, `/allowdomain`, `/disallowdomain`, `/resetdomain`, `/domains`, `/enablegreyai`, `/disablegreyai` | Not implemented | Admin/group-owner gates, explicit guild/channel scope, allowlist and deny precedence |
| Advertising | `/adcreate`, `/confirmad`, `/adlist`, `/cancelad`, `/resumead` | Not implemented | Admin-only preview/confirmation, target permission checks, automatic pause and failure alerts |
| Billing administration | `/stars`, `/starsbalance`, `/withdrawstars` | Not implemented | Telegram Stars remain Telegram-specific; Discord may show redacted status only, never collect wallet or payment secrets |
| Core background services | watcher worker, schedule worker, notification outbox, crash failsafe, queue | Shared runtime exists; Discord delivery is incomplete | Platform-aware delivery routing and restart-safe restoration |

## Completion rule

The adapter must not advertise a command as complete until a focused test covers a successful case, an unauthorized or wrong-scope case, a bounded-input/error case, and any confirmation or privacy boundary. Unsupported or Telegram-only commands must be omitted from user-facing help until their Discord behavior is implemented.

## Current honest boundary

The existing implementation is a real paired Discord surface, not a disconnected demo, but it is not yet full parity. The next implementation slices start with shared platform-aware delivery and the monitoring/schedule contracts because those are the main blockers to safely exposing the remaining background features.

## Rollback

Each parity slice is committed independently. Reverting the slice commit must leave `DISCORD_ENABLED=false` safe and preserve Telegram behavior.

## Source

The inventory was extracted from the authoritative `CommandHandler` registrations and help sections in `bot.py`, plus the current `discord_bot.py` slash-command registry.

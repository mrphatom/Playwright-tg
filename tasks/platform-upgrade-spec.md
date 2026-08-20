# GreyAI Platform Upgrade Specification

## Scope

This change adds administrator announcements and direct messages, affected-user moderation notifications, durable bulk moderation with preview and confirmation, banned/suspicious/top-user/top-referrer/risk views, a developer event bridge, and safer chat-versus-agent routing. Existing slash commands, public-mode authorization, SQLite persistence, quotas, SSRF controls, and developer-key boundaries remain compatible.

## Safety contract

Administrative mutations are deny-by-default and server-side authorized. Single-user messages are length-bounded and delivered through a durable notification outbox. Announcements and bulk actions are preview-first, bounded by a configurable recipient/target maximum, require a short-lived confirmation token, are idempotent by job ID, and record an audit action. Administrators cannot mass-ban or alter administrator accounts. User-visible moderation notifications contain the action, reason/resolution, and appeal/support path but never internal risk evidence, secrets, or other users' data.

## Notification outbox

`user_notifications` stores one durable row per intended recipient with a unique idempotency key, delivery state, attempt count, and safe body. A background worker sends rows through Telegram with bounded exponential backoff. Telegram delivery failures are recorded and do not roll back moderation state.

## Bulk moderation

`admin_bulk_jobs` stores action, target IDs or appeal IDs, preview count, confirmation hash, expiration, status, processed/succeeded/failed counts, and timestamps. Actions are `announce`, `mass_dm`, `mass_ban`, `mass_unban`, and `mass_appeal`. Commands create a preview and return `/confirmbulk <job_id> <token>`; confirmation is required before side effects.

## Analytics

Queries expose bounded summaries for banned users, human-review risk queue, top users by operations, top referrers by referral count, and highest-risk users. Results are paginated/limited and redact message bodies and secrets.

## Developer event bridge

Active developers can create a scoped event cursor/feed for their own integrations. Events are owner-scoped, redacted, cursor-based, rate-limited, and limited to operation completion, watcher alerts, quota degradation, and moderation state changes relevant to the developer's own users/keys. No arbitrary callback URL or cross-tenant event access is introduced in this phase.

## Routing hardening

The route classifier becomes explicit and observable: ordinary conversation stays fast; explicit browser verbs, URLs, schedules, watch/monitor language, and structured management commands enter task mode. A task fallback must never be converted to chat merely because the model is unavailable. Model output is validated against the allowlisted intent schema, and ambiguous destructive/admin requests require an explicit confirmation path.

## Rollback

All schema changes use `CREATE TABLE IF NOT EXISTS` and additive indexes. Runtime behavior can be disabled with feature flags for notifications, bulk actions, and developer events. The release is reverted through the merge commit if regression or safety tests fail.

## Verification

Representative tests must cover normal and boundary notification delivery, failed Telegram delivery, preview-only bulk action, expired/invalid confirmation, administrator-target rejection, banned/suspicious/top analytics, developer event ownership, prompt-injection-resistant routing, ordinary chat latency path, explicit task path, and full regression/security scans.

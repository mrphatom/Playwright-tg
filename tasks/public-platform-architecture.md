# Public Platform Architecture and Threat Model

## Audit findings

The current service is a single Python process using `python-telegram-bot` polling, Playwright Chromium, Gemini, SQLite, and a Fly.io persistent volume. Authorization is currently a process-level `ALLOWED_TELEGRAM_USERS` set. There is no user table, role table, persistent rate-limit ledger, web authentication, dashboard server, payment ledger, payment webhook, moderation case system, or durable job queue. The existing tables are `sessions`, `watchers`, `schedules`, and `audit_logs`.

The browser session data is encrypted with Fernet, but the current fallback key is derived from the Telegram bot token when `SESSION_ENCRYPTION_KEY` is absent. Public release must fail closed when the encryption key is missing instead of deriving one from another secret. The existing allowlist and per-user cooldown are useful boundaries but are not sufficient for multi-user public operation, durable quotas, abuse controls, or administrator workflows.

## Target trust boundaries

1. Telegram updates and user messages are untrusted input.
2. Gemini output is untrusted data and must never directly authorize tools, SQL, shell commands, payments, or administrative actions.
3. Browser-fetched pages are untrusted prompt-injection content.
4. Payment callbacks are untrusted until provider authenticity, invoice identity, amount, currency, and user ownership are verified.
5. Dashboard requests and websocket subscriptions are untrusted until authenticated and authorized server-side.
6. Administrator actions are privileged and require explicit role checks, resource ownership checks, audit records, and anti-CSRF protection for web mutations.

## Assets to protect

Credentials and encrypted browser sessions, Telegram identity mappings, payment and entitlement records, moderation case data, admin capabilities, execution logs, user privacy, Gemini and Telegram credentials, and service availability.

## Roles and lifecycle

Users default to `user`. Administrators are configured by a server-side environment variable containing Telegram IDs or a separate admin table; the identifier must never be exposed in client code. Account states are `active`, `limited`, `suspended`, and `banned`. Suspensions are time-bounded and include a reason, actor, and audit record. A report or AI risk signal must not automatically ban a user.

## Cautious moderation policy

Risk scoring is advisory. The system should record evidence categories, confidence, and model/version, then apply graduated actions: no action, ask for clarification, temporary feature cooldown, human-review queue, or time-bounded limitation. Automatic permanent bans are prohibited. A user can open an appeal ticket, see its status, and add context. An administrator must review high-impact actions.

## Billing and quotas

For digital services sold inside Telegram, Telegram's official payment guidance requires Telegram Stars (`XTR`), a pre-checkout response within the provider deadline, verification of `successful_payment` before granting access, durable storage of `telegram_payment_charge_id`, and support/refund paths. Crypto cannot replace Stars for digital goods inside Telegram clients; a crypto rail may be offered only as a separately reviewed external web checkout subject to legal, provider, and platform constraints. The implementation must use a provider adapter and never treat a client message as proof of payment.

Free users receive server-enforced quotas, not client-side limits. Entitlements are computed from a durable ledger with idempotent payment and refund processing. A payment can be applied once by provider charge ID and invoice payload ID.

## Dashboard architecture

The dashboard should be served by an authenticated web application on the same Fly app or a separately deployed service. It must use HTTPS, secure HTTP-only same-site cookies, CSRF protection, strict security headers, bounded CORS, server-side authorization, and websocket subscription checks. Users see only their own sessions, schedules, reports, quotas, and execution events. Administrators see aggregate health and privileged operational views, with sensitive session contents and credentials permanently excluded.

## Enterprise foundations

Add durable operations with IDs, status transitions, timestamps, attempt counts, bounded retries, idempotency keys, and a dead-letter or failed state. Add structured audit events with actor, resource, operation ID, reason, and redacted metadata. Add runtime metrics with bounded labels and a health endpoint. Add backups and migration versioning before public launch.

## Release gates

Do not publish publicly until the service has: a required encryption key, role and resource authorization tests, login and webhook rate limits, payment idempotency tests, admin action audit tests, SSRF and domain-validation tests, secret scanning, dependency audit, backup/restore verification, dashboard security-header checks, and a rollback procedure.

## Official payment references

- Telegram Stars Bot Payments: https://core.telegram.org/bots/payments-stars
- Telegram Bot Payments: https://core.telegram.org/bots/payments
- Telegram Star subscriptions: https://core.telegram.org/api/subscriptions

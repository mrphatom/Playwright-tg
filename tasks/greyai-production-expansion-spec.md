# GreyAI Production Expansion Specification

## Objective

Expand GreyAI into a reliable, observable, multi-tenant automation platform across Telegram, Discord, the dashboard, and the developer API. The system must remain operational during partial failures, preserve durable task state, expose clear user controls, and add business/developer capabilities without weakening authorization, privacy, or manual-approval boundaries.

## Current baseline

- Python 3.12, aiohttp dashboard, Telegram long polling, discord.py gateway, Playwright, Gemini failover, Neon PostgreSQL with SQLite compatibility.
- Existing durable operations, request queue, watchers, schedules, maintenance state, runtime snapshots, API keys, dashboard sessions, user roles/plans, and public status routes.
- Existing verification baseline: 399 tests passed on commit `16a59d4`.

## Assumptions

1. Neon PostgreSQL is the production source of truth; SQLite remains supported for local tests and fallback development.
2. Existing Telegram and Discord commands remain backward-compatible.
3. New functionality is introduced behind feature flags until its vertical slice passes tests and live smoke checks.
4. Browser automation remains authorized and standards-compliant: no CAPTCHA bypass, anti-bot evasion, credential exfiltration, or unrestricted side effects.
5. High-impact external actions continue to require explicit user confirmation or an existing approved workflow.
6. The dashboard remains aiohttp-rendered for this implementation phase; a separate React/TypeScript frontend can be introduced later without changing API contracts.

## Product surfaces

### User task control
- Task list with status, ETA, progress timeline, artifacts, sources, and failure reason.
- Pause, resume, cancel, retry, and retry-from-step where the operation supports it.
- Execution plan preview with run, edit, read-only, and ask-before-action modes.
- Persistent state across provider failover, browser restart, handoff, and process restart.

### Research and monitoring
- Evidence/source receipts with URL, title, access time, extracted evidence, and confidence metadata.
- Named workspaces containing instructions, source preferences, sessions, watchers, schedules, and memory scope.
- Smart watcher digests with significance thresholds, before/after changes, suppression, retries, and configurable delivery.

### Operations and reliability
- Admin diagnostics matrix for database, migrations, providers, browser pool, queues, Telegram, Discord, dashboard, watchers, and schedules.
- Deployment readiness gate: additive migrations, schema checks, dashboard bind, gateway startup, browser smoke test, then operational state.
- Incident timeline, public/private status views, recovery progress, snapshots, and post-incident summaries.
- Bounded live activity timeline and structured redacted execution logs.

### Developer platform
- Versioned webhook events with HMAC signatures, replay protection, retries, dead-letter visibility, and secret rotation.
- OpenAPI-like developer contract and console for keys, scopes, request logs, usage, webhooks, and examples.
- Custom tools/connectors with schemas, scope checks, quotas, timeouts, validation, and audit receipts.

### Business platform
- Organization/tenant workspaces with owner/admin/member roles and data isolation.
- Per-tenant plans, quotas, domain policies, tool scopes, audit history, and operational metrics.
- Cost and usage analytics for model calls, browser time, files, tasks, watchers, and API requests.

## Data model principles

- Additive migrations only in the first release: new tables, nullable columns, defaults, indexes after query paths are known.
- Every entity has an opaque ID, owner/tenant scope, timestamps, lifecycle status, and audit linkage where applicable.
- User-visible task state is separate from provider/browser implementation details.
- Secrets, cookies, prompts containing credentials, and private source content are never written to ordinary logs or webhook payloads.

## API contracts

New dashboard/API resources use plural nouns, pagination, structured errors, and idempotency keys where mutations can be retried:

- `GET /api/operations`
- `GET /api/operations/{operation_id}`
- `POST /api/operations/{operation_id}/pause`
- `POST /api/operations/{operation_id}/resume`
- `POST /api/operations/{operation_id}/cancel`
- `POST /api/operations/{operation_id}/retry`
- `GET /api/operations/{operation_id}/events`
- `GET /api/workspaces`
- `POST /api/workspaces`
- `GET /api/status/incidents`
- `GET /api/admin/diagnostics`
- `GET /api/v1/webhooks`
- `POST /api/v1/webhooks`
- `GET /api/v1/tools`
- `POST /api/v1/tools`

All mutation responses use `{ "data": ..., "request_id": "..." }`; errors use `{ "error": { "code": ..., "message": ..., "details": ... }, "request_id": "..." }`.

## Testing strategy

- Unit tests for validation, state transitions, permissions, idempotency, redaction, pagination, and migration behavior.
- Integration tests against SQLite compatibility and a PostgreSQL-like adapter contract.
- Dashboard route tests for auth, CSRF, role boundaries, structured responses, and frontend strings.
- Failure tests for provider outage, browser crash, queue overload, duplicate retries, stale callbacks, and maintenance transitions.
- Full suite before each commit; deployment workflow must run regression tests before Fly deployment.
- Live smoke checks: dashboard HTTP 200, port 8080 health, Telegram startup, Discord gateway readiness, browser pool readiness, and no migration traceback.

## Boundaries

- Always: validate at boundaries, scope every read/write to the authenticated owner or tenant, redact secrets, use idempotency, preserve existing commands, add tests, and keep migrations reversible where practical.
- Ask first: new external paid services, destructive schema changes, billing/withdrawal behavior, broad message publication, or credentials/login side effects.
- Never: bypass CAPTCHAs or anti-bot controls, expose cookies/API keys, execute arbitrary code from model output, silently broaden permissions, or claim a feature is production-ready before tests and live checks pass.

## Success criteria

1. Existing 399-test baseline remains green after each vertical slice.
2. A user can inspect and control a long-running task without losing it after provider/browser restart.
3. Every task has a durable redacted timeline and actionable failure state.
4. Admins can run a bounded diagnostics matrix and see incident/recovery history.
5. Research responses can include source evidence without leaking private data.
6. Developer integrations can register signed webhooks and scoped tools with auditability.
7. Organizations can be isolated and measured without changing existing personal-account behavior.
8. Deployment gates prevent schema/startup regressions from taking the service offline.

## Rollout

Features are released in dependency order behind flags: control plane → diagnostics/deployment → research/workspaces → developer platform → tenant/business platform. Each slice is independently testable, deployable, and revertible.

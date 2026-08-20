# GreyAI Platform Upgrade v27 Specification

## Objective

Extend GreyAI so factual questions that require current web evidence are automatically interpreted into a safe browser check, while ordinary conversation remains fast. Add administrator messaging by role audience, a persistent status and maintenance history, priority-aware overload handling with visible ETAs, and a crash fail-safe that enters hard maintenance mode, preserves a sanitized runtime snapshot, and notifies affected users and administrators.

## Safety and authorization

Every request continues through the existing authorization, account-status, quota, domain-allowlist, SSRF, and action-validation boundaries before Gemini or Playwright execution. Role-targeted messaging is administrator-only and supports only fixed audiences: `all_active`, `users`, `developers`, and `admins`. Audience membership is resolved server-side from current SQLite roles and statuses; callers cannot provide arbitrary recipient lists through the role command. Maintenance mutations are administrator-only. Public status reads expose only sanitized status, reason, timestamps, and an incident/update ID; stack traces, prompts, URLs containing secrets, credentials, and provider keys remain private.

## Natural-language web verification

The route classifier adds a factual-verification signal for questions containing currentness or official-source language such as `officially announced`, `currently`, `latest`, `today`, `did X say`, `is X true`, or `has X retired`. The interpreter emits a validated `check` plan with a discovered canonical HTTPS URL when safe, otherwise a deterministic search/news fallback. The bot returns extracted text and an optional screenshot rather than claiming that chat has no internet access. Ambiguous requests remain chat responses or ask for a source; no arbitrary search engine or unallowlisted domain is invented.

## Persistent maintenance and crash recovery

`maintenance_state` stores the current mode (`operational`, `scheduled`, `degraded`, or `hard_maintenance`), public message, reason, start/end timestamps, incident ID, and sanitized update metadata. `maintenance_events` stores append-only status changes, update messages, reasons, timestamps, and actor IDs for a GitHub-status-style history. `runtime_snapshots` stores a sanitized JSON snapshot of queue depth, active operation counts, provider counters, maintenance state, and recent operation identifiers. A global error handler records the snapshot, switches to hard maintenance, writes an administrator-only diagnostic event, and sends a public-safe notification through the durable outbox. Recovery is explicit through an administrator command and does not automatically claim the underlying cause is fixed.

## Priority queue

`request_queue` stores one row per admitted browser operation with operation ID, user ID, chat ID, kind, priority tier, state, enqueue/start/finish timestamps, estimated wait seconds, and a bounded error code. Paid plans and administrators receive higher priority; free users remain accepted but are queued fairly with an ETA derived from queue position, active slots, and an exponential moving average of completed task duration. Queue admission is bounded. When full, users receive a retry-safe overload response rather than an unbounded memory allocation. Duplicate operation IDs are rejected. Chat-mode replies and maintenance/status reads bypass the browser queue.

The first implementation uses a single in-process dispatcher backed by SQLite state and the existing concurrency limit. The database record makes queue state visible and recoverable across worker restarts; the dispatcher must not claim the same operation twice. A later multi-machine deployment can replace the dispatcher without changing the command contract.

## Role-targeted messaging

The existing preview-first bulk job system is extended with audience selectors. Commands such as `/massrole developers <message>` and `/massrole admins <message>` create a preview with the resolved recipient count, audience, and expiry. `/confirmbulk` remains the only delivery path. Messages use the durable notification outbox with idempotency keys containing job ID and recipient ID. Banned accounts and duplicate recipients are excluded.

## Verification and rollback

Tests cover current factual questions, ambiguous questions, role audience boundaries, maintenance visibility, hard-maintenance admission refusal, queue ordering and ETA bounds, queue saturation, crash snapshot redaction, global error recovery, and notification idempotency. Rollback is the previous main commit; the new tables are additive, and feature flags can disable role messaging, queue admission, maintenance mutations, or crash notifications without removing existing user data.

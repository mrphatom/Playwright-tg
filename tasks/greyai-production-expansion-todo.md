# GreyAI Production Expansion Tasks

## Current delivery status — 2026-09-30

- **Delivered:** durable task lifecycle, dashboard task controls/timelines, approval-aware execution plans, restart/failover continuity, responsive dashboard redesign, and admin diagnostics readiness matrix.
- **In progress:** workspace foundation (owner-scoped persistence and dashboard API); Telegram context/workspace selection and watcher/schedule attachment remain the next increment.
- **Verification baseline:** 408 tests passed before workspace changes; focused workspace tests currently pass.

- [x] **Slice 1 — Task control contract and durable lifecycle**
  - Acceptance: operation detail, pause/resume/cancel/retry state transitions are idempotent, owner-scoped, audited, and compatible with existing queue statuses.
  - Verify: control-plane unit tests, duplicate mutation tests, authorization tests, full pytest suite.
  - Files: `control_plane.py`, `bot.py`, `dashboard.py`, `test_platform.py`, `test_dashboard.py`.

- [x] **Slice 2 — Task Control Center UI and live timeline**
  - Acceptance: dashboard lists tasks with status, ETA, progress events, source/artifact links, and clear retry/cancel controls.
  - Verify: route tests, HTML assertions, websocket/poll fallback test, live dashboard smoke check.
  - Files: `dashboard.py`, `test_dashboard.py`.

- [x] **Slice 3 — Execution plan preview and approval modes**
  - Acceptance: agent plans can be previewed, edited within the allowlisted schema, run read-only, or require per-action confirmation.
  - Verify: malformed-plan, unauthorized-action, confirmation, and read-only tests.
  - Files: `bot.py`, `control_plane.py`, `test_bot.py`.

- [x] **Slice 4 — Restart/failover continuity**
  - Acceptance: provider failover, browser recreation, manual handoff, and process restart preserve operation ID, owner context, plan, and resumable state.
  - Verify: simulated provider 429, browser crash, stale handoff, and resume tests.
  - Files: `bot.py`, `control_plane.py`, tests.

- [ ] **Slice 5 — Diagnostics and deployment readiness gate** *(diagnostics matrix delivered; CI/deployment readiness checks remain)*
  - Acceptance: admin diagnostics returns structured checks; deployment verifies migrations, schema, dashboard, browser, Telegram, and Discord before operational readiness.
  - Verify: local diagnostics fixtures, CI workflow run, Fly health check, redacted logs.
  - Files: `control_plane.py`, `dashboard.py`, `.github/workflows/fly-deploy.yml`, tests.

- [ ] **Slice 6 — Incident timeline and status surfaces**
  - Acceptance: incidents expose start, updates, affected components, recovery probes, resolution, and snapshot references without secrets.
  - Verify: maintenance transition and recovery tests plus public/private route tests.
  - Files: `control_plane.py`, `dashboard.py`, tests.

- [ ] **Slice 7 — Evidence receipts and source-aware research**
  - Acceptance: research results can attach bounded source receipts and evidence while preserving existing output delivery and privacy scopes.
  - Verify: source redaction, conflicting-source, provider-outage, and long-output tests.
  - Files: `bot.py`, `control_plane.py`, `api_contract.py`, tests.

- [x] **Slice 8 — Workspaces and project memory** *(workspace persistence and chat/memory isolation delivered; user-facing workspace controls remain)*
  - Acceptance: users can create isolated workspaces with instructions, memory scope, source preferences, sessions, watchers, and schedules.
  - Verify: ownership, deletion/archival, context isolation, and migration tests.
  - Files: `control_plane.py`, `bot.py`, `dashboard.py`, tests.

- [ ] **Slice 9 — Smart watcher digest**
  - Acceptance: watcher changes support significance thresholds, before/after evidence, digest schedules, suppression, bounded retries, and delivery receipts.
  - Verify: watcher-change, no-change, failure, digest, and restart tests.
  - Files: `control_plane.py`, `bot.py`, tests.

- [ ] **Slice 10 — Developer webhooks and event delivery**
  - Acceptance: scoped webhook subscriptions use signed payloads, timestamps, replay protection, retry/backoff, delivery history, and revocation.
  - Verify: signature, replay, retry, secret rotation, scope, and redaction tests.
  - Files: `control_plane.py`, `dashboard.py`, `api_contract.py`, tests.

- [ ] **Slice 11 — Custom tools/connectors**
  - Acceptance: developers can register validated tools with schemas, scopes, timeouts, quotas, audit records, and disabled-by-default side effects.
  - Verify: schema, authorization, timeout, quota, SSRF, and model-output injection tests.
  - Files: `control_plane.py`, `dashboard.py`, `bot.py`, tests.

- [ ] **Slice 12 — Tenant/business workspaces and analytics**
  - Acceptance: organizations have isolated members, roles, plans, quotas, policies, audit logs, and usage/cost aggregates; existing personal accounts remain compatible.
  - Verify: tenant isolation, role boundaries, aggregate redaction, quota, migration, and dashboard tests.
  - Files: `control_plane.py`, `dashboard.py`, `bot.py`, tests.

- [ ] **Slice 13 — Documentation and rollout**
  - Acceptance: README, API contract, operator runbook, migration notes, and rollback instructions match shipped behavior.
  - Verify: docs consistency checks, full test suite, CI deployment, live smoke tests, and clean git state.
  - Files: `README.md`, `docs/`, `api_contract.py`, workflow files as needed.

# GreyAI Advanced Feature Wave Plan

**Date:** 2026-10-02  
**Status:** Planned for review; no runtime code changes in this planning pass.  
**Baseline:** commit `2f876c0`, branch `fix/neon-percent-placeholders`, full suite `413 passed`, latest Fly deployment successful.

## Objective

Extend GreyAI from a reliable task runner into a durable research, monitoring, developer, and business platform without destabilizing the Telegram/Discord gateways or weakening authorization and approval boundaries.

The next wave is intentionally sequenced around the current gaps: workspace controls are persisted but not user-facing, research outputs lack durable evidence receipts, watchers lack production-grade change intelligence, and the deployment/incident surfaces need to become operationally actionable.

## Assumptions I am making

1. Neon PostgreSQL remains the production source of truth; SQLite compatibility remains mandatory for local tests.
2. Telegram and Discord commands remain backward-compatible; new controls may be added through buttons, dashboard APIs, and natural language.
3. Existing user roles/plans remain the authorization source until tenant/business workspaces are implemented.
4. Browser automation remains compliant: no CAPTCHA bypass, stealth evasion, credential exposure, or unauthorized side effects.
5. External side effects continue to use explicit approval or an already-approved workflow.
6. This wave should be implemented incrementally, one vertical slice at a time, with a full regression suite before each deployment.
7. The dashboard remains aiohttp-rendered in this wave; the API contract must not depend on a future frontend rewrite.

## Prioritized feature waves

### Wave A — Workspace control center and memory UX

**Why first:** The database foundation and workspace-scoped conversation memory already exist. Exposing them now turns an invisible capability into a usable product surface and reduces context leakage risk.

#### User capabilities

- `/workspace` plus natural-language equivalents such as “switch to Client Alpha”.
- Telegram inline keyboard for list, create, select, rename, archive, and view instructions.
- Dashboard workspace selector and workspace detail view.
- Workspace-level instructions, source preferences, memory scope, and active-session summary.
- Clear indicator in task/chat responses showing the active workspace.
- Safe default: a personal workspace or “Private chat” scope when no workspace is selected.
- Workspace-local task, watcher, schedule, source receipt, and conversation filters.

#### Acceptance criteria

- A user can create/select/archive only their own workspaces.
- Selecting a workspace changes subsequent chat/task memory scope without changing another workspace.
- Archived workspaces cannot receive new tasks, watchers, or schedules but remain readable according to retention policy.
- Telegram callbacks are idempotent and do not rely on stale message state.
- Dashboard and Telegram show the same active workspace state.
- Existing chats with no workspace continue to behave exactly as before.

#### Likely files

`bot.py`, `control_plane.py`, `dashboard.py`, `test_bot.py`, `test_platform.py`, `test_dashboard.py`.

---

### Wave B — Smart watcher engine and digest delivery

**Why second:** Watchers are a core reason users return to GreyAI, but repeated polling without significance detection creates noise, quota pressure, and unreliable notifications.

#### User capabilities

- Significance modes: exact change, semantic change, threshold, availability, price, and custom condition.
- Before/after evidence with bounded excerpts and source URL.
- Per-watcher quiet hours, debounce window, failure retry policy, and digest schedule.
- Delivery receipt: detected, suppressed, queued, delivered, failed, or acknowledged.
- Natural-language setup and edits, mapped to the existing validated watcher schema.
- Workspace-scoped watcher list and pause/resume controls.
- Restart-safe watcher checkpoints and deduplication keys.

#### Acceptance criteria

- No-change polls do not generate user messages.
- Repeated identical changes are suppressed within the configured debounce window.
- Provider/browser failures retry with bounded exponential backoff and preserve the last successful checkpoint.
- A watcher restart does not duplicate a notification.
- Every delivered notification has a durable receipt and redacted evidence reference.
- Free/pro/max plan limits are enforced before scheduling work.

#### Likely files

`control_plane.py`, `bot.py`, `test_bot.py`, `test_platform.py`, `docs/intelligent-navigation-spec.md`.

---

### Wave C — Evidence receipts and source-aware research

**Why third:** Research quality and trust improve when answers carry bounded, inspectable evidence rather than only prose or screenshots.

#### User capabilities

- Source receipts containing URL, title, retrieval time, source type, bounded evidence excerpt, and extraction status.
- “Show sources”, “open source”, and “compare sources” controls.
- Conflict labels when sources disagree; no forced false consensus.
- Provider-outage fallback that preserves partial source evidence.
- Privacy scopes: private receipt, workspace receipt, or shareable receipt.
- Exportable research result with redacted metadata.

#### Acceptance criteria

- Every source receipt is linked to an operation and owner/workspace scope.
- Private source content never appears in public status, ordinary logs, or unsigned webhooks.
- Long evidence is bounded and paginated rather than truncated mid-structure.
- Conflicting source values are represented explicitly.
- A failed AI extraction can still return source URL/title and bounded page evidence where available.
- Receipt persistence survives provider failover and process restart.

#### Likely files

`control_plane.py`, `bot.py`, `api_contract.py`, `dashboard.py`, `test_bot.py`, `test_platform.py`, `test_dashboard.py`.

---

### Wave D — Incident timeline and deployment readiness gate

**Why fourth:** The service has experienced maintenance transitions and schema-startup failures. Operational state must be diagnosable and deployment must fail before taking the bot offline.

#### Admin capabilities

- Incident timeline with start time, affected components, sanitized reason, probes, snapshots, recovery attempts, and resolution.
- Deployment readiness checks for migrations, schema columns/indexes, dashboard bind, database connectivity, provider configuration, Telegram, Discord, browser pool, queue, watchers, and schedules.
- Admin dashboard actions: acknowledge, annotate, retry probe, enter maintenance, and resolve after recovery criteria.
- Public status projection containing only safe component state and timestamps.
- Redacted incident export for support/debugging.

#### Acceptance criteria

- A failed readiness gate blocks release before the process is considered operational.
- A single component failure does not erase unrelated component health.
- Incident records never contain tokens, passwords, cookies, raw credential prompts, or full private page contents.
- Automatic recovery requires the configured consecutive healthy probes and records each probe.
- Maintenance mode does not prevent `/settings`, `/maintenance_log`, or admin diagnostics from responding.
- Fly deployment logs expose a safe failure reason and request/incident ID.

#### Likely files

`control_plane.py`, `dashboard.py`, `.github/workflows/fly-deploy.yml`, `test_platform.py`, `test_dashboard.py`.

---

### Wave E — Developer webhooks and event delivery

**Why fifth:** Once operations, receipts, and incidents have durable events, developer integrations can consume them safely instead of polling internal tables.

#### Developer capabilities

- Create/revoke webhook subscriptions by workspace and event type.
- HMAC signatures, timestamp tolerance, replay protection, secret rotation, and delivery IDs.
- Retry/backoff with dead-letter visibility and manual replay.
- Delivery history with response status, latency, and redacted error.
- Per-key scopes, quotas, and rate limits.
- Test delivery endpoint and signed example payloads.

#### Acceptance criteria

- A webhook cannot receive another owner’s or workspace’s events.
- Duplicate delivery IDs are safe to process idempotently.
- Rotating a secret invalidates old signatures according to a documented grace period.
- Payloads exclude secrets and private source content by default.
- Failed deliveries are bounded and observable without blocking task execution.
- Dashboard and API responses use structured request IDs and error codes.

#### Likely files

`control_plane.py`, `dashboard.py`, `api_contract.py`, `bot.py`, `test_platform.py`, `test_dashboard.py`.

---

### Wave F — Custom tools/connectors with safe execution contracts

**Why sixth:** Custom tools are valuable for developers, but they should be built only after scopes, webhooks, audit events, and workspace boundaries are stable.

#### Developer capabilities

- Register a tool name, version, input schema, output schema, timeout, and allowed scopes.
- Read-only tools enabled by default; side-effecting tools require explicit approval mode.
- Per-tool quota, concurrency limit, retry policy, and audit trail.
- Connector health checks and disable/revoke controls.
- Natural-language tool selection constrained to the registered schema.
- Test-run mode with synthetic inputs and no external side effects.

#### Acceptance criteria

- Invalid schemas, excessive timeouts, unsafe URLs, and unsupported side effects are rejected before storage.
- Model output cannot expand a tool’s permissions or invoke unregistered operations.
- Tool execution is owner/workspace scoped and auditable.
- SSRF protections and private-network blocking are enforced at the connector boundary.
- Tool failure returns a structured error without cancelling unrelated operation artifacts.

#### Likely files

`control_plane.py`, `dashboard.py`, `bot.py`, `api_contract.py`, `test_platform.py`, `test_dashboard.py`, `test_bot.py`.

---

### Wave G — Tenant/business workspaces and analytics

**Why last:** This is the largest authorization and data-isolation change. It should follow the personal workspace, event, and tool contracts rather than be introduced first.

#### Capabilities

- Organization/workspace membership with owner, admin, member, developer, and viewer roles.
- Tenant-level plans, quotas, domains, tool scopes, retention, and approval policies.
- Usage aggregates for model calls, browser time, files, tasks, watchers, webhooks, and API requests.
- Admin analytics with privacy-preserving aggregates.
- Tenant export, archive, and retention controls.

#### Acceptance criteria

- Cross-tenant reads/writes are impossible in unit, integration, and route tests.
- Existing personal accounts remain compatible and do not require migration-time organization membership.
- Role changes are audited and take effect on the next authorization decision.
- Usage aggregates exclude raw prompts, secrets, and private source content.
- Billing/plan mutations remain outside this wave unless separately confirmed.

#### Likely files

`control_plane.py`, `dashboard.py`, `bot.py`, `discord_bot.py`, `api_contract.py`, tests, migration notes.

## Dependency graph and implementation order

```text
A Workspace UX
  ├── B Smart watchers
  └── C Evidence receipts
        └── D Incident/readiness
              ├── E Webhooks
              │     └── F Custom tools
              └── G Tenant/business platform
```

Recommended execution order:

1. Wave A: workspace controls and context indicator.
2. Wave B: watcher checkpoints, significance, and receipts.
3. Wave C: research evidence receipts.
4. Wave D: incident timeline and CI readiness gate.
5. Wave E: signed webhooks and delivery history.
6. Wave F: custom tools/connectors.
7. Wave G: tenant/business workspaces and analytics.
8. Documentation, rollout, and deprecation cleanup after each wave—not only at the end.

## Cross-cutting engineering requirements

- Use additive, idempotent migrations; create indexes after nullable columns exist.
- Every mutation accepts or derives an idempotency key where retries are possible.
- Every async operation has an owner/workspace scope, lifecycle state, redacted event trail, and bounded retry policy.
- Use structured error codes and request IDs across Telegram, Discord, dashboard, and developer API.
- Keep natural-language interpretation separate from authorization; the model may propose an action, but deterministic validation decides whether it can run.
- Keep user-visible progress honest: queued, thinking, waiting for approval, running, paused, retrying, completed, failed, or maintenance.
- Add feature flags and rollback notes per wave.
- Do not introduce a new paid external service without explicit approval.

## Verification plan

For each wave:

```bash
python -m py_compile bot.py control_plane.py dashboard.py
pytest -q <focused tests>
pytest -q
git diff --check
```

Before deployment:

```bash
git status --short
gh workflow run 'Deploy to Fly.io' -R mrphatom/Playwright-tg --ref fix/neon-percent-placeholders
gh run watch <run-id> -R mrphatom/Playwright-tg --exit-status
curl -fsS --max-time 20 https://playwright-tg-mrphatom.fly.dev/
```

Live smoke checks must cover dashboard bind, Neon initialization, Telegram startup, Discord gateway readiness, browser pool readiness, and at least one read-only operation.

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Workspace context leaks across chats | Owner/workspace predicates, explicit null-scope semantics, isolation tests, response indicator |
| Watcher notification storms | Checkpoint hashes, debounce, quiet hours, bounded retries, delivery receipts |
| Evidence exposes private data | Scope every receipt, bounded excerpts, redaction tests, no public default |
| Migration breaks existing Neon tables | Add columns before indexes; idempotent catalog checks; restart tests |
| Webhook replay or secret leakage | HMAC + timestamp + delivery ID + rotation + redacted payloads |
| Custom tool expands permissions | Deterministic schema/permission validator; approval mode for side effects |
| Tenant migration causes authorization regressions | Personal-account compatibility layer; deny-by-default tests; staged rollout |
| Large feature wave destabilizes bot | One vertical slice per commit/deployment; feature flags; full suite gate |

## Open questions for review

1. Should each Telegram user receive an automatically created personal workspace, or should workspace mode be opt-in?
2. Should workspace selection apply independently to Telegram and Discord, or be synchronized through account pairing?
3. Which watcher significance modes should be available on free, Pro, Max, and developer plans?
4. Should evidence receipts default to private or workspace-visible?
5. Which incident fields may appear on the public status page?
6. Should developer webhooks be available only to developer/Max plans initially?
7. Should custom tools be HTTP-only in the first release, or should Telegram/Discord actions be registrable too?
8. Is tenant/business billing explicitly out of scope until the authorization and analytics layer is complete?

## Decision gate

This document is a planning artifact. Do not begin Wave B or later until Wave A’s user-facing workspace contract is reviewed and accepted. Any answer to the open questions that materially changes data isolation, billing, public publication, or external side effects should update this document before implementation.

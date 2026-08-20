# Developer Mode Design

## Objective

Add a governed developer tier for Telegram users who need to integrate GreyAI with other Telegram bots or external automation. Developer access is never self-service: a user requests access from the bot, the request is delivered to the configured administrator, and only an administrator can grant or revoke the role.

## Authorization model

The platform keeps three roles: `user`, `developer`, and `admin`. The `developer` role is strictly below `admin`; it cannot inspect other users, mutate roles, ban users, review reports, or access administrator endpoints. Existing admin identification through `ADMIN_TELEGRAM_IDS` remains authoritative. A developer must also have an active account status; banned, suspended, or limited users cannot use developer API keys.

Role grants and revocations are performed only by admin-protected Telegram commands and the equivalent CSRF-protected dashboard routes. `/devrequest` is available to normal users, stores an auditable request, and sends a concise notification to every configured administrator. The request message must not contain credentials or secrets. Grant and revoke operations are idempotent and preserve the target user's current account status.

## Developer advantages

Developers receive a higher default quota than free users, configurable through `DEVELOPER_QUOTA_LIMIT` with a conservative default of 250 units. The advantage is implemented in the server-side quota policy, not in Telegram UI. A developer still consumes quota, remains subject to account status, global concurrency limits, domain allowlists, SSRF protections, and API-key rate limits. Developers do not bypass payment, safety, or browser execution controls.

## API-key lifecycle

API keys use a random high-entropy secret with a public identifier prefix. The plaintext key is returned exactly once at creation and is never stored, logged, or included in later responses. The database stores only a keyed digest derived with HMAC-SHA-256 from `API_KEY_HASH_SECRET` (falling back to the existing session encryption seed only for local development). Key rows contain `key_id`, `key_hash`, owner, display name, JSON scopes, status, per-minute limit, timestamps, last-use metadata, and revocation time.

The key lifecycle is create, authenticate, use, revoke. Creation requires an active developer role and validates a bounded name and an allowlisted non-empty scope set. Authentication uses constant-time digest comparison, rejects unknown, revoked, expired, or non-developer owners, and returns only server-side metadata. Revocation is owner- or admin-authorized, idempotent, and immediately blocks further requests. Key listings return identifiers, names, scopes, status, timestamps, and last-use metadata but never key material or hashes.

## Scopes

The initial scope set is intentionally small:

| Scope | Capability |
|---|---|
| `check` | Run a bounded browser check against a validated URL and return redacted title/extraction/status data. |
| `watch` | Reserved for a future API-managed watcher endpoint; not enabled until a durable ownership contract exists. |
| `schedule` | Reserved for a future API-managed schedule endpoint; not enabled until delivery and ownership semantics are defined. |
| `sessions` | Reserved for a future session-management endpoint; not enabled until encrypted-session transfer semantics are reviewed. |

Only `check` is enabled in the first release. The schema accepts the full documented scope vocabulary for forward compatibility, but creation rejects scopes that are not currently enabled. This prevents a key from appearing to have permissions that no endpoint actually enforces.

## Integration endpoint

The first integration endpoint is `POST /api/v1/check`, authenticated with `Authorization: Bearer <key>`. The request accepts a URL and an optional bounded extraction prompt. The handler validates JSON type and size, reuses the existing URL allowlist/SSRF checks through the browser pipeline, creates an operation with a correlation ID, enforces the API-key minute limit and platform concurrency, and returns a redacted JSON result. Screenshots are deleted before the request completes. The endpoint never exposes cookies, browser contexts, credentials, raw page dumps, or internal stack traces.

The dashboard session endpoints provide developer-owned key management: `GET /api/keys`, `POST /api/keys`, `DELETE /api/keys/{key_id}`, and `GET /api/developer/stats`. Mutations require the existing secure dashboard session plus CSRF validation. API-key authentication is separate from dashboard cookies and does not inherit dashboard privileges.

## Rate limiting and audit

Each key has a configurable per-minute limit, defaulting to 30 requests per minute and bounded by a server-side maximum. Usage is recorded in a rolling minute bucket with an atomic transaction so concurrent requests cannot bypass the limit. Usage rows are bounded by retention cleanup and indexed by key and bucket. Every key creation, listing, authentication denial, rate-limit denial, use, and revocation produces an audit event without the plaintext key.

The on-call questions are: which keys are active, which integrations are denied or rate-limited, whether a developer role changed, and whether browser checks are failing by operation ID. Structured logs include event type, key ID, owner ID, scope, operation ID, and outcome; they exclude bearer values and page content.

## Migration and rollback

The role change uses an additive migration strategy. Existing `users` tables created with the old role check constraint are rebuilt transactionally into a replacement table with the expanded constraint while preserving all rows and indexes. New API-key and usage tables are additive and can be left unused if deployment is rolled back. Code is deployed only after tests cover fresh and existing-style databases, ownership checks, role revocation, single-display key material, scope enforcement, concurrent-limit boundaries, and endpoint authentication.

Rollback consists of reverting application code and disabling developer API routes while retaining the additive tables. Previously issued keys should be revoked before rollback if the integration surface is considered unsafe; no plaintext key recovery is possible or required.

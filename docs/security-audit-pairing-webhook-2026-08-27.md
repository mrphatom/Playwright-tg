# Webhook and Pairing-Token Security Audit

**Project:** GreyAI Telegram + optional Discord bot  
**Audit revision:** `16fac7db0183ca59ed50c65c72013be389ff0f35`  
**Audit date:** 27 August 2026  
**Scope:** Webhook exposure, Telegram↔Discord pairing codes, dashboard login/session tokens, manual-handoff capabilities, Discord authorization scope, audit logging, and deployment configuration.

## Executive conclusion

The deployed application does **not currently use inbound webhooks**. Telegram is started with long polling, and Discord uses the `discord.py` gateway client. A repository-wide source search found no webhook route, `set_webhook` call, signature-header handler, or Discord HTTP interactions endpoint. Consequently, there is no current webhook secret-verification defect to fix. If a webhook transport is introduced later, it must be treated as a new security boundary rather than inferred from the current gateway/polling implementation. Telegram documents the `secret_token` header for webhook requests, while Discord requires validation of `X-Signature-Ed25519` and `X-Signature-Timestamp` on HTTP interactions.[1] [2]

The pairing flow was substantially secure before this audit: the code is high entropy, only a SHA-256 digest is stored, the code is private-chat confirmed on Telegram, invalid guesses are bounded, and a successful code is consumed. The audit reproduced one concrete database defect and several hardening gaps. These are now fixed in commit `16fac7d`: repeated pair–revoke–repair cycles preserve history, pairing consumption uses an explicit write transaction, challenge issuance is rate-limited and cleans stale pending records, issuance/revocation generate secret-free security events, and Discord guild traffic requires both an explicitly allowed server and an explicitly allowed channel. Full tests, static checks, deployment, and public health validation passed.

## Token and capability inventory

| Token or capability | Issuer and transport | Storage | Lifetime and replay | Binding and revocation | Audit result |
|---|---|---|---|---|---|
| Discord pairing code | `/pair` in a private Discord DM; manually entered as Telegram `/pair <code>` | SHA-256 digest only in `account_pairing_challenges`; raw code is sent transiently in an ephemeral Discord response | Default 600 seconds, application-bounded to 60–900 seconds; consumed on success; invalid guesses count toward five attempts | Bound to the requested Discord identity and the authenticated Telegram user; active account uniqueness is enforced by database indexes; unpairing revokes the active relationship | **Hardened and tested.** No raw code was found in the database or the new security-audit metadata. |
| Dashboard login token | Dashboard link issued by the bot and received as `GET /login?token=...` | SHA-256 digest and encrypted session material in SQLite | Creation TTL is bounded; the same still-active token intentionally returns the same active session on replay | Session revocation invalidates the resulting session; login-token replay behavior is an existing, tested product decision | **Protected but residual bearer-URL risk remains.** `no-store` and `Referrer-Policy: no-referrer` are applied; strict one-use semantics were not introduced because existing tests codify replay-to-the-same-session behavior. |
| Dashboard session and CSRF token | Secure HTTP cookies after login | Hashed session ID, CSRF token, and expiry in SQLite; recovery/session material is encrypted in public mode | Default session lifetime is 24 hours, bounded maximum 72 hours; session is revoked server-side | Session cookie is `Secure`, `HttpOnly`, and `SameSite=Lax`; mutations require CSRF cookie/header/session equality | **Pass.** Existing dashboard tests cover session scoping, revocation, CSRF, redaction, and security headers. |
| Developer API key | Generated only for active developer/admin accounts | HMAC-SHA-256 digest using a dedicated API-key hash secret; raw key is returned only at creation | No raw key replay semantics; explicit revocation and bounded per-minute rate limit | Owner/admin scoped, active-role checked, scope checked, and rate-limited | **Pass.** Existing tests verify one-time presentation, omitted listings, HMAC authentication, revocation, and atomic rate limiting. |
| Manual challenge handoff URL | Unauthenticated capability URL sent to the user for a human CAPTCHA/MFA/security challenge | High-entropy in-memory capability state; no cookie authentication | Short-lived and owner-scoped; action payloads and interaction types are bounded | Expiry, cancellation, and completion remove capability state | **Protected capability boundary.** Routes use token syntax checks, `Cache-Control: no-store`, `X-Robots-Tag: noindex,nofollow`, CSP nonce, and no-referrer policy. Possession remains the authorization mechanism until expiry. |

## Verified controls

The Telegram pairing confirmation is restricted to a private Telegram chat before any pairing-code lookup or consumption occurs. Group and channel messages receive a security response and cannot consume a code. A raw Telegram numeric ID is never accepted as proof. The Discord side is DM-only for both pairing initiation and unpair confirmation. The unpair confirmation button is bound to the original Discord user, so another user cannot press a leaked or forwarded confirmation control successfully.[3]

Pairing codes are generated with `secrets.token_urlsafe(18)`, which provides a high-entropy random value, while only a digest is persisted. Successful consumption now starts with `BEGIN IMMEDIATE`, rechecks the challenge inside the write transaction, and requires the conditional `consumed_at` update to affect exactly one row. This makes the one-winner contract explicit under concurrent Telegram confirmations and prevents a race from leaking an uncaught database exception.[4]

The dashboard middleware applies `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, a nonce-bearing CSP, and `Cache-Control: no-store`. Dashboard mutation routes require a CSRF token in both the cookie and request header, and the server-side session copy must match using constant-time comparison. The login response sets secure cookie flags and redirects to `/`, removing the token from the visible URL after the exchange.[5]

## Findings and remediation

### Finding P-01 — repeated revocation could raise a database integrity error

**Severity:** Medium reliability/security-boundary defect.  
**Status:** Fixed and deployed.

The original `account_pairings` table used `UNIQUE(telegram_user_id, status)` and `UNIQUE(discord_user_id, status)`. That allowed one revoked row, but the second transition from `active` to `revoked` attempted to create a duplicate `(identity, 'revoked')` value. The audit reproduced this with `pair → revoke → pair → revoke`, where the second revoke raised `sqlite3.IntegrityError`.

The fix migrates legacy tables without dropping rows, removes status-inclusive table uniqueness, and installs partial unique indexes restricted to `status = 'active'`. Revoked history is therefore retained while the database still enforces at most one active pairing per Telegram identity and per Discord identity. A legacy-schema migration test and a three-cycle repair test now pass.[6]

### Finding P-02 — pairing consumption did not make its transaction boundary explicit

**Severity:** Medium concurrency integrity risk.  
**Status:** Fixed and tested.

The original implementation selected an unused challenge and later marked it consumed without an explicit immediate write transaction or checking the update row count. Under concurrent confirmations, SQLite commonly serialized the operations, but the intended one-winner guarantee was not encoded clearly enough and an active-pairing conflict could surface as a database error.

The implementation now takes an immediate SQLite transaction before reading the challenge and checks that exactly one conditional consume update succeeds. The concurrent confirmation regression passes with exactly one pairing and no exception returned to the caller. The user-facing loser remains a generic invalid/expired/already-used response.

### Finding P-03 — challenge issuance could be spammed by one Discord identity

**Severity:** Low-to-medium resource exhaustion and user-confusion risk.  
**Status:** Fixed and tested.

Pairing challenge creation previously had no per-identity cooldown and left stale pending challenges in the database. The fix removes expired or already-consumed rows, enforces a bounded five-to-300-second cooldown per Discord identity, and invalidates that identity’s older pending code when a new request is allowed. The default is 30 seconds. The Discord response remains generic on throttling and does not reveal any code in logs or audit metadata.

### Finding P-04 — Discord guild authorization was broader than the approved privacy boundary

**Severity:** Medium authorization/privacy gap.  
**Status:** Fixed and documented.

The prior predicate allowed all channels in an allowlisted guild. The implementation now requires both `DISCORD_ALLOWED_GUILD_IDS` and `DISCORD_ALLOWED_CHANNEL_IDS` to match for non-DM messages and interactions. DMs remain available to authenticated paired users; guild traffic is denied when either list is empty or the channel is not explicitly listed. This prevents a server-level allowlist from silently becoming a whole-server authorization grant.

### Finding P-05 — Discord pairing lifecycle events were not durably auditable

**Severity:** Low-to-medium accountability gap.  
**Status:** Fixed and tested.

Pairing issuance and unpair confirmation now create durable `security_audit_events` entries containing platform, principal, action, outcome, and tightly filtered metadata. The audit writer accepts only bounded metadata keys such as reason, TTL, and source. It does not store the pairing code, dashboard token, handoff URL, API key, cookie, or arbitrary request payload. Tests verify the challenge digest differs from the displayed code and that the audit row contains no raw code.

## Webhook review

No webhook endpoint exists in the current application. The observed transports are:

| Platform | Current transport | Current signature path | Audit decision |
|---|---|---|---|
| Telegram | Long polling through `run_polling(allowed_updates=Update.ALL_TYPES)` | Not applicable because the application does not receive Telegram HTTP callbacks | No webhook code added; polling remains unchanged |
| Discord | `discord.py` gateway client | Not applicable because the bot is not using an HTTP interactions endpoint | No HTTP interactions endpoint added; gateway remains unchanged |
| Dashboard/API | Public aiohttp HTTP routes | Session, CSRF, bearer API-key, and capability-token controls apply by route class | Existing session/API/challenge controls were reviewed; no webhook-style signature claim is made |

The README now states the future requirements explicitly. A future Telegram webhook must validate `X-Telegram-Bot-Api-Secret-Token` before parsing or acting on the update. A future Discord HTTP interactions endpoint must validate both timestamped Ed25519 headers against the raw request body before parsing, acknowledge PING correctly, reject invalid signatures with `401`, and add replay, size, schema, and negative-signature tests.[1] [2]

## Residual risks and deliberate non-changes

**Dashboard login-token replay remains a deliberate compatibility decision.** The current exchange function returns the same still-active session when an unexpired login token is replayed. This avoids breaking the existing dashboard-link UX and is covered by a test. It is still a bearer URL: anyone who obtains the URL before expiry can attempt the exchange. The response has `no-store`, `no-referrer`, secure cookies, and a redirect to a token-free path, which reduce but do not eliminate exposure through copied URLs, browser history, reverse-proxy access logs, or chat retention. Strict single-use exchange should be a separately approved product/security change because it changes the tested behavior.

**Pairing hashes remain compatible SHA-256 digests.** Pair codes are high entropy and short-lived, so the practical online guessing risk is bounded by expiry, five attempts, and the new issuance cooldown. A keyed HMAC or pepper for pairing hashes could improve containment after a database-only compromise, but changing it without a compatibility migration would invalidate existing challenges and would not justify silently disrupting active users. API keys already use a dedicated keyed HMAC design.

**Manual handoff links remain bearer capabilities.** This is intentional: the user must be able to open the challenge without an authenticated dashboard session. The link is high entropy, owner-scoped in server state, short-lived, non-indexable, non-cacheable, and action-bounded. Operators should avoid logging full query strings and should not paste handoff URLs into public channels.

**No live Discord pairing test was performed.** No Discord bot token or approved test server/channel was provided for this audit, and the Discord adapter remains disabled unless separately configured. The repository tests exercise the pairing, authorization, audit, and scope boundaries; they do not prove a live Discord gateway session.

**Other previously identified Discord risks remain outside this focused patch.** In particular, attachment URL fetching should still be hardened with strict Discord CDN host validation or the native attachment-read path, and destructive Discord administrative commands should remain confirmation-gated with ownership, idempotency, and audit receipts before being treated as production-grade. These are not claimed as fixed by this pairing/webhook audit.

## Deployment and validation evidence

| Check | Result |
|---|---|
| Focused pre-change security suite | 50 passed, 3 warnings |
| Pairing/security regression module after changes | 28 passed, 3 warnings |
| Full repository suite | **369 passed, 3 warnings** |
| Python compilation of affected modules | Passed |
| Ruff import/undefined-name checks (`I,F`) | Passed |
| `git diff --check` | Passed |
| Changed-file credential-shaped literal scan | No matches |
| GitHub deployment workflow | `33075326321`, success |
| Deployed revision | `16fac7db0183ca59ed50c65c72013be389ff0f35` |
| Public root | HTTP 200 |
| Public `/api/status` | HTTP 200, operational |
| Live response headers | `no-store`, `no-referrer`, CSP, `DENY`, and `nosniff` observed |

The three warnings are third-party Python/Discord deprecation warnings, not test failures. The GitHub CLI could not enumerate Actions secret names because the current integration returned HTTP 403, and `flyctl` was unavailable locally; no secret values were requested, printed, or copied. The workflow itself successfully consumed its configured secret references during deployment.

## Secure activation checklist

Before enabling Discord, keep `DISCORD_BOT_TOKEN` only in Fly.io or GitHub secret storage, set `DISCORD_ENABLED=true` only after the secret exists, enable Discord Message Content Intent in the Developer Portal, and configure both the server and channel ID lists. Do not put the token, pairing code, dashboard URL, API key, or handoff URL in a public channel, repository, issue, log, screenshot, or prompt.

To pair, the user should run `/pair` in a private Discord DM, then send `/pair <code>` only in GreyAI’s private Telegram chat. To replace a relationship, use `/unpair` in the private Discord DM and confirm with the displayed button. The Telegram account remains authoritative for plan, role, quota, status, and durable context.

For public operation, keep `PUBLIC_MODE=true` only with a dedicated strong `SESSION_ENCRYPTION_KEY`, `API_KEY_HASH_SECRET`, a reviewed `DASHBOARD_BASE_URL`, and an explicit non-empty domain allowlist. Keep `PAIRING_CHALLENGE_COOLDOWN_SECONDS` at its bounded default unless there is a measured operational reason to change it; the application clamps it to 5–300 seconds.

Any credential or bot token that was ever pasted into chat or exposed to a tool/session should be rotated. This recommendation is intentionally expressed without repeating or identifying any historical secret value.

## References

[1]: https://core.telegram.org/bots/api "Telegram Bot API — setWebhook and secret_token"

[2]: https://docs.discord.com/developers/interactions/overview "Discord Interactions Overview — gateway versus HTTP endpoint and signature validation"

[3]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/bot.py#L9850-L9870 "GreyAI Telegram private pairing confirmation"

[4]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/control_plane.py#L805-L896 "GreyAI pairing challenge issuance and atomic consumption"

[5]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/dashboard.py#L170-L203 "GreyAI dashboard security middleware and login handler"

[6]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/control_plane.py#L563-L657 "GreyAI legacy account-pairing constraint migration"

[7]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/discord_bot.py#L82-L132 "GreyAI Discord guild and channel scope predicates"

[8]: https://github.com/mrphatom/Playwright-tg/blob/16fac7db0183ca59ed50c65c72013be389ff0f35/README.md#telegram-and-discord-surfaces "GreyAI operational pairing, scope, and future webhook guidance"

## Postflight evolution record

The security-and-hardening workflow produced a sanitized accepted evolution record for change `16fac7d`. The observed baseline was 50 focused tests; the final repository suite passed 369 tests, deployment succeeded, and the public root/status endpoints returned HTTP 200. The reusable workflow improvement was to require explicit transport classification, reproduce token lifecycle abuse cases before editing, verify secret-free storage, and include pairing/Discord/platform-contract tests in the deployment regression gate. The rollback unit is commit `16fac7d`; any rollback of the database constraint migration should be reviewed as a data migration rather than performed as a blind schema revert.

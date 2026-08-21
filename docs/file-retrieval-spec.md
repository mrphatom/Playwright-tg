# GreyAI File Retrieval and Delivery Specification

## Objective

GreyAI may retrieve and send a file when the user asks for a lawful, user-authorized, public-domain, openly licensed, or otherwise permitted resource. The result is delivered as a Telegram document, audio file, video file, archive, or other validated artifact instead of a screenshot. The request is handled as a bounded background operation with an estimated time, short progress updates, a success receipt, and a clear failure message.

## Content boundary

The feature must not locate or distribute pirated music, movies, software, books, games, or other copyrighted material without permission. It must not bypass DRM, paywalls, account controls, download restrictions, CAPTCHAs, malware defenses, or platform blocks. Grey may retrieve direct user-provided URLs or discover a source from approved search providers when the request is authorized and the source policy permits it. “Find a song/movie/app” no longer requires a direct URL: Grey searches approved providers, follows bounded result/detail links, and selects the best permitted artifact candidate. Suspicious, private, blocked, or clearly unauthorized sources still fail closed.

## Plan policy

| Account | Access | Per-file limit | Daily jobs | Behavior |
|---|---|---:|---:|---|
| Free | Denied | 0 | 0 | Explain that retrieval is unavailable and show `/upgrade`. |
| Pro | Limited | Configured bounded size | Configured bounded count | Allow approved, lawful sources with stricter concurrency, duration, and file-size limits. |
| Max | Expanded | Configured maximum | Configured maximum | Allow larger bounded artifacts and higher concurrency, subject to the same source and malware controls. |
| Developer | Controlled | Configured maximum | Configured maximum | Access follows the developer account policy; it does not bypass source, safety, or quota enforcement. |
| Admin | Operational | Configured maximum | Configured maximum | Same safety controls; administrative status does not authorize unlawful distribution. |

A download consumes one existing execution quota unit only after entitlement and URL validation succeed. Download-specific rate limits and active-job limits are enforced separately from browser-task limits.

## Pipeline

1. Parse a `download` intent containing a request, optional explicit URL, optional source candidates, and a desired artifact type. URL-less requests create an approved search-first discovery plan.
2. Enforce account status, plan entitlement, download cooldown, active-job limit, global queue capacity, and existing URL/domain/Tor policy before network retrieval.
3. Resolve an explicit source or search approved providers, then follow at most two bounded result/detail hops. Do not select an unapproved marketplace, private host, or dark-web target.
4. Stream the response to a private temporary path with a strict byte cap, total timeout, redirect policy, content-type and extension checks, and progress callbacks.
5. Validate the final artifact using magic bytes and archive safety checks. Reject path traversal, archive bombs, executable payloads when not requested, suspicious double extensions, oversized decompression ratios, and unknown or mismatched content.
6. Send the artifact through Telegram using the correct media type and a concise receipt. Never expose the temporary path or source credentials.
7. Delete the temporary artifact after delivery or failure and record a redacted operation receipt. Progress messages are edited in place and do not disclose secrets or full URLs with credentials.

## Progress contract

The user receives an initial estimate, then updates no more often than the configured interval and no more frequently than the Telegram-safe edit rate. Updates include phase, downloaded bytes, total size when known, percentage when calculable, and a coarse ETA. Success includes the artifact name, size, source host, and operation reference. Failure includes a safe reason and retry guidance without stack traces.

## Source policy

The existing exact and wildcard domain allowlist remains authoritative. The release may add a curated set of official, public, open-source, and public-domain domains as deployment defaults, but it must not enable arbitrary domains or dark-web marketplaces by default. `.onion` access remains explicit-host allowlisted and restricted to the existing Max/governed role policy. Tor is a routing option, not a trust signal.

## Browser reliability

Grey must not evade detection or defeat platform security. Reliability improvements are limited to normal browser behavior: realistic bounded waits, reuse of one browser context per job, cache-aware retries, rate-aware backoff, transparent user-agent policy, honoring explicit block/robots/terms signals where practical, and clear escalation when a site requires a login, CAPTCHA, or manual approval. No stealth fingerprint manipulation or automated anti-bot bypass is added.

## Acceptance criteria

- Free users are refused before network access.
- Pro users can retrieve a permitted small artifact and are refused when size, duration, rate, or daily limits are exceeded.
- Max/developer/admin jobs remain bounded and auditable.
- Direct HTTPS retrieval follows redirects only when each destination passes policy; private IPs, localhost, credentials in URLs, and unsupported schemes are rejected.
- Download progress edits are throttled and success/failure states are visible.
- Artifacts are sent as files and deleted locally after completion.
- Archive traversal and suspicious executable content are rejected.
- Malformed model output, unsupported source types, provider errors, and cancellation fail safely.
- Existing chat, browser, watcher, screenshot, API, and starter-archive tests remain green.

## Additional agentic extensions to prioritize after the core release

1. Artifact provenance receipts with source host, content hash, license/source classification, and retention status.
2. Resumable downloads for permitted large files using bounded range requests and integrity checks.
3. User-owned artifact history with explicit deletion and expiration controls.
4. Batch retrieval plans that require a preview and confirmation before multiple downloads.
5. File transformation tools such as format conversion, OCR, transcription, metadata extraction, and archive listing, each separately gated and bounded.
6. Agent handoff summaries that preserve the original goal, current job state, and retry options across Gemini failover.

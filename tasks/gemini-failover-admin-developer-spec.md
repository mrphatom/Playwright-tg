# Dual Gemini failover and administrator developer capability

## Baseline

The bot currently has one `GEMINI_API_KEY`, one legacy `ai_model`, and direct model calls in chat, intent parsing, activity review, watcher condition checks, browser extraction, and multimodal interpretation. A provider failure can surface as a normal error and there is no second credential path. Developer access is role-exclusive: configured administrators are `admin`, while API-key creation, the Telegram developer decorator, and dashboard developer routes require `developer` exactly. This explains why the configured administrator sees elevated-access text for `/devrequest` but cannot use `/newkey`.

## Provider contract

Preserve the existing `GEMINI_API_KEY` as primary and add `GEMINI_API_KEY_2` as the optional secondary. The provider resolves the current key list at runtime, never logs keys, and keeps short in-memory cooldowns for keys that return quota/rate-limit or transient-provider failures. Each model request attempts the current healthy key first and switches to the other key only for retryable provider errors such as HTTP 429, quota/resource-exhausted responses, 5xx, timeout, or transport failure. Invalid-request/authentication errors are not silently retried as if quota exhaustion; if the primary is invalid but the secondary succeeds, the request continues and the failure is logged without secrets. If both keys fail, the caller receives the existing safe generic failure behavior.

The provider owns text and media requests. Existing legacy model fakes remain usable in tests and local single-key mode; production dual-key mode uses per-request HTTPS headers so keys do not share mutable global SDK configuration. Failover is per model call, not a browser-task restart: browser pages, saved sessions, operation IDs, and task state remain intact while a subsequent extraction or condition evaluation uses the healthy key.

## Administrator developer semantics

Configured administrators remain stored as `admin` and retain all administrator permissions. `is_developer` becomes capability-oriented: an active, non-banned administrator or an active developer returns true. API-key ownership/authentication and dashboard developer management accept either active admin or active developer. `/devrequest` continues to short-circuit for admins; `/grantdeveloper` still requires a prior open request for ordinary users and remains admin-only. `/revokedeveloper` must not downgrade or remove administrator permissions; attempting to target an administrator returns the existing protected response.

## Safety and rollback

Secondary-key values are environment-only and documented as placeholders. No key appears in URLs, logs, audit rows, Telegram responses, or source. The failover provider is a single module-level seam, so rollback is one commit reverting the provider and restoring direct calls. Regression tests cover primary success, retryable primary failure with secondary success, both-key failure, no retry on malformed requests, administrator developer capability, ordinary-user denial, and protected administrator role preservation.

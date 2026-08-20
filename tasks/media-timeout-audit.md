# Media timeout audit

## User evidence

The provided Telegram screenshots show 1-second and 3-second voice notes and a screenshot image receiving `The media interpretation timed out. Please try a shorter voice note or smaller image.` The inputs are below the configured 12 MB media cap, so size is not a sufficient explanation.

## Local reproduction

A production-like screenshot request using the configured local primary Gemini credential returned HTTP 429 in 0.54 seconds. The redacted provider response identified `RESOURCE_EXHAUSTED` for the `generate_content_free_tier_requests` metric on the configured `gemini-3.6-flash` model and advised retrying after approximately 10 seconds.

## Root-cause hypotheses

The current media provider uses the general 20-second chat deadline for each key attempt and does not distinguish quota exhaustion from media-format or model errors in the user-facing handler. The primary key is quota-exhausted locally. Production has a secondary key configured, but the live secondary outcome is not visible from the sandbox because its secret is stored only in GitHub/Fly. A secondary timeout can therefore surface as the misleading media-timeout message even when the original failure was quota exhaustion.

## Required fix

Add a media-specific provider deadline and retry-after-aware error classification, preserve key failover, and return safe, actionable quota/provider messages rather than asking users to shorten tiny media. Add tests for HTTP 429 primary-to-secondary media failover, both-key quota exhaustion, and image/voice response handling. Keep keys out of logs and response text.

## Official Gemini documentation findings

The current [Gemini rate-limit documentation](https://ai.google.dev/gemini-api/docs/rate-limits), retrieved 2026-08-20, states that rate limits are applied per project, not per API key. Therefore, two keys only provide useful failover when they belong to projects with independent quota; rotating keys within one project cannot bypass that project's exhausted quota. The same documentation recommends waiting and retrying after a 429 and reducing expensive request context/output when appropriate.

The [Gemini audio documentation](https://ai.google.dev/gemini-api/docs/audio), retrieved 2026-08-20, confirms inline audio under 20 MB, OGG Vorbis with MIME type `audio/ogg`, and transcription by explicitly requesting a transcript. The [image understanding documentation](https://ai.google.dev/gemini-api/docs/image-understanding) confirms PNG `image/png`, JPEG `image/jpeg`, and inline image input.

The current [Interactions API documentation](https://ai.google.dev/gemini-api/docs/interactions), retrieved 2026-08-20, recommends the Interactions API for new multimodal work. Its REST input contract uses `input` entries such as `{\"type\":\"text\",\"text\":...}` and `{\"type\":\"audio\",\"data\":base64,\"mime_type\":\"audio/ogg\"}` or `{\"type\":\"image\",\"data\":base64,\"mime_type\":\"image/png\"}`. It also supports `store=false`, which is appropriate for transient Telegram media.

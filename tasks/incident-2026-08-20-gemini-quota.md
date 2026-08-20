# GreyAI production incident: 2026-08-20

## User-visible symptom
Text chat, natural-language interpreter, screenshots, and voice notes all return the generic chat failure response: “I couldn't generate a reply right now.”

## Evidence
- The latest production deployment is reachable over HTTP and the dashboard returns HTTP 200.
- The exact generic response is returned by `generate_chat_reply()` when `gemini_provider.generate_text()` raises an exception.
- Media handlers pass their interpretation into `_process_natural_language()`, so media can reach the same failing chat-generation path.
- The deployed text model is `gemini-3.6-flash`.
- A direct non-secret smoke test against the configured Gemini credential returned HTTP 429 for `gemini-3.6-flash`: the project exceeded its free-tier `generate_content` request quota for that model.
- The same smoke test against `gemini-3.5-flash-lite` returned HTTP 200 with a valid `OK` response.
- Google's current official model documentation lists both model IDs as stable models. Google's rate-limit documentation states limits are evaluated per project and vary by model.

## Root-cause hypothesis
The primary text model quota is exhausted. The existing failover retries another key against the same model, which cannot reliably recover when both keys share a project or the fallback project/model quota is also exhausted. Media may be successfully interpreted but then fail during the final text response, producing the same generic reply message.

## Fix direction
Add model-level text fallback to `gemini-3.5-flash-lite` after retryable quota/provider failures, while preserving the existing key failover and authorization boundaries. Add regression tests for model fallback, exhausted-provider behavior, and normal primary success. Keep media routing on its dedicated model and improve safe diagnostics so quota exhaustion is distinguishable from generic failures.

## Security notes
No credential values were recorded in this file. The direct smoke tests used environment injection and reported only HTTP status and non-secret response metadata.

## Rollback
Revert the incident fix commit if the fallback introduces regressions; the last known-good production commit before the fix is available in git history.

## Sources
- https://ai.google.dev/gemini-api/docs/models
- https://ai.google.dev/gemini-api/docs/generate-content/get-started
- https://ai.google.dev/gemini-api/docs/rate-limits

Recorded: 2026-08-20.

The finding that `gemini-3.5-flash-lite` succeeded is an initial observation from the configured sandbox credential, not a guarantee that the production fallback credential has independent quota. If both production keys belong to the same project, project-level limits still apply.

## Proposed change
- Add `TEXT_FALLBACK_MODEL` configuration, defaulting to `gemini-3.5-flash-lite`.
- Make text requests try model/key combinations with cooldowns, preserving a single request budget per attempt.
- Treat empty successful candidates as provider errors so the bot does not cache a blank response.
- Add tests for 429-to-fallback and no-plaintext-secret behavior.
- User-facing errors should say when Gemini text capacity is unavailable rather than implying the prompt is at fault.

Decision status: accepted. The model-level fallback implementation passed the focused regression and full suite. A real provider smoke test with the injected credential returned `PROVIDER_OK` after Gemini 3.6 Flash quota exhaustion, demonstrating recovery through Gemini 3.5 Flash-Lite. Production deployment verification is pending.

Postflight status: pending deployment and live Telegram validation.

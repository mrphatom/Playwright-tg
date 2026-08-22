# GreyAI Whole-Code Audit and Recovery Report

## Outcome

GreyAI was audited and repaired in place. No rollback was used as the solution. The integrated repair was committed as [`e01e127`](https://github.com/mrphatom/Playwright-tg/commit/e01e12733a9cebd4b6b609fa8901a65765be76af), pushed to `main`, and deployed successfully to Fly.io. The live status endpoint returned `status: operational`, and the repository worktree was clean with `HEAD` and `origin/main` both at `e01e12733a9cebd4b6b609fa8901a65765be76af`.

The release workflow completed successfully in CI run [`32594331480`](https://github.com/mrphatom/Playwright-tg/actions/runs/32594331480) and Fly deployment run [`32594331516`](https://github.com/mrphatom/Playwright-tg/actions/runs/32594331516). The production health response also retained the expected security headers: `nosniff`, `DENY` frame protection, a restrictive Content Security Policy, and `no-store` caching.

## Confirmed root causes and repairs

| Area | Confirmed defect | Repair |
|---|---|---|
| Ordinary private chat | Short social turns could inherit unrelated durable task/code history and cause a new casual message to receive an unrelated code continuation. | Deterministic social-turn handling, history omission for standalone social turns, explicit untrusted context boundaries, and current-request authority in chat prompts. |
| Shared-chat privacy | In-memory conversation history was keyed by chat only when durable history was absent. | Owner-plus-chat history keys with private-chat compatibility preserved. |
| Selected browser sessions | Active saved-session selection was keyed by chat only, allowing one user’s session choice to enter another user’s interpreter context. | Owner-plus-chat session-state keys; direct and natural-language deletion clear the scoped selection. |
| Watchers | Watcher browser execution used the shared chat ID as the browser user ID. This could apply incorrect authorization, quota, allowlist, and session policy. | Requester identity now propagates through creation, restoration, follow-up lookup, and polling. Watcher listing, stopping, and persistence remain owner-scoped. |
| Schedules | Shared-chat schedule listing and cancellation were chat-wide. Cancellation could occur before ownership was checked. | Owner-filtered listing/deactivation and ownership verification before cancelling the running task. |
| Contact logging | Natural-language login credentials were not consistently redacted, and an unquoted password pattern could consume unrelated prose. | Credential patterns now cover natural-language username/password forms, retain quoted multi-word protection, and stop at common new-clause boundaries. |
| Response cleanup | Repeated paragraphs could be silently removed from model output. | Cleanup no longer drops repeated user-visible content; the complete response is preserved. |
| Telegram delivery | Screenshot cleanup occurred after the upload attempt, and a failed progress-message deletion could turn an already successful result into a reported failure. | Screenshot cleanup is guaranteed in `finally`; missing screenshots fail explicitly; final status deletion is best-effort after delivery. |
| Queue lifecycle | An unexpected queue-worker boundary error could enter maintenance while leaving the waiting request future unresolved. | Queue and operation state are marked failed when possible, the future receives the original exception, and maintenance then starts. `task_done()` remains guaranteed. |
| Dashboard/API input | Malformed or non-object JSON bodies could produce unhandled parser/type failures. | Shared validated JSON-object parsing returns safe 400 responses across affected mutation handlers. |
| Long responses and formatting | The shared viewer and safe renderer were reinforced so generated Markdown becomes Telegram-compatible HTML, safe placeholders remain copyable, real secrets are redacted, and long responses remain navigable. | Render-aware page sizing, owner-bound viewers, Previous/Next callbacks, placeholder-aware redaction, and bounded fallback behavior remain enforced. |

## Regression coverage

The final local gate passed **307 tests** across `test_bot.py`, `test_platform.py`, `test_dashboard.py`, and `test_sanitize.py`. The suite includes the screenshot-derived cases for casual-chat contamination, literal/broken formatting, safe placeholder preservation, long-response navigation, generic code archives, landing-page ZIP delivery, duplicate update handling, watcher ownership, schedule ownership, dashboard malformed input, contact-log credentials, download delivery races, queue failure resolution, and owner-scoped state.

Static verification also passed:

```text
Python compilation: passed
Ruff selected reliability/security checks: passed
git diff --check: passed
Production-source secret scan: passed
```

## User-visible behavior now covered

A request such as **“give me a landing page website in a zip file”** enters the dedicated landing-page archive path and delivers a deterministic dependency-light static project containing `index.html`, `styles.css`, `script.js`, and `README.md`. A request such as **“package the code above as a zip”** packages only authorized fenced source already present in the current owner-scoped context. Archives are bounded, path-validated, secret-checked, syntax-checked where applicable, inert, and never executed.

Long rendered responses use the owner-bound viewer when the rendered Telegram message would exceed the platform limit. Ordinary short chat remains a single response. Developer examples use Telegram-compatible Markdown before rendering, so application-generated HTML tags are not exposed literally. Safe placeholders remain syntactically valid, while recognized real credential-like values are redacted.

The existing verified Grey integration starter remains separate and was not replaced by the generic archive path. Existing authorization, plan gates, rate limits, domain policy, manual challenge handoff, provider failover, maintenance recovery, and confirmation requirements remain in force.

## Verification limitation

This recovery was verified with the repository’s full automated suite, fake Telegram delivery tests, static inspection, CI, Fly deployment status, and the live health endpoint. I did **not** send test messages as the user, operate Telegram Web, or claim a manual Telegram UX test that was not performed. The remaining production observation is to send the exact reported prompts through the bot normally and confirm the visible Telegram result; no code change should be made unless that observation produces a new reproducible failure.

## Operational note

The local GitHub CLI credential returned a `401 Bad credentials` while watching the deployment after the deployment steps had already completed. This did not invalidate the release: the public read-only workflow endpoint reported the exact run as `completed` with `success`, and the live Fly endpoint returned HTTP 200 with `status: operational`.

## References

1. [GreyAI audit repair commit e01e127](https://github.com/mrphatom/Playwright-tg/commit/e01e12733a9cebd4b6b609fa8901a65765be76af)
2. [CI/CD workflow run 32594331480](https://github.com/mrphatom/Playwright-tg/actions/runs/32594331480)
3. [Fly.io deployment workflow run 32594331516](https://github.com/mrphatom/Playwright-tg/actions/runs/32594331516)
4. [GreyAI live operational status endpoint](https://playwright-tg-mrphatom.fly.dev/api/status)

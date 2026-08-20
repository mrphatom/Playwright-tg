# GreyAI Gemini provider alerting

## On-call questions

1. Are Gemini quota failures occurring, and which configured model is affected?
2. Are requests succeeding through a fallback model/key, or are all providers exhausted?
3. Are non-quota model failures recurring, and when did the current incident begin?
4. Has the affected provider recovered, or does the administrator need to intervene?

## Alert policy

- Send alerts only to configured administrator Telegram IDs resolved by `admin_ids()`.
- Never include API keys, authorization headers, prompts, user IDs, URLs, raw exception messages, or response bodies.
- Use two alert categories: `quota_exhaustion` and `model_failure`.
- Apply a configurable cooldown (`PROVIDER_ALERT_COOLDOWN_SECONDS`, default 900 seconds) per category and model to prevent Telegram floods.
- A quota/failure event is a warning when a fallback succeeds; it is an urgent alert when all text providers fail.
- Send at most one recovery notice when the affected model succeeds again.
- Alert delivery is best-effort and must never block or fail the user request.
- Keep bounded in-memory state; a process restart intentionally permits a fresh alert if the failure recurs.

## Metrics

Track bounded counters for text attempts, quota failures, model failures, fallback successes, provider-unavailable outcomes, alerts sent, alerts suppressed by cooldown, and recoveries sent. Model names are controlled configuration values and are not user-provided labels.

## Rollback

Revert the monitoring commit. Provider request and failover behavior must remain usable if alert delivery is disabled or administrator delivery fails.

Status: implementation complete in working tree; focused alert-manager test passes. Full regression testing and deployment remain pending.

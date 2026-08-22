# GreyAI Response Delivery and Continuity Design

## Observation

The current `/help` viewer is bounded and owner-checked, but most other user-facing paths still call `truncate_text()` or send raw `reply_text`/`edit_text` values. The primary loss points are normal chat responses, the fallback chat branch, browser extraction, scheduled briefings, watcher alerts, command/admin listings, and inline results. `telegram_safe_html()` also truncates before formatting, so content can be lost before a sender can decide whether pagination is needed.

Conversation turns are persisted with owner/chat scope and secret redaction, but the in-memory mirror keeps only eight turns and 2,000 characters per turn. Reply recovery already uses the durable message-id index, which should remain the authority for cross-provider continuity. The existing natural-language interpreter already has a unified chat/task route, but routing is still primarily a single plan decision and does not expose a bounded continuity envelope to response delivery.

## Contract

1. Telegram text pages are at most 3,700 source characters before rendering and at most 3,900 rendered characters. Captions remain at most 1,024 characters and are never used for long content.
2. A short response remains one ordinary message. An oversized response becomes one viewer message with page number plus owner-scoped Previous/Next controls; it is not dumped as multiple static messages.
3. Viewer callback data uses a separate `page:` namespace, contains an opaque short viewer id, a bounded integer page, and a compact owner binding. Callback payloads are validated, limited to 64 bytes, expire after a short TTL, and cannot be read or advanced by another Telegram user.
4. Viewer state is bounded in count and age, contains only redacted display text, and is removed on expiry or replacement. It is not a global durable store for arbitrary secrets, cookies, credentials, or another user's output.
5. Help keeps its role/plan filtering and migrates to the shared viewer. Existing `help:` callbacks remain supported during a compatibility window.
6. Durable conversation records keep the complete redacted response up to the control-plane limit and store explicit metadata for operation id, response kind, viewer id when applicable, and provider/failover-neutral continuity. Prompts use bounded history and summaries/references, not unbounded output.
7. Adaptive behavior means a validated, deterministic decision layer can select chat, task, pagination, reply-context inclusion, and continuation based on request, permissions, plan, current operation state, and provider availability. It does not claim self-training, self-awareness, or unreviewed autonomous policy changes.
8. Authorization, privacy, rate limits, quota, domain policy, manual challenge handoff, and artifact safety remain unchanged.

## Implementation slices

- Add pure viewer/page helpers and a bounded in-memory registry.
- Add one shared async text-delivery helper for reply/edit/send targets, with plain-text fallback when formatting fails.
- Route chat, extraction, scheduled/watcher text, help, and selected list/admin outputs through the helper. Keep file/photo/document delivery unchanged except for caption bounds.
- Add callback routing for the shared viewer and preserve old help callbacks.
- Strengthen history metadata and continuation envelope at the natural-language response boundary.
- Add regression-first tests for page completeness, ownership, expiry, redaction, short-message compatibility, extraction/task output, reply context, and provider failover continuity.

## Rollback unit

The rollback unit is the single commit containing the viewer registry, shared sender, continuity metadata changes, tests, and README documentation. Reverting that commit restores the previous help callback and truncation behavior without changing the database schema or authorization policy.

## Metrics to monitor

Viewer creations, page navigation successes/failures, expired/foreign callbacks, long-output fallback sends, context retrieval successes, replies without recovered continuity, provider failover events, and Telegram handler errors.

## Postflight evidence — 2026-08-22

The implementation was released as commit `41f5ae5` (`Harden long responses and continuity`) on `main`. The local release gate passed with **277 tests**, compilation of the runtime modules, Ruff checks for the configured error and async rules, whitespace validation, and a repository diff secret scan. GitHub CI/CD run `32586970707` completed successfully, and Fly.io deployment run `32586970694` completed successfully.

The live health endpoint returned `status: operational` after deployment. It also reported that the service had automatically recovered after stability checks, with no active maintenance window. No Telegram Web login, user impersonation, or test message was used for verification.

The primary regression evidence covers complete page reconstruction, short-message compatibility, owner and expiry isolation, credential redaction, inline delivery, long chat replies, long search/extraction content, continuation-aware routing, durable assistant-result receipts, reply-context continuity, help entitlement filtering, and existing authorization and safety behavior. The rollback unit is commit `41f5ae5`; reverting it restores the previous runtime behavior without a database schema migration.

Production metrics to monitor are `text_viewers_created`, `text_viewer_navigation_success`, `text_viewer_navigation_rejected`, `text_viewer_expired`, `long_output_fallbacks`, context retrieval success/failure, assistant results recorded without a recovered continuity link, provider failover successes, Telegram handler errors, and any increase in viewer creation without corresponding navigation completion. The viewer registry remains bounded by count and TTL; durable conversation storage remains owner-and-chat scoped and redacted.

## Second postflight evidence — 2026-08-22

A follow-up report showed that long code-heavy MCP guidance could still appear as one clipped Telegram message. The root cause was identified in two places: the developer API-example Agent branch used a direct `edit_text` call, and the shared viewer split raw source characters before Markdown/HTML escaping, allowing code and HTML-like content to expand beyond Telegram’s limit after page construction.

Commit `9f5c1bc` fixes both boundaries. Developer API examples and developer key listings now use the shared viewer; viewer pages are split against the rendered Telegram size with a reserved header budget, preserving source content without a final hard slice. The native context now includes a bounded, explainable `request.next_step` signal for conversational response, Agent planning, prior-operation continuation after revalidation, or application validation. This signal guides the model but never authorizes side effects.

The post-fix local gate passed with **280 tests**, compilation, Ruff, whitespace, and secret checks. GitHub CI run `32588282486` and Fly.io deployment run `32588282458` both completed successfully. The live `/api/status` endpoint returned `status: operational`. No attached screenshots were reopened and no Telegram Web or impersonated-user testing was performed. The rollback unit is commit `9f5c1bc`; the documentation-only follow-up may be reverted separately.

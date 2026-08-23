# Whole-code audit working notes

This is an in-progress engineering note for the GreyAI recovery audit. It does not include credentials or attached screenshots.

## Baseline

- Repository: `mrphatom/Playwright-tg`
- Baseline before this audit: commit `907d2c3`, worktree clean, local suite `291 passed`, compile and focused Ruff checks passed.
- CI and Fly deployment for `907d2c3` completed successfully; live `/api/status` returned `status: operational`. This is deployment evidence only, not proof of the new uncommitted repairs.
- User explicitly requested an in-place whole-code audit and said not to use rollback as the solution.

## Confirmed defects reproduced and repaired locally

1. Standalone private-chat turns could inherit durable prior code/task history. `generate_chat_reply()` passed old history into the prompt, and the prompt ended as a continuation template. Added deterministic handling for short social turns, omitted unrelated history for those turns, and marked history/current request as untrusted, explicitly separated blocks. Regression tests cover `How are you?`, `I'm okay`, `huh?`, and stale `/start` code.
2. In-memory shared-chat history was keyed only by `chat_id`. When durable history was empty, a different user in a group could receive another user's in-memory context. Added `_chat_history_key(owner_user_id, chat_id)` and used it in remember/load paths while preserving private-chat compatibility. Regression test passes.
3. Durable contact/conversation redaction covered only narrow `label=value` forms. Natural-language login wording could persist a username and multi-word password. Added redaction patterns for quoted usernames/email addresses and `password is ...`/quoted multi-word values. Regression test passes.
4. Viewer secret redaction treated quoted safe placeholders as secrets because it checked the quotes as part of the candidate. It also redacted only the first token of quoted multi-word values, corrupting source syntax. Added quote-aware placeholder checks and an atomic quoted-value viewer regex. Regressions for `TOKEN = "YOUR_BOT_TOKEN_HERE"`, `API_KEY = "replace_with_your_key"`, and quoted real secrets pass.
5. `clean_grey_response()` silently removed repeated paragraphs. This violates the no-loss response contract. Removed content-dropping deduplication; regression confirms repeated paragraphs are preserved.

## Current focused verification

- Social/stale-context tests: passing.
- Group-history ownership tests plus existing continuity/failover tests: passing.
- Durable redaction tests: passing.
- Viewer placeholder/secret tests plus long viewer tests: passing.
- Compile and focused Ruff checks: passing before the latest focused test additions; rerun after final changes.

## Remaining audit targets

- Review every generated-response delivery path for raw `reply_text`/`edit_text` bypasses and malformed Markdown.
- Review full natural-language normalization/structured-output boundary and action validation.
- Review queue/watchers/schedules/download cleanup and operation-state consistency.
- Review dashboard/API authorization, CSRF, status payloads, and error paths.
- Add only evidence-backed regression tests; then run complete gate, review diff, commit once, push, monitor both workflows, and validate production health.

## Constraints

- Do not inspect the attached screenshots with the file tool again; use the user-visible findings already supplied and source-level tests.
- Do not send test messages through Telegram Web or act as the user.
- Do not add broad new capabilities during this recovery.
- Preserve security boundaries: no CAPTCHA/anti-bot evasion, no credential harvesting, no unrestricted executable delivery, no secret logging.
6. Shared-chat watchers were also keyed only by chat ID. A requester could list or stop another user’s watcher, and contextual watcher follow-ups could expose another user’s URL/condition. Added nullable `owner_user_id` migration, owner-aware save/list/deactivate paths, and passed the requester through natural-language follow-up and `/watchers`/`/stopwatch`. Existing private compatibility is preserved; new production-created watchers carry the requester owner. Focused watcher tests pass.
7. Download delivery had a state-integrity race: after a document was sent and the job/operation were marked successful, a failure editing the final status message entered the broad failure handler and reclassified the job as failed. The success status edit is now best-effort and cannot overwrite completed delivery state. A focused fake-Telegram regression passes.
8. Scheduled briefings had the same shared-chat ownership flaw: listing was chat-wide, and `/unschedule`/natural-language unschedule cancelled the in-memory task before ownership was verified. Listing and deactivation now accept the authenticated owner, and task cancellation occurs only after the owner-scoped database update succeeds. Schedule lifecycle tests pass.
9. Active saved-session selection was keyed only by chat ID. In shared chats, one user’s selected session name could enter another user’s interpreter context. It is now keyed using the same owner-plus-chat boundary as conversation history, and direct session deletion clears the scoped selection. 
10. Natural-language check delivery had two state/cleanup hazards: screenshot paths were assigned after the upload attempt, and deleting the progress message after successful delivery could enter the error branch. Screenshot cleanup is now in a `finally`, missing screenshots fail explicitly, and status deletion is best-effort after result delivery. 
11. The natural-language durable secret sanitizer was over-broad: an unquoted `password is ...` pattern consumed all following prose unless it matched a very narrow reminder clause. A failing boundary test reproduced the loss. The matcher now stops at common new-clause markers (`and then/ask/tell/show`, plus existing remember/save/keep), while still redacting quoted values and end-of-message multi-word credentials. Positive secret-redaction and boundary tests pass.
12. The queue worker could enter hard maintenance on an unexpected boundary exception (for example, a claim/database failure) without resolving the request future, leaving the originating handler waiting indefinitely. A focused fake-queue test reproduced the pending future. The worker now marks the queue/operation failed when possible, resolves the future with the original exception, then enters maintenance; `task_done()` remains guaranteed. The regression passes.
13. Manual challenge handoff regression: the browser retry wrapper enforced the ordinary 90-second command timeout even while a handoff was advertised for 600 seconds, so the task could be cancelled and its in-memory token removed before the user opened it. A focused regression reproduced this with a live operation record. The retry wrapper now extends only that operation’s deadline to the active handoff expiry plus a small completion margin. A second regression confirmed cancellation previously orphaned the shielded browser task; cancellation now cancels and awaits it. Dashboard coverage also confirms a fresh unexpired token renders the handoff page. Focused handoff tests pass.

14. Production handoff investigation found two runtime-only defects missed by same-process tests. First, the container launches `python bot.py`, so the live bot module is `__main__`; dashboard handlers lazily imported `bot`, creating a second module instance with an empty in-memory `manual_challenges` registry. Fresh handoff URLs therefore returned `handoff_not_found_or_expired` immediately. Dashboard stateful handlers now resolve the live runtime module, preferring `__main__` when it owns the bot state, and the regression test reproduces the script execution boundary. Second, python-telegram-bot defaults to serial update processing; `_process_natural_language` awaited long browser work inline, so a paused manual handoff prevented later normal chat updates from being dispatched. The application now uses bounded configurable concurrent update processing (2–64, default 16), with a regression test asserting the built application is concurrent. No Telegram Web or real CAPTCHA interaction was used. Focused and full test suites pass (315 tests).

## Latest focused verification
- Dashboard runtime-module handoff regression: passing.
- Telegram concurrent-update startup regression: passing.
- Full CI-equivalent suite: 315 passed, 2 warnings.
- Python compilation, dashboard F/I lint, diff check, and changed-diff secret scan: passing.

## Remaining deployment verification
- Commit the focused repair, push it, monitor CI and Fly deployment workflows, then confirm production health.
- Do not claim a real CAPTCHA handoff completion until the user independently opens a fresh production link and completes any challenge themselves.

## Constraints
- Do not inspect the attached screenshots with the file tool again; use the user-visible findings already supplied and source-level tests.
- Do not send test messages through Telegram Web or act as the user.
- Preserve security boundaries: no CAPTCHA/anti-bot evasion, no credential harvesting, no unrestricted executable delivery, no secret logging.

15. Follow-up production verification found a second handoff defect class: the backend acknowledged browser actions without first bringing the live Playwright page to the foreground, and closed or detached pages could surface as an unhelpful request failure. Manual actions now activate the live page when supported, preserve the bounded click/scroll/key/type allowlist, and return `live_page_unavailable` on browser-operation failure without falsely recording the action. The mobile handoff surface now uses a scrollable live-preview container, opens at bounded 250% zoom, supports 100–400% zoom controls, maps clicks against the scaled image bounds, refreshes after action settlement, prevents global keyboard shortcuts from hijacking the text field, and labels typing as input into the selected live-page field. Ordinary private-chat messages were also unnecessarily entering the slow unified interpreter and spawning progress messages; high-confidence chat routes now go directly through the existing conversational responder, while task-like requests retain the full interpreter. Common short social turns (`Cool`, `Talk?`, and `Good to know`) use the existing low-latency path. Focused interaction and chat regressions pass.
The direct conversational shortcut is intentionally limited to the recognized standalone-social set; general chat remains on the unified interpreter so LLM-classified Agentic tasks cannot be accidentally downgraded to chat.
16. Production `.onion` requests using `/allowdomain` were rejected before browser execution because `set_domain_policy()` persisted the administrator’s runtime allow rule in `domain_policies`, while `onion_host_allowed()` consulted only the environment variable `TOR_ONION_ALLOWLIST`. Natural-language model plans containing a bare `.onion` hostname were also rejected by URL validation because the normalizer expected an explicit scheme. Fixed both paths: onion authorization now applies persisted runtime allow/deny policies with deny precedence while retaining environment entries, and structured plans normalize bare onion hostnames to `https://` before the existing SSRF, tier, Tor, and allowlist checks. Synthetic-host regressions pass; no real onion destination was opened or tested.
17. Follow-up production evidence showed allowlist authorization was succeeding, but `.onion` checks still ended in the generic approved-source failure. The browser context only attaches Tor when the action list contains `proxy:tor`; the natural-language normalization path did not inject that action for an onion URL, so approved requests attempted direct navigation instead of Tor. Validated onion plans now automatically prepend `proxy:tor`, while the existing proxy-presence check still denies execution if `TOR_PROXY_SERVER` is unavailable. Focused onion routing and tier tests pass; no real hidden-service destination was opened.

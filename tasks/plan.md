# Spec: Natural-language Telegram requests

## Objective

Add plain-language Telegram messages to the existing `playwright-tg` bot without replacing its current slash commands, browser pipeline, encrypted sessions, or persistent watchers. A user should be able to write a request such as `Check https://example.com and tell me when Apple Pie is in stock`; the bot should interpret the request into a validated plan, run a one-time check or create a persistent watcher, and keep the user informed.

## Assumptions

The existing `google-generativeai==0.4.1` dependency remains in use for this first implementation rather than replacing the SDK. The existing `/check`, `/watch`, `/watchers`, `/stopwatch`, `/sessions`, and `/deletesession` handlers remain available. Natural-language requests are accepted only from the existing authorized-user boundary, and plain text must never execute arbitrary Python, shell commands, or unrestricted browser JavaScript.

The parser will return a small allowlisted intent schema: `mode` (`check`, `watch`, or `unknown`), `url`, `actions`, `condition`, and `interval_seconds`. The executor will reuse the existing `run_browser_task`, `execute_pipeline`, `save_watcher_to_db`, and `watcher_loop` functions. Watch mode will persist in SQLite and survive restarts exactly like `/watch`.

## Commands and verification

Run focused parser/validation tests with `pytest test_bot.py -q`. Run the repository CI-equivalent suite with `pytest test_bot.py -v`. Compile-check the module with `python3 -m py_compile bot.py`. Verify the deployed process through Fly.io status/logs and manually exercise one plain-language check and one watcher request in Telegram.

## Project structure

`bot.py` will contain the parser, plan validation, natural-language handler, and handler registration. `test_bot.py` will contain deterministic parser and validation tests. `docs/USAGE.md` will document natural-language examples while retaining the existing slash-command syntax.

## Safety boundaries

Always authorize before invoking Gemini or Playwright, validate HTTP/HTTPS URLs, apply the domain whitelist, cap intervals and output lengths, keep the browser action vocabulary allowlisted, and preserve the existing concurrency and timeout controls. Ask first before adding new external services or committing secrets. Never store API keys in source, allow arbitrary code execution, or silently replace the existing command interface.

## Acceptance criteria

1. Authorized plain text is routed to a natural-language handler.
2. Existing slash commands continue to register and operate.
3. A valid one-time request opens the URL and returns the existing screenshot/extraction response.
4. A valid watch request creates a SQLite-persisted watcher using the existing watcher engine.
5. Invalid, missing, unsupported, or disallowed URLs are refused without Gemini/Playwright execution.
6. Parser failures produce a clear Telegram response rather than a crash.
7. The active test suite passes and the deployed Fly machine starts with the browser pool ready.

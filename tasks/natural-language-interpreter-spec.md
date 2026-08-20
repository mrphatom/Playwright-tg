# Specification: Unified Natural-Language Command Interpreter

## Objective

Replace the current keyword-and-URL gate with one validated interpreter for authorized Telegram messages. The interpreter must map ordinary language to every existing bot capability without removing conversational chat or slash commands.

## Supported intents

The normalized command model supports `chat`, `check`, `watch`, `schedule`, `login`, `list_watchers`, `stop_watch`, `list_sessions`, and `delete_session`. Browser pipelines may contain the existing actions `type`, `click`, `wait`, `extract`, `ai_extract`, `save_session`, `load_session`, `proxy:on`, `condition_contains`, `condition_ai`, `type_username`, `type_password`, `click_login_next`, and `click_login_submit`.

## Interpretation contract

Every authorized non-command message is sent first to the unified interpreter. Credential-bearing login messages use a deterministic parser and never go to Gemini. Other messages may use Gemini structured JSON, followed by deterministic recovery for strongly recognizable check, watch, schedule, session, and management phrases. Model output is treated as untrusted data and must pass allowlist validation before execution.

## Safety boundaries

Authorization and rate limiting happen before interpretation. URLs are normalized only for missing HTTP(S) schemes, then validated and checked against the domain allowlist. Non-HTTP schemes, private/unsafe execution primitives, arbitrary shell/code, and unknown action names are rejected. Credentials are never logged or sent to Gemini; login actions are masked in status output and audit logs. Saved browser sessions remain encrypted and are only created when explicitly requested.

## Combined-message behavior

A message can contain a session operation plus a login or browser task, such as: `Create a session called x_login, then log in to https://x.com with username ... and password ..., and remember this login.` The interpreter compiles the session name into a validated `save_session:x_login` action and executes the login pipeline. If a message contains multiple independent operations that cannot be represented safely as one pipeline, the bot returns a precise clarification instead of guessing.

## Compatibility

All existing slash commands remain registered and retain their current behavior. Existing persistence, scheduler restoration, watcher restoration, encrypted session CRUD, browser timeouts, concurrency limits, domain checks, and audit logging remain intact.

## Testing strategy

Use pytest unit tests for each normalized intent, action allowlist, exact screenshot wording, combined login/session wording, scheme-less URLs, malformed model output, credential non-disclosure, unknown action rejection, and plain conversational fallback. Run `pytest test_bot.py -q`, `python3 -m py_compile bot.py`, and `git diff --check` before release.

## Success criteria

The exact screenshot request produces a login plan rather than the safe-web-request error. Natural language can express every documented command family, including management operations and action pipelines. Plain chat remains conversational. Invalid or ambiguous commands fail with a useful clarification. The complete test suite passes and the deployed Fly.io machine remains healthy.

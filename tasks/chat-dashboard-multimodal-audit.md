# Chat, dashboard, and multimodal audit

## Observed routing bottleneck

`natural_language_handler` currently creates a Telegram “Thinking” message, writes an operation, and then calls `parse_natural_language_intent` for every ordinary text message. When `ai_model` is configured, the parser always performs a Gemini call unless a deterministic management/login branch matches. Only after that call returns does the handler invoke `generate_chat_reply`, which performs a second Gemini call for ordinary conversation. This creates two sequential model calls for normal chat, plus Telegram edit and SQLite operations.

The fast-path hypothesis is to classify obvious conversational messages deterministically before invoking the task planner. Only task-like language, management commands, schedules, login requests, or web requests should enter the expensive intent parser. Chat replies should use one model call and a minimal status lifecycle. A lightweight bounded classifier must remain conservative: uncertain requests go to the existing planner.

## Website discovery gap

`is_web_automation_request` and deterministic web parsing require URL-like text. `parse_natural_language_intent` also rejects a model-produced check/watch URL unless the URL appears literally in the user message. This prevents requests such as “go to Google News and summarize it.” The safe change is to permit an AI-discovered URL only after `normalize_natural_language_plan` applies `is_valid_url` and `is_domain_allowed`, while retaining the existing browser SSRF protections.

## Dashboard loading gap

The dashboard client executes `me().then(() => { refresh(); queues(); ... })` without a catch or timeout. Any failed/hanging `/api/me`, `/api/operations`, `/api/referrals`, or admin polling request leaves the initial “connecting” and “Loading…” labels unchanged. Refresh also returns silently on a non-OK response. The fix should use bounded fetches, explicit success/error/empty states, a bootstrap catch/finally path, and polling that cannot create unhandled rejected promises.

## Multimodal gap

The bot currently imports only the deprecated `google-generativeai` SDK and has no Telegram voice/photo handlers. Current official Gemini documentation recommends `google-genai`/Interactions API and supports audio and image inputs via the Files API or bounded inline media. Telegram media must be downloaded through the bot API, size-limited, processed in a temporary file, and deleted in `finally`.

## Security and compatibility constraints

Authorization must run before media download or Gemini processing. Media-derived text must be treated as untrusted input and routed through the same chat/task boundary. Any discovered URL must pass `is_valid_url`, `is_domain_allowed`, and the existing browser execution checks. Do not claim an image or voice task was executed unless the browser path actually ran. Existing slash commands and explicit-URL behavior must remain unchanged.

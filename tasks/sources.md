# Source notes

The repository pins `python-telegram-bot==20.7`; its official MessageHandler documentation is https://docs.python-telegram-bot.org/en/v20.7/telegram.ext.messagehandler.html and its filters documentation is https://docs.python-telegram-bot.org/en/v20.7/telegram.ext.filters.html. The relevant pattern is a `MessageHandler` with combinable filters such as `filters.TEXT & ~filters.COMMAND`, registered after command handlers.

Google’s official structured output documentation is https://ai.google.dev/gemini-api/docs/structured-output. It documents JSON Schema structured output for the newer Google Gen AI SDK. The existing repository instead pins `google-generativeai==0.4.1`, whose inspected `GenerationConfig` signature supports temperature and token controls but not a visible response schema parameter. For compatibility, this implementation keeps the existing SDK, requests JSON-only output in the prompt, extracts fenced/plain JSON, validates the result strictly, and avoids introducing a dependency migration in the feature change.

The live Gemini API model discovery on 2026-08-20 returned `models/gemini-3.6-flash` and the API explicitly recommended that model after rejecting `gemini-2.5-flash` as unavailable to new users. The bot default was therefore changed to `gemini-3.6-flash`, with `GEMINI_MODEL` remaining overrideable through the environment.

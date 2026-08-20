# Multimodal implementation findings

Sources consulted on 2026-08-20:

- https://ai.google.dev/gemini-api/docs
- https://ai.google.dev/gemini-api/docs/image-understanding
- https://ai.google.dev/gemini-api/docs/audio
- https://ai.google.dev/gemini-api/docs/files
- https://core.telegram.org/bots/api
- https://github.com/google-gemini/deprecated-generative-ai-python

The current official Gemini documentation recommends the Interactions API and the unified Google GenAI Python SDK (`google-genai`). The legacy `google-generativeai` repository is deprecated and reached end of support on 2025-11-30.

Gemini supports multimodal text generation from images and audio. Current official examples use `client.files.upload(file=...)` followed by `client.interactions.create(...)` with typed `image` or `audio` input objects, or inline base64 for small media. The docs list supported image types PNG, JPEG, WEBP, HEIC, and HEIF. Supported audio types include WAV, MP3, AIFF, AAC, OGG Vorbis, and FLAC. Inline media has a 20 MB request-size limit; the Files API is preferred for reusable or larger media and files are automatically deleted after 48 hours.

Telegram Bot API messages can contain photos and voice messages. Bots use `getFile`/the python-telegram-bot download helpers to retrieve media; the standard Bot API download limit is 20 MB. Media handling must enforce tighter application caps, use temporary files only, delete them in `finally`, and never forward raw media to unrelated destinations.

Implementation implications: add a unified GenAI client only for multimodal processing initially, keep the existing text model as a compatibility path if necessary, route voice/image messages through a fast multimodal helper, then feed the bounded transcript/visual description into the same deterministic chat-versus-task router. Website discovery should be an explicit, constrained AI extraction step that returns an HTTPS URL; the existing `is_valid_url` and `is_domain_allowed` validators must run before browser execution. Never let model-discovered URLs bypass public-mode allowlists or SSRF checks.

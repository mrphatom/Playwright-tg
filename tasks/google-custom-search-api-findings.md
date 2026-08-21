# Google Custom Search JSON API integration findings

Retrieved 2026-08-21 from official Google documentation.

The API uses a single GET endpoint, `https://www.googleapis.com/customsearch/v1`, with required query parameters `key`, `cx`, and `q`. `cx` is the Programmable Search Engine ID; `key` is the Google API key. The request URL should remain within Google’s documented 2048-character limit. `num` accepts 1–10 results, and `start` supports pagination up to the first 100 results. The response is JSON with search metadata, engine metadata, and an `items` array containing result URLs, titles, and snippets.

Before calling the API, the owner must create a Programmable Search Engine in Google’s control panel and enable the relevant API/key in Google Cloud. API keys must be injected as deployment secrets, never committed or logged. The site-restricted endpoint is not appropriate for GreyAI’s broad web discovery: Google’s current documentation says that endpoint ceased serving traffic on January 8, 2025 and points customers toward Vertex AI Search.

Project seams identified from the repository:

- `bot.py` currently turns factual verification into `news.google.com/search?q=...` and generic live-web requests into `www.google.com/search?q=...` URLs.
- The natural-language routing and normalization pipeline already applies domain allowlisting, SSRF checks, quotas, timeouts, and audit logging.
- Provider metrics and alert/failover patterns already exist for Gemini and can be mirrored for search-provider failures.
- `test_bot.py` currently asserts Google URL conversion for factual and generic search requests; these tests should be changed or extended to assert API-provider routing while preserving the agent fallback for direct website tasks.
- `.env.example` and `fly.toml` have no Google search API settings yet.

Sources:

- https://developers.google.com/custom-search/v1/introduction
- https://developers.google.com/custom-search/v1/using_rest
- https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
- https://developers.google.com/custom-search/v1/site_restricted_api

## Implemented design

The integration adds a `GoogleCustomSearchProvider` around the official JSON endpoint. It accepts only server-injected `GOOGLE_CUSTOM_SEARCH_API_KEY` and `GOOGLE_CUSTOM_SEARCH_CX`, bounds query length and result count, uses an async timeout, validates the JSON shape and HTTP/URL fields, and records sanitized search metrics. It never opens the Google HTML search page when the API feature is enabled but unavailable; it reports a fail-closed provider error instead.

`GOOGLE_CUSTOM_SEARCH_ENABLED` defaults to false so existing deployments remain backward compatible until the owner creates a Programmable Search Engine and configures the API key and `cx`. When enabled, generic live-search and current-fact requests become `mode=search` plans; explicit website tasks and watchers retain the Playwright path. The health report exposes enabled/configured state, attempts, and failures.

Validation observed on 2026-08-21: 123 tests passed; Python compilation passed; the whitespace check passed after removing one README trailing-space issue. The next rollback unit is the single integration commit/PR; disabling `GOOGLE_CUSTOM_SEARCH_ENABLED` restores the legacy fallback behavior without removing the adapter.

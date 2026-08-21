# Specification: GreyAI Intelligent Browser Navigation

## Objective

GreyAI must interpret a user’s web task as a goal rather than a single URL fetch. For requests such as “What is the price of Bitcoin?”, Grey should select an appropriate allowed source, open the relevant page, inspect the page’s available controls and links, search or filter within the site when needed, follow the relevant result, extract the requested facts, and return a concise answer. This behavior must be domain-general and must not contain a CoinMarketCap-only implementation.

The browser should remain an execution tool owned by Grey’s application layer. The language model may propose a bounded navigation plan, but application code must validate the plan, enforce authorization/domain policy, cap steps and time, and treat all webpage content as untrusted data. Existing direct URL checks, search fallbacks, Tor gates, watcher behavior, screenshot requests, API checks, and Telegram delivery must remain compatible.

## Assumptions and boundaries

1. Read-only navigation, searching, clicking, waiting, and extraction are allowed when the user is authorized and the destination passes existing domain policy.
2. Form submission, account changes, purchases, messages, posts, file uploads, or other consequential actions remain confirmation-gated or use the existing explicit-action policy; intelligent navigation must not silently broaden those permissions.
3. The planner may use user intent and bounded page metadata, but webpage text, links, labels, and redirects are untrusted data and never become instructions for Grey.
4. The first release optimizes factual retrieval and page traversal. It does not promise that every anti-bot, login wall, CAPTCHA, infinite-scroll page, or client-rendered application can be automated.
5. If the planner fails or returns an unsafe/invalid plan, Grey must fail closed or fall back to the existing validated `ai_extract` path rather than execute arbitrary model output.

## Behavior contract

For an intelligent navigation request, the validated plan may contain a bounded sequence of navigation actions such as:

- open the selected URL or an existing allowed session page;
- inspect the current page for links, buttons, inputs, headings, and visible text summaries;
- enter a non-sensitive search query into a clearly identified search field when that is necessary to find the requested entity;
- click a semantically relevant link or button selected from the inspected page;
- wait for a bounded state change or page load;
- extract the requested facts from the resulting page;
- optionally capture a screenshot only when explicitly requested, when extraction is empty, or when a diagnostic artifact is required.

The planner must prefer semantic targets and stable attributes over brittle coordinates. Every click or input must be validated against the inspected page and limited to the current allowed origin unless an explicit, separately authorized navigation target is present. A navigation plan must have a maximum step count, a maximum number of same-page retries, a maximum cumulative action timeout, and a loop detector.

For “price of Bitcoin” style requests, Grey should be able to produce a structured retrieval plan similar to: select an allowed market-data source; open its search or asset route; search for Bitcoin if the asset is not already identified; follow the Bitcoin result; extract price, currency, timestamp, and source; return the result with the source URL. The exact path and labels must be discovered at runtime, not hard-coded for only one domain.

## Project structure

- `bot.py`: intent classification, navigation-plan normalization, browser execution, fallback routing, and Telegram result delivery.
- `docs/intelligent-navigation-spec.md`: this living feature specification.
- `test_bot.py`: unit and integration-style tests for plan validation, navigation execution, source fallback, loop limits, and screenshot policy.
- `README.md`: user-facing behavior and limitation documentation after implementation.

## Commands

```bash
cd /home/ubuntu/playwright-tg
.venv/bin/python -m py_compile bot.py dashboard.py api_contract.py starter_templates.py
.venv/bin/pytest test_bot.py test_platform.py test_dashboard.py -q
git diff --check
curl -fsS https://playwright-tg-mrphatom.fly.dev/api/status
```

## Code style

Keep model output as data and validate it before execution. A navigation-plan normalizer should produce the same internal action grammar used by the executor:

```python
{
    "mode": "check",
    "url": "https://example.com",
    "actions": [
        "inspect",
        "search:Bitcoin",
        "click:Bitcoin",
        "ai_extract:Return the current price and timestamp",
    ],
    "screenshot": False,
}
```

Action names, limits, and target values must be bounded and normalized before they reach Playwright. New behavior should be additive and preserve the existing `goto` plus extraction path for simple checks.

## Testing strategy

Tests must cover a normal domain-general navigation plan, an entity-search-and-click plan, a plan with an explicit screenshot request, malformed or unknown model actions, cross-origin or disallowed destinations, excessive step counts, navigation loops, empty extraction fallback, and preservation of direct path-specific checks. Tests should assert resulting state and validated actions rather than private implementation call order.

Where a real browser fixture is available, verify a local deterministic HTML fixture containing a search input, result link, and detail page. Do not use a real external site as the sole automated test because content and selectors change. Production verification should exercise the public health endpoint and, when authorized test credentials are available, a non-destructive Telegram request.

## Security requirements

- Enforce the existing allowlist, public-mode restrictions, Tor tier gates, and SSRF protections at the application boundary.
- Treat all LLM output and browser content as untrusted; do not execute JavaScript supplied by a page or model.
- Do not permit arbitrary CSS/XPath or coordinate actions from the model unless they pass a strict validator and are constrained to the current page.
- Do not submit forms or perform irreversible actions without the existing confirmation gate.
- Do not include tokens, cookies, credentials, or full private page contents in logs or model context.
- Record bounded, redacted navigation telemetry with operation correlation identifiers.

## Success criteria

1. A general navigation request can traverse at least one search control and one relevant link before extraction.
2. The same execution path works for different domains and label wording without a domain-specific handler.
3. The result is extracted text first; a screenshot is not sent unless explicitly requested or extraction is unusable.
4. Invalid, unsafe, cross-origin, looping, and over-budget plans are rejected or safely reduced to the existing fallback behavior.
5. Existing test coverage remains green, and new tests cover the normal, adversarial, boundary, and regression cases.
6. Production health remains operational after deployment, with navigation success/fallback/failure telemetry available for diagnosis.

## Open questions

None blocking implementation. The safe default is read-only intelligent navigation; consequential actions continue to use existing explicit confirmation and authorization rules.

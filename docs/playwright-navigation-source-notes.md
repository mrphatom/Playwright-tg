# Playwright navigation source notes

## Official sources

- https://playwright.dev/python/docs/locators — Playwright recommends user-facing locators such as `get_by_role`, `get_by_label`, `get_by_placeholder`, and `get_by_text`; locators auto-wait and are resolved against the current DOM before actions. The implementation uses bounded locator inspection and semantic labels instead of coordinates.
- https://playwright.dev/python/docs/navigations — Playwright supports navigation caused by page interactions, automatically waits for actionable targets, and recommends explicit navigation waits when clicks trigger navigation. The implementation waits for `domcontentloaded` after semantic clicks with a bounded timeout.
- https://playwright.dev/python/docs/api/class-locator — `locator.all()` and `all_inner_texts()` expose current matching elements; the implementation caps inspected elements and treats the returned page data as untrusted input.

## Implementation implications

The planner is allowed to select only bounded `search`, `click`, `wait`, `extract`, or `stop` decisions. Application code validates the decision, checks dangerous click terms, validates HTTP/HTTPS link destinations against the existing domain policy, and limits navigation steps. Webpage text, labels, hrefs, and model output remain data, not instructions.

# Google and Reddit Anti-Bot Compliance Audit

## Scope

This audit reviews GreyAI’s browser launch configuration, browser-context identity, proxy and Tor routing, HTTP download headers, Google and Reddit source routing, CAPTCHA handling, advertisement handling, pacing, retries, and domain-policy enforcement. The goal is transparent and standards-compliant reliability. The audit does not optimize GreyAI to evade detection, defeat anti-bot systems, bypass CAPTCHAs, or circumvent platform access controls.

## Findings

| Area | Finding | Decision |
|---|---|---|
| Chromium launch | The browser uses headless Chromium with only container-runtime flags (`--no-sandbox` and `--disable-dev-shm-usage`). | Retained for deployment compatibility; no automation-control flag is used. |
| Webdriver identity | Grey no longer injects JavaScript to hide `navigator.webdriver`. | Removed and verified. |
| Static browser identity | Grey no longer overrides the Playwright browser user-agent with a copied Chrome string. | Removed; the Playwright-managed browser identity is used. |
| CAPTCHA solving | The application does not invoke a CAPTCHA solver or bypass service. | The unused CAPTCHA-solver configuration surface was removed from the environment template. CAPTCHA challenges require manual review or a safe failure. |
| Advertisement handling | No ad blocker or advertisement-removal code is present in the audited paths. | Ads are not modified or suppressed. |
| Google routing | Generic search may use the configured Google Custom Search API; otherwise the existing approved search fallbacks are used. | No Google CAPTCHA or HTML anti-bot bypass is added. |
| Reddit routing | Subreddit monitoring uses normal allowlisted HTTPS navigation and existing watcher controls. | No Reddit-specific stealth, session harvesting, or rate-limit bypass is added. |
| Proxy and Tor routing | Explicit proxy/Tor actions remain available for approved non-restricted destinations and governed `.onion` access. | Google, Google News, and Reddit explicitly reject proxy/Tor routing to avoid evasion-like behavior. |
| URL and redirect controls | Every navigation and download candidate remains subject to HTTPS, SSRF, allowlist, redirect, timeout, quota, and authorization checks. | Retained. |
| Pacing | Existing bounded waits, queueing, retries, and provider/source fallback remain. | Reliability improvements are allowed; synthetic human-behavior simulation is not. |
| Failure handling | Access denied, CAPTCHA, login, or platform-block responses are surfaced as safe failures. | Retained. |

## Implementation changes

The audit added `proxy_routing_allowed_for_url()` and applies it before any explicit `proxy:on` or `proxy:tor` action. Google and Reddit hosts are rejected by that policy. The Chromium launch path no longer uses `--disable-blink-features=AutomationControlled`, and the browser context no longer masks webdriver identity or supplies a copied static user-agent. The unused `CAPSOLVER_API_KEY` application setting was removed from the public environment template because Grey does not integrate a CAPTCHA solver.

The README description was corrected from “stealth web automation” to “authorized web automation.” The public documentation now states that Grey does not mask webdriver identity, remove advertisements, bypass CAPTCHAs, defeat anti-bot systems, or evade platform security controls.

## Verification

The focused proxy-transparency regression passes. The full repository suite should be run before release, together with Python compilation, whitespace validation, and the staged credential scan. The expected behavior is that ordinary approved hosts can still use a configured proxy when an authorized action explicitly requests it, while Google, Google News, Reddit, and Reddit subdomains cannot use proxy or Tor routing through Grey’s browser action grammar.

## Remaining operational guidance

If Google or Reddit returns a CAPTCHA, consent page, login wall, rate-limit response, or access-denied page, Grey should report the state and stop or use an already configured approved source fallback. Operators should not add stealth flags, rotate proxies to evade a restriction, inject fake browser fingerprints, use CAPTCHA-solving services, or remove advertisements as a workaround. If higher reliability is needed, prefer the official Google Custom Search API, Reddit’s permitted access mechanisms, cached public sources, lower request frequency, and explicit administrator allowlisting.

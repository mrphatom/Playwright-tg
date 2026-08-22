# 🤖 Playwright-tg: Enterprise Web Automation Agent

![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-Pipeline-blue?logo=githubactions&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google_Gemini-3.6_Flash-8E44AD?logo=googlegemini&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

Playwright-tg is an asynchronous, AI-powered Telegram bot for authorized web automation. It fuses Playwright's headless browsing with Google Gemini 3.6 Flash, allowing you to control browser sessions, extract structured data via AI, schedule recurring web briefings, and run continuous background watchers—all via natural language messages or explicit commands in Telegram.

---

## Native Grey Intelligence

GreyAI’s identity and operating context are owned by the application rather than by the model provider. The runtime maintains a versioned native registry containing Grey’s name, description, owner relationship, commands, capabilities, execution processes, plan benefits, limitations, and current maintenance state. The same registry is used by ordinary chat, natural-language interpretation, multimodal input, inline mode, groups, channels, Secretary Mode, administrative workflows, developer integrations, watchers, schedules, and Agentic execution.

Every model call receives a bounded `grey.context.v1` envelope assembled from application-owned state. It can include the requesting user’s Telegram identity, role, plan, status, quota summary, authorized scopes, chat scope, reply metadata, durable conversation counts, operation receipts, platform health, active-user aggregates, and provider health. Conversation turns and contact logs remain owner-and-chat scoped. Grey can use the requester’s relevant history, but ordinary users never receive another user’s private history or hidden moderation data. Aggregate active-user and active-operation counts are telemetry only.

Gemini is an interchangeable inference provider, not Grey’s identity, memory store, authorization layer, command registry, or execution engine. Provider failover changes only the model/key slot; the native context, operation ID, durable receipt, role, plan, and Agentic state remain unchanged. Model output is untrusted and cannot grant roles, change plans, bypass quotas, reveal secrets, or execute side effects. The application validates the normalized intent and enforces authorization, plan gates, domain policy, confirmations, and Telegram permissions before any browser or messaging action.

> A literal weight-level training or fine-tuning pipeline is a separate concern. This release provides native Grey grounding and orchestration; weight-level tuning requires a curated consented dataset, provider support, evaluation gates, and a rollback plan.

### Navigable responses and bounded adaptive routing

GreyAI applies one response-delivery boundary across ordinary chat, natural-language Agent tasks, browser extraction, search results, scheduled briefings, watcher alerts, health and status reports, administrator feeds, developer event feeds, and inline answers. Short text stays in one normal Telegram message. When rendered content is too long for Telegram, GreyAI keeps the complete redacted response in a short-lived, owner-scoped viewer and presents **Previous** and **Next** buttons instead of silently clipping the tail or dumping a chain of static messages. Viewer callbacks are opaque, size-bounded, validated, expired automatically, and rejected for foreign or no-longer-authorized users. Screenshots and documents remain separate Telegram media deliveries with bounded captions.

The adaptive layer is deliberately bounded and application-owned. It combines the validated intent plan, deterministic route signals, the current user role and plan, chat scope, reply-to metadata, recent durable turns, operation receipts, provider availability, and existing policy gates to decide whether a message is conversational, a browser task, a continuation, or a request that needs clarification. Gemini keys are interchangeable inference providers: switching keys does not reset the owner-scoped conversation or operation receipt. This is native grounding and orchestration, not unsupported self-training or a claim of autonomous self-awareness.

## ✨ Core Features

- **👀 Continuous Watchers:** Monitor websites in the background. If a condition is met (e.g., "In Stock" or an AI evaluation), the bot alerts you and stops automatically. Watchers survive server reboots!
- **⏰ Scheduled Briefings:** Deliver timezone-aware daily or weekday summaries from multiple URLs, with persistent schedules restored after restarts.
- **💬 Conversational Chat:** Ask ordinary questions, brainstorm, discuss code, plan, or role-play without a command. Obvious chat messages use a single low-latency Gemini call and bypass the browser-task planner.
- **🗣️ Grey Private Chat:** In private chats Grey responds warmly to greetings, thanks, short emotional messages, teasing, playful insults, and casual profanity. It can use light witty banter without changing group tone or weakening task, authorization, privacy, or safety boundaries.
- **💼 Telegram Secretary Mode:** Telegram’s current user-facing label for connected-account automation. An owner can connect GreyAI as a Secretary Bot so Grey can participate directly in selected private chats. The original user message remains visible and Grey’s answer is sent as a separate message in the same conversation, subject to explicit read/reply permissions and the owner allowlist.
- **🔁 Chat-Agent Continuity:** Follow-up messages resolve the current chat’s durable watcher state before ordinary chat. Questions such as “What about the watch session we had on Reddit?” return the watcher ID, URL, interval, condition, and running or restored state instead of resetting the conversation or claiming that GreyAI has no access to its prior task.
- **🧠 Durable Conversation Memory:** Conversation turns and contact interactions are stored in SQLite by authorized owner and chat, so Gemini key failover, process restarts, and long gaps do not erase context. The prompt loads a bounded recent window from the durable log, while the underlying history remains available for future retrieval.
- **↩️ Telegram Reply Context:** When a user replies to an earlier GreyAI or contact message, Grey reads the replied-to text, author, and message ID automatically in normal, group, channel, and Secretary Mode flows.
- **🎙️ Multimodal Telegram Input:** Send voice notes for transcription or photos/screenshots for visual identification, OCR, and image-aware answers. Captions and interpreted media can enter either chat mode or the authorized browser-agent path.
- **🔎 Website Discovery and Live Lookup:** Say “go to Google News and summarize it”, “search for Apple and tell me the current iPhone price”, “find the latest headlines”, or “check availability” without manually typing a URL. When configured, generic searches use the approved Google Custom Search JSON API instead of scraping Google Search HTML. Direct website tasks still use the governed Playwright agent path, with domain allowlisting and SSRF-safe URL validation. Ordinary educational questions such as “How does Google search work?” remain conversational.
- **🧭 Intelligent Site Navigation:** Grey can inspect a page’s visible search fields, links, buttons, headings, and labels; search within the selected site; follow a relevant read-only result; handle client-rendered navigation with bounded waits; and extract from the resulting detail page. The same planner is domain-general, so it is not hard-coded to CoinMarketCap, Google, or any single website. For example, a Bitcoin-price request can open an approved market-data source, search for Bitcoin, click the Bitcoin result, and return the price and source URL instead of sending a full-page screenshot.
- **🧠 AI-Powered Extraction:** Query webpages using conversational prompts instead of fragile CSS selectors. Grey returns extracted text first and only sends a screenshot when explicitly requested or when extraction is unusable.
- **🛡️ Standards-Compliant Browsing:** Grey uses transparent browser behavior with bounded waits, retries, caching, and rate-aware backoff. It does not mask webdriver identity, remove advertisements, bypass CAPTCHAs, defeat anti-bot systems, or evade platform security controls. If a site requires login, consent, CAPTCHA, or manual review, Grey reports that limitation instead of attempting to circumvent it.
- **🧑‍💻 Manual Challenge Handoff:** When an approved browser task reaches a CAPTCHA, MFA, or security check, Grey pauses the live page and sends a private, short-lived Telegram handoff link with an inline button. The user can click, scroll, type an approved one-time code, complete the challenge on the site, and press “I’m done” to resume. Grey never solves or bypasses the challenge.
- **⏱️ Transparent Interaction Pacing:** Browser navigation waits for normal DOM readiness, allows a short deterministic client-render settle window, and uses bounded exponential retry backoff for transient failures. These waits are for page correctness and provider load, not behavioral camouflage; no cursor jitter, randomized human simulation, or anti-bot evasion is used.
- **⚙️ Button-Driven Settings:** `/settings` opens a personal settings panel. Persistent login and automatic encrypted session saving are paired and can be toggled together; manual challenge handoff can be enabled or disabled; saved sessions can be deleted and active handoffs cancelled from buttons without command arguments.
- **🔒 AES-Encrypted Sessions:** Login to sites once and save your session. Your cookies and tokens are encrypted at rest inside a local SQLite database.
- **⚡ Persistent Browser Pooling:** Maintains a warm background Chromium instance. Commands launch isolated tabs in milliseconds.
- **🛡️ Enterprise Security:** Role-aware authorization, rate limiting, server-side quotas, SSRF-resistant URL validation, encrypted sessions, strict command timeouts, audit records, and a required domain allowlist in public mode.
- **👥 Public User Lifecycle:** Persistent user records, user/developer/admin roles, active/limited/suspended/banned states, administrator search, ban/unban, role management, reports, and appeals.
- **🧩 Developer Mode:** Admin-granted developer access, Telegram approval requests, scoped one-time API keys, revocation, per-key rate limits, integration endpoints, and auditable developer activity.
- **💳 Entitlements:** Telegram Stars Pro upgrade flow with pre-checkout validation, idempotent receipts, durable entitlements, and an optional external HTTPS crypto checkout adapter.
- **🎁 Referrals:** Unique Telegram deep links, one-time attribution, self-referral and duplicate protection, verified-payment qualification, auditable quota rewards, user stats, and admin reporting.
- **📊 Operations Dashboard:** One-time Telegram-issued dashboard links, secure cookie sessions, CSRF-protected admin actions, redacted execution logs, saved-session metadata, health data, analytics, banned-user views, and live polling/websocket updates.
- **📬 Durable User Notifications:** Ban, unban, and appeal decisions enqueue bounded, secret-free Telegram notifications in an idempotent retryable SQLite outbox delivered by a background worker.
- **📰 Current-Fact Verification:** Questions such as “Have Cristiano Ronaldo officially announced his retirement?” are locally classified as verification tasks. If Custom Search is configured, GreyAI returns bounded Google API results without opening Google’s HTML search page; otherwise it preserves the legacy browser-search fallback.
- **📣 Role-Targeted Messaging:** Administrators can preview and confirm messages to users, developers, or administrators through `/massrole`, with server-side role resolution, banned-user exclusion, audit records, and revalidation at delivery time.
- **🟢 Maintenance Status:** Administrators can publish scheduled, degraded, or hard-maintenance updates with reasons. A scheduled maintenance entry accepts a future local time and IANA timezone; the persistent worker activates hard maintenance automatically at that time, pauses browser work, and enqueues one idempotent notification per user. Users can read the current status and timestamped history through Telegram and the public dashboard status endpoints.
- **⚖️ Priority Queueing:** Browser work uses a bounded priority queue. Administrators, Max, developers, and Pro users receive progressively higher priority; free users remain accepted fairly with an estimated wait time, while full queues fail safely.
- **🚨 Crash Failsafe:** Unhandled runtime failures capture a sanitized SQLite snapshot, transition the service to hard maintenance, pause browser work, enqueue a public incident notice, and send administrators a diagnostic incident and snapshot reference without exposing secrets.
- **🧰 Confirmation-Gated Administration:** Announcements, private messages, mass ban/unban, and mass appeal decisions use preview-first jobs with bounded target counts, short-lived single-use confirmation tokens, audit records, and per-item success/failure counts.
- **🧪 Cautious Activity Review:** Advisory AI risk review with confidence calibration. Strong signals create human-review work; the model never automatically bans, suspends, or limits an account.
- **🐳 Production Docker Ready:** Built-in volume mapping and memory limits for 24/7 VPS hosting.

---

## GreyAI Telegram Profile and Command Reference

### Description

GreyAI is a fast Telegram assistant for ordinary conversation and authorized web work. Users can send text, short voice notes, or screenshots. Natural-language chat stays on the low-latency chat path, while browsing, named websites, extraction, monitoring, scheduling, login, and account-management requests enter the governed agent path. The agent can discover a clearly named website such as Google News and intelligently traverse approved pages using visible semantic controls rather than relying on one hard-coded domain. Generic live searches use the server-side Google Custom Search JSON API when enabled; direct website tasks continue through the browser agent and every discovered URL passes HTTPS, domain-allowlist, SSRF, quota, timeout, and concurrency checks before browser execution. Read-only navigation can search and click approved results; consequential actions remain confirmation-gated.

### Information and permissions

Free accounts receive the configured base quota. Pro and Max plans are purchased with Telegram Stars and provide 1,000 and 5,000 monthly execution units respectively. Active administrators can use administrator and developer capabilities. Ordinary users can request developer access with `/devrequest`; only an administrator can approve it. Developer API keys are scoped, rate-limited, owner-bound, hashed at rest, revocable, and never shown in listings.

When a new key is created, GreyAI sends a separate, clearly labeled message containing the key ID, label, scope, rate limit, and secret. That one-time message self-deletes after the configured copy window, which defaults to 90 seconds and is bounded between 30 and 300 seconds. The secret is not stored in plaintext and is never displayed again. If the message is exposed, revoke the key immediately with `/revokekey <key_id>` and create a replacement.

### User commands

| Command | Purpose | Example |
|---|---|---|
| `/start` | Start GreyAI and receive your referral link | `/start` |
| `/help` | Show the in-Telegram feature and command guide | `/help` |
| `/settings` | Open button-driven personal settings for sessions and challenge handoffs | `/settings` |
| `/health` | View bot, browser, database, watcher, schedule, and resource health | `/health` |
| `/check` | Run a browser workflow with URL and pipe-separated actions | `/check https://example.com \| ai_extract:Summarize this page` |
| `/watch` | Monitor a page on an interval until a condition is met | `/watch 300 https://example.com \| condition_contains:In Stock` |
| `/watchers` | List active monitors | `/watchers` |
| `/stopwatch` | Stop one monitor | `/stopwatch <watcher_id>` |
| `/schedule` | Create a recurring web briefing | `/schedule 08:00 Europe/London weekdays https://example.com \| Summarize` |
| `/schedules` | List recurring briefings | `/schedules` |
| `/unschedule` | Cancel one briefing | `/unschedule <schedule_id>` |
| `/sessions` | List encrypted browser-session metadata | `/sessions` |
| `/deletesession` | Delete one saved browser session | `/deletesession <name>` |
| `/dashboard` | Request a secure one-time operations-dashboard link | `/dashboard` |
| `/upgrade` | Compare Pro and Max benefits and choose a plan with Telegram buttons | `/upgrade max` for a direct invoice |
| `/referral` | Create or display your invite link | `/referral` |
| `/report` | Submit a support or safety report | `/report The browser task failed` |
| `/appeal` | Open an account review appeal | `/appeal Please review my limitation` |
| `/support` | Request platform support | `/support` |
| `/paysupport` | Request payment support | `/paysupport` |
| `/terms` | View the platform terms notice | `/terms` |
| `/stars` or `/starsbalance` | Administrator-only live bot Stars balance and bounded recent revenue report | `/stars` |

### Natural-language examples

```text
Summarize the latest Google News headlines

Check https://example.com and tell me whether Apple Pie is in stock

Have Cristiano Ronaldo officially announced his retirement?

Every weekday at 08:00 Europe/London, summarize Google News and send me one briefing

Log in to my saved session and extract the order status

What can you do?

Download this permitted public-domain file and send it to me: https://archive.org/download/example/example.txt
```

### Lawful file retrieval and Telegram delivery

Grey can retrieve and send permitted artifacts as Telegram files when the source is public-domain, openly licensed, officially published, or otherwise authorized by the user. A request may contain a direct URL, but it can also simply say “find the song,” “get the public-domain movie,” “download the official app archive,” or “send me the PDF.” Grey searches approved providers, follows bounded result/detail links, selects the best permitted candidate, streams the artifact with a bounded byte and time limit, validates the content type and magic bytes, checks archives for traversal, symlinks, executable members, excessive expansion, and suspicious compression ratios, then sends the validated file and deletes its temporary copy.

Free users are blocked from file retrieval by default. Pro users receive limited access with smaller per-file and daily-job limits; Max, developer, and administrator accounts receive higher but still bounded limits. Each job has an estimated maximum, a short initial status, throttled progress updates with an approximate ETA when the source exposes a size, and a final success or safe failure message. Jobs are rate-limited, concurrency-limited, persisted with a redacted receipt, and audited by source host rather than credential-bearing URL.

Grey will not distribute pirated music, films, applications, books, or other copyrighted material without permission. It will not bypass DRM, paywalls, logins, CAPTCHAs, malware defenses, download restrictions, or platform blocks. For an explicitly approved login, Grey can pause at a site-owned CAPTCHA or MFA screen and hand the live page to the authorized user through a short-lived Telegram link; the user completes the challenge and Grey resumes only after the user presses the handoff completion control.
Executable installers, scripts, and executable archive members are blocked by default. Public mode uses the same HTTPS, SSRF, domain-allowlist, Tor, quota, timeout, and authorization policy as browser checks. `.onion` hosts remain explicit administrator-allowlisted destinations; dark-web marketplaces are not seeded into the default allowlist.

### Voice notes and screenshots

A voice note is transcribed and then routed as either a normal chat message or an agent task. A photo or screenshot is analyzed for visible text, labels, prices, objects, and UI intent before the same routing decision. Media is authorized before download, size-limited, processed with the dedicated multimodal model, bounded as untrusted context, and deleted from temporary storage after processing. Agent task receipts are added to the bounded chat history so later conversational replies know that an application-owned task was accepted and can distinguish confirmed state from information requiring a fresh browser check.

In a private chat, Grey uses a warmer persona than it uses in groups or inline mode. Very short social messages such as greetings, thanks, “cry”, or playful profanity can receive an immediate local response, keeping the conversation responsive during provider latency or quota pressure. Longer or ambiguous messages still use the private-chat Gemini prompt. Grey may be witty, but it does not use slurs, threats, coercion, or encouragement of self-harm or violence, and private-chat personality instructions never suppress a recognized browser-agent task.

Conversation memory is keyed to the authorized Telegram owner and chat rather than to a Gemini API key. Each Gemini fallback therefore receives the same durable conversation context. Contact logs retain bounded message metadata, reply relationships, and timestamps; credential-like strings are redacted before persistence. The active prompt window is controlled by `CHAT_CONTEXT_TURNS`, while the in-process mirror is bounded by `CHAT_MEMORY_TURNS` and `CHAT_MEMORY_TEXT_CHARS` to improve continuity without unbounded memory growth.

### Telegram Secretary Mode (Telegram Business Bot)

Telegram currently labels this capability **Secretary Mode** in the BotFather interface. It allows an authorized account to connect GreyAI as a Secretary Bot for selected private chats. The feature is disabled unless `BUSINESS_MODE_ENABLED=true`, and every connection is stored with its `is_enabled`, `can_read_messages`, and `can_reply` rights. Grey rejects connections that are disabled, cannot read messages, cannot reply, belong to a bot, or are owned by a Telegram account outside `ALLOWED_TELEGRAM_USERS`. Secretary-mode work uses the owner’s quota, role, audit trail, and developer permissions while sending the response back to the external chat through Telegram’s `business_connection_id`.

**Enable the setting shown in your screenshot:** open `@BotFather`, select `@GreyBrowserBot`, open **Bot Settings**, open **Mode Settings**, and switch **Secretary Mode** from red/off to blue/on. Telegram’s current official user flow then uses **Settings → Chat Automation**: select GreyAI, choose which chats it may access, and grant permission to read and reply. Telegram’s current documentation does not require Telegram Premium for Secretary Bot connections. The owner must still be an authorized GreyAI user. After connection, the contact’s original message stays visible and Grey’s response appears as a separate message in that same chat. Disconnecting the bot, pausing Chat Automation, or revoking either permission stops processing immediately. Voice notes, photos, screenshots, plain-language chat, web lookups, and watcher alerts use the same permission checks.

### Developer commands and API integration

| Command | Permission | Purpose |
|---|---|---|
| `/devrequest <reason>` | Any active user | Submit a developer-access request to an administrator |
| `/devrequests` | Administrator | Review open and resolved developer requests |
| `/grantdeveloper <telegram_id>` | Administrator | Approve an open request and grant developer access |
| `/denydeveloper <telegram_id> [reason]` | Administrator | Deny an open request |
| `/revokedeveloper <telegram_id>` | Administrator | Revoke developer access and all active keys; administrators cannot be downgraded |
| `/newkey <name> check` | Active developer or administrator | Create a scoped API key and receive its secret once |
| `/devkeys` | Active developer or administrator | List labeled metadata without secret values |
| `/revokekey <key_id>` | Key owner or authorized administrator | Revoke a key |
| `/developerstats` | Active developer or administrator | View key activity, request counts, and denied events |
| `/devevents [after_event_id]` | Active developer or administrator | Read an owner-scoped, cursor-based event feed with secret-like payload keys redacted |

Other Telegram bots use the versioned integration API:

```http
POST https://playwright-tg-mrphatom.fly.dev/api/v1/check
Authorization: Bearer gai_live.key_...
Content-Type: application/json
```

```json
{
  "url": "https://example.com",
  "extract": "Return the current availability and price."
}
```

The initial enabled scope is `check`. Keys are not dashboard credentials, and the API applies the same URL, SSRF, quota, timeout, concurrency, and redaction controls as Telegram browser tasks.

### Administrator command groups

Administrators can search users, inspect account state, ban and unban accounts, review reports and appeals, resolve tickets, inspect referral activity, grant and revoke administrator roles, review developer requests, approve or deny developer access, inspect platform health, publish maintenance status, view the live Telegram Stars balance and a bounded revenue summary, open the owner-side withdrawal handoff, and manage the domain policy. The available commands include `/admin`, `/admin_user`, `/grantadmin`, `/revokeadmin`, `/ban`, `/unban`, `/banned`, `/reports`, `/appeals`, `/review`, `/resolveappeal`, `/referrals`, `/analytics`, `/stars`, `/starsbalance`, `/withdrawstars`, `/announce`, `/dm`, `/massdm`, `/massrole`, `/maintenance`, `/status`, `/maintenance_log`, `/massban`, `/massunban`, `/massappeals`, `/confirmbulk`, `/devrequests`, `/grantdeveloper`, `/denydeveloper`, `/revokedeveloper`, `/domains`, `/allowdomain`, `/disallowdomain`, and `/resetdomain`.

### Announcements, private messages, and bulk moderation

`/announce <message>` previews an announcement to active users. `/dm <telegram_id> <message>` previews a private message to one existing user, while `/massdm <id1,id2,...> | <message>` previews a bounded multi-recipient message. `/massrole <users|developers|admins> | <message>` resolves the selected role on the server and previews a role-targeted message. These commands do not deliver immediately. The preview includes a job ID and short-lived token; delivery starts only after the administrator sends `/confirmbulk <job_id> <token>`. Confirmation is single-use and expires after ten minutes.

The same workflow protects `/massban <id1,id2,...> | <reason>`, `/massunban <id1,id2,...>`, and `/massappeals <resolved|denied> <appeal_id1,appeal_id2,...> | <resolution>`. Administrator accounts are never valid mass-ban targets. A completed job reports processed, succeeded, and failed items, and every state change is written to the audit trail. `/banned` lists currently banned accounts, `/analytics` shows banned users, suspicious users awaiting human review, top users by operations, top referrers, and the most risky accounts, and `/stars` shows the bot’s current Telegram Stars balance plus received, outgoing/refund, net, and recent transaction totals for the latest bounded transaction window. `/withdrawstars` checks the live balance and opens the official owner-side Telegram/Fragment withdrawal handoff. It never collects wallet addresses, seed phrases, private keys, or Telegram 2FA passwords. The Stars report does not expose payer identities or transaction IDs.

Ban, unban, and appeal decisions send the affected user a bounded notification through the durable outbox. Successful Pro and Max purchases also enqueue an idempotent payment alert to every configured administrator, including the plan, amount, customer Telegram ID, and payment order ID. Notifications use unique idempotency keys, bounded retries, exponential backoff, and HTML escaping; internal risk evidence, API keys, cookies, prompts, and administrator-only details are not included.

### Maintenance, queueing, and incident recovery

Administrators publish status updates with `/maintenance <mode> | <public message> | <reason>`, where mode is `operational`, `scheduled`, `degraded`, or `hard_maintenance`. Users can use `/status` and `/maintenance_log` to view the current state and timestamped history. The public dashboard exposes `GET /api/status` and `GET /api/status/events`; authenticated administrators can inspect queue depth and the latest sanitized crash snapshot at `/api/admin/runtime`.

Administrators can schedule an automatic maintenance start with the fourth pipe-delimited field:

```text
/maintenance scheduled | Database migration begins soon | Planned database migration | 2026-08-22 14:30 Europe/London
```

The time must be in the future and use `YYYY-MM-DD HH:MM IANA/Timezone`. Before activation, `/maintenance_status` reports the planned start. At the configured time, GreyAI changes the state to `hard_maintenance`, pauses browser tasks, and sends durable user notifications. To cancel a scheduled window before it starts, use `/maintenance operational | Service restored | Scheduled window cancelled`.

Browser tasks are admitted to a bounded priority queue. The response includes an estimated wait when work is queued. Chat replies, status reads, and maintenance commands bypass the browser queue. If an unhandled application failure reaches the global error boundary, GreyAI records a sanitized snapshot, enters hard maintenance, pauses browser work, sends a safe incident notice through the notification outbox, and alerts administrators with the incident and snapshot identifiers. Recovery should be performed by an administrator after reviewing the logs and can be published with `/maintenance operational | Service restored | Incident resolved`.

### Versatile domain allowlist

The public-mode allowlist is no longer limited to a small hard-coded set. It combines deployment-seeded patterns from `ALLOWED_DOMAINS` with persistent administrator-managed runtime policies. An exact pattern such as `example.com` allows the apex domain and its subdomains for backward compatibility. A wildcard pattern such as `*.example.com` allows subdomains but not the apex domain. A deny rule always takes precedence over environment and runtime allow rules.

Administrators can expand access without redeploying:

```text
/allowdomain docs.python.org
/allowdomain *.wikipedia.org
/domains
```

They can block a host or family of subdomains immediately:

```text
/disallowdomain tracking.example.com
/disallowdomain *.untrusted.example
```

`/resetdomain <pattern>` removes the runtime override and returns to the deployment-seeded policy. Every mutation is normalized, parameterized, administrator-only, and written to the audit log. Patterns cannot contain paths, ports, credentials, IP addresses, or arbitrary wildcards. These controls expand the hostname policy only; HTTPS validation, private-network and SSRF blocking, quotas, timeouts, concurrency limits, and user authorization remain mandatory.

---

## 🚀 Quickstart (VPS / Production)

1. **Clone the repository**
   ```bash
   git clone [https://github.com/mrphatom/Playwright-tg.git](https://github.com/mrphatom/Playwright-tg.git)
   cd Playwright-tg
   ```

2. **Configure environment variables**  
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_API_KEY_2=your_optional_fallback_gemini_api_key
   GEMINI_API_KEY_3=your_optional_fallback_gemini_api_key_3
   GEMINI_API_KEY_4=your_optional_fallback_gemini_api_key_4
   # Optional approved generic search provider; keep the API key server-side.
   GOOGLE_CUSTOM_SEARCH_ENABLED=true
   GOOGLE_CUSTOM_SEARCH_API_KEY=your_google_cloud_api_key
   GOOGLE_CUSTOM_SEARCH_CX=your_programmable_search_engine_id
   GOOGLE_CUSTOM_SEARCH_TIMEOUT_SECONDS=8
   GOOGLE_CUSTOM_SEARCH_RESULTS=5
   GEMINI_MODEL=gemini-3.6-flash
   MULTIMODAL_MODEL=gemini-3.5-flash-lite
   CHAT_TIMEOUT_SECONDS=20
   # Show a persistent “still thinking” message only when work exceeds this delay.
   PROGRESS_FEEDBACK_DELAY_SECONDS=1.2
   # Transparent page-readiness timing; these are bounded usability waits, not camouflage.
   BROWSER_INITIAL_SETTLE_MS=750
   BROWSER_ACTION_SETTLE_MS=250
   BROWSER_READY_TIMEOUT_MS=4000
   BROWSER_RETRY_BACKOFF_SECONDS=2
   CHAT_CONTEXT_TURNS=32
   CHAT_MEMORY_TURNS=48
   CHAT_MEMORY_TEXT_CHARS=6000
   TEXT_VIEWER_TTL_SECONDS=900
   TEXT_VIEWER_MAX_ACTIVE=256
   TEXT_VIEWER_BODY_LENGTH=3300
   MEDIA_TIMEOUT_SECONDS=45
   MEDIA_MAX_BYTES=12000000
   MAX_MEDIA_CONTEXT_CHARS=6000
   NOTIFICATION_WORKER_ENABLED=true
   BULK_ACTIONS_ENABLED=true
   DEVELOPER_EVENTS_ENABLED=true
   MAX_BULK_TARGETS=200
   NOTIFICATION_POLL_SECONDS=5
   ROLE_MESSAGING_ENABLED=true
   MAINTENANCE_FEATURE_ENABLED=true
   CRASH_FAILSAFE_ENABLED=true
   QUEUE_ENABLED=true
   QUEUE_MAX_DEPTH=100
   QUEUE_POLL_SECONDS=1
   QUEUE_ETA_FLOOR_SECONDS=5
   ALLOWED_TELEGRAM_USERS=123456789,987654321
   # Seed domains; administrators can add exact hosts or *.subdomain patterns at runtime.
   ALLOWED_DOMAINS=github.com,amazon.com,news.ycombinator.com,google.com,coinmarketcap.com,duckduckgo.com,bing.com,brave.com,startpage.com,reddit.com
   DUCKDUCKGO_ENABLED=true
   BING_SEARCH_ENABLED=true
   BRAVE_SEARCH_ENABLED=true
   STARTPAGE_SEARCH_ENABLED=true
   # Self-hosted Tor is optional outside Fly; keep local startup disabled unless tor is installed.
   TOR_LOCAL_ENABLED=false
   TOR_LOCAL_SOCKS_PORT=9050
   TOR_PUBLIC_FALLBACK_ENABLED=false
   TOR_ONION_ACCESS_ENABLED=false
   TOR_PROXY_SERVER=
   TOR_ONION_ALLOWLIST=
   SESSION_ENCRYPTION_KEY=your_aes_encryption_key
   ```

3. **Configure Google Custom Search (optional but recommended for generic live search)**
   Create a [Programmable Search Engine](https://programmablesearchengine.google.com/controlpanel/create), configure the sites or web scope you want it to search, and copy its Search Engine ID (`cx`). In [Google Cloud Console](https://console.cloud.google.com/), enable the Custom Search JSON API and create a restricted API key. Do not commit the key to Git or place it in Telegram messages. The API route is used for generic search and current-fact lookups; direct URLs still use Playwright.

   For Fly.io, inject the two secrets rather than placing them in `fly.toml`:
   ```bash
   fly secrets set GOOGLE_CUSTOM_SEARCH_API_KEY="..." GOOGLE_CUSTOM_SEARCH_CX="..." -a playwright-tg-mrphatom
   ```
   Then set `GOOGLE_CUSTOM_SEARCH_ENABLED=true` in the deployment environment and redeploy. If the API is enabled but its credentials are missing or its quota is exhausted, GreyAI fails closed and does not retry Google’s HTML search page.

4. **Optional Tor routing**
   GreyAI’s Fly image includes a self-hosted Tor client. When `TOR_LOCAL_ENABLED=true`, the entrypoint starts Tor as a client, binds `SocksPort` to loopback `127.0.0.1:9050`, waits for readiness, exports the private SOCKS endpoint to GreyAI, and shuts Tor down with the container. `.onion` access is a separate feature: it requires `TOR_ONION_ACCESS_ENABLED=true`, an explicit `TOR_ONION_ALLOWLIST`, an eligible Max account or developer/admin role, and the same URL/action safety checks. Green/free and Pro users are denied `.onion` access. Public-web Tor fallback requires `TOR_PUBLIC_FALLBACK_ENABLED=true`; it does not expose a public SOCKS port.

5. **Deploy with Docker Compose**
   ```bash
   docker compose up -d --build
   ```

---

## 🎮 Command Manual

Commands are chained using the pipe (`|`) character.

### Basic & AI Automation (`/check`)
Execute a one-off pipeline to interact with a page and take a screenshot when requested. Natural-language checks return targeted extraction first and preserve exact URL paths.

For public search tasks, GreyAI can use Google Custom Search when configured, then browser-based DuckDuckGo, Bing, Brave Search, and Startpage fallbacks. Crypto price requests prefer Google and CoinMarketCap before the public search fallbacks.

- **Available Actions:** `type:<css>=<text>`, `click:<css>`, `wait:<sec>`, `extract:<css>`, `ai_extract:<prompt>`, `save_session:<name>`, `load_session:<name>`.

```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com) | ai_extract:Summarize top stories
```

---

### Continuous Background Watchers (`/watch`)
Tell the bot to check a page on an interval until a specific condition is met.

- **Available Conditions:** `condition_contains:<text>`, `condition_ai:<prompt>`.
- **Watcher Commands:**
  - `/watchers` - List your active background watchers.
  - `/stopwatch <ID>` - Manually kill a watcher by its ID.

```bash
/watch 300 [https://example.com/store](https://example.com/store) | condition_contains:In Stock
```

---

### Scheduled Morning Briefings (`/schedule`)
Create a persistent recurring briefing from one or more pages:

```bash
/schedule 08:00 Europe/London weekdays combined https://example.com/news,https://example.org/releases | Summarize the important updates
```

You can also write the request naturally:

```text
Every weekday at 08:00 Europe/London, summarize https://example.com/news and https://example.org/releases and send me one morning briefing
```

Use `/schedules` to list active briefings and `/unschedule <ID>` to stop one.

---

### Administrator Advertising Campaigns (`/adcreate`)

GreyAI administrators can create bounded advertising campaigns for explicit groups or channels where the bot is already present and has permission to post. This is a separate administrator-controlled path and does not remove the ordinary `/enablegreyai` requirement for user-initiated shared-chat conversations.

Campaigns are previewed first and never post until the administrator confirms the short-lived, single-use token. Each delivery re-checks membership and posting permission. Channels require GreyAI to be an administrator with permission to post; groups and supergroups do not require GreyAI to be a group administrator, but GreyAI must remain a member and be able to send messages. Targets are never discovered automatically. If a channel removes GreyAI, removes its posting permission, or a group removes its send permission, the affected delivery is disabled and administrators receive a dedicated permission-loss alert.

```text
/adcreate <chat_id|@username,...> | <title> | <ad copy or ai: brief> | <repeat/timing options>
/confirmad <campaign_id> <token>
/adlist
/cancelad <campaign_id>
/resumead <campaign_id>
```

For example:

```text
/adcreate -1001234567890,@mychannel | GreyAI | ai: introduce GreyAI's browser assistant | 3 times every 2 hours
```

The `ai:` form uses the existing Gemini failover pool to draft concise plain-text copy. Administrators can also provide exact copy instead. Repetition is bounded, the minimum interval is one hour by default, per-chat cooldowns prevent repeated posts from different campaigns, and delivery receipts plus failures are persisted in SQLite. Interrupted sends are reclaimed safely, retried a bounded number of times, and surfaced as failed rather than retried forever. Campaigns resume after a container restart and can be cancelled with `/cancelad`.

As a safety circuit breaker, a campaign is automatically paused after the configured number of distinct targets lose membership or posting permission. The default `AD_CAMPAIGN_PERMISSION_LOSS_PAUSE_THRESHOLD=2` prevents a broad campaign from repeatedly hitting inaccessible chats. Each affected target receives a durable administrator alert, and the pause is recorded with a reason and timestamp. After reviewing Telegram membership and send rights, the administrator can restore access and run `/resumead <campaign_id>`; GreyAI resets only the permission-loss dead letters for the interrupted occurrence and retries that occurrence. Set the threshold to `0` to disable automatic pausing.

Natural language is supported in the administrator’s private GreyAI chat, for example: `Create an ad campaign for chat ID -1001234567890, write an honest ad about GreyAI, and send it 3 times every 2 hours.` GreyAI returns a preview and requires `/confirmad` before any external message is posted. Ordinary users and shared-chat invocations cannot create campaigns.

---

### Encrypted Session Management
Log in once and reuse the state safely.

- **Save Session Example:**
  ```bash
  /check [https://github.com/login](https://github.com/login) | type:#login_field=me@mail.com | type:#password=123 | click:input[name="commit"] | wait:5 | save_session:github_main
  ```
- **Session Management:**
  - `/sessions` - List all your saved encrypted sessions.
  - `/deletesession <name>` - Securely wipe a session from the database.

---

## 🌐 Public Release Configuration

Public mode is enabled only when `PUBLIC_MODE=true`. Before opening the bot to outside users, set a strong `SESSION_ENCRYPTION_KEY`, configure `ADMIN_TELEGRAM_IDS`, set `DASHBOARD_BASE_URL`, and replace the starter `ALLOWED_DOMAINS` list with the domains you are prepared to permit. Public mode rejects private and loopback IP targets and refuses to operate with an empty domain allowlist. Search-provider fallbacks remain allowlist-controlled; the Fly deployment runs Tor privately on loopback for public fallback, and `.onion` hosts remain unavailable to Green/free and Pro users.

Users can request a one-time dashboard link with `/dashboard`, create an invite link with `/referral`, compare Pro and Max benefits with `/upgrade` and select either plan using Telegram buttons, or use `/upgrade pro` and `/upgrade max` for direct invoices. They can also purchase access using Telegram Stars, submit `/report` and `/appeal` tickets, request developer access with `/devrequest`, and use ordinary natural-language messages for the existing browser, watcher, schedule, session, chat, and developer-management capabilities. Ordinary conversation is routed directly to the chat path; browser-like wording, named-site requests, schedules, watchers, and management actions remain on the task path. Administrators can use `/admin`, `/admin_user`, `/ban`, `/unban`, `/grantadmin`, `/revokeadmin`, `/reports`, `/appeals`, `/referrals`, `/review`, `/resolveappeal`, `/devrequests`, `/grantdeveloper`, `/denydeveloper`, `/revokedeveloper`, `/adcreate`, `/confirmad`, `/adlist`, `/cancelad`, and `/resumead` for the advertising campaign workflow.

The current plans are **Pro at 750 Stars for 30 days with 1,000 monthly execution units** and **Max at 1,000 Stars for 30 days with 5,000 monthly execution units**. Telegram payment validation checks the selected plan, amount, currency, invoice owner, and idempotent payment record before granting the matching entitlement.

Voice notes and photos are processed only after normal authorization checks. Media is size-limited, downloaded to a temporary file, sent to the dedicated `MULTIMODAL_MODEL` with a 45-second `MEDIA_TIMEOUT_SECONDS` deadline, and deleted in a `finally` cleanup path. Short Telegram voice notes use `audio/ogg`; screenshots use `image/jpeg` or `image/png`. Quota exhaustion is reported as provider capacity, not as a false “try a shorter voice note” message. The interpreted content is bounded and marked as untrusted before it reaches either chat or agent routing. The dashboard uses bounded requests, explicit degraded/error states, and retrying polling rather than leaving panels indefinitely stuck on “Loading…”.

Set `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, and `GEMINI_API_KEY_4` to enable the ordered four-key provider pool. The primary key is used first; quota/rate-limit responses, timeouts, transport failures, and Gemini 5xx responses temporarily cool down that key and retry the text request with `TEXT_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`) before advancing through the remaining healthy keys. Media uses the same four-key pool with the dedicated `MULTIMODAL_MODEL`. The failover is per model call, so an active Playwright page, saved session, operation ID, and task state are not restarted. Only the non-secret provider slot is retained for diagnostics; key values are never logged, displayed, or placed in request URLs. Invalid-request and authentication errors are not treated as quota exhaustion. Gemini rate limits are applied per project rather than per key, so independent projects are recommended when separate quota capacity is required [1].

### Automatic failsafe recovery

When an unexpected unhandled runtime failure triggers GreyAI’s hard-maintenance failsafe, the service now starts a guarded recovery monitor. It checks the SQLite control plane, queue state, browser connectivity, and Telegram Bot API connectivity at a bounded interval. If the browser process is unavailable, the monitor performs a controlled browser-pool restart before evaluating recovery.

GreyAI must pass three consecutive health probes by default before the state changes back to operational. A failed probe resets the stability counter and keeps browser work paused. Recovery is atomic, recorded in the timestamped maintenance history with the original incident ID, and followed by durable user notifications plus an administrator recovery alert. `/health` exposes probe, probe-failure, and automatic-recovery counters.

The monitor never clears administrator-declared or scheduled maintenance. Those states carry their own source metadata and remain under explicit administrator control. Set `AUTO_RECOVERY_ENABLED=false` to disable the monitor while retaining the crash failsafe, or adjust `AUTO_RECOVERY_POLL_SECONDS`, `AUTO_RECOVERY_STABILITY_CHECKS`, and `AUTO_RECOVERY_PROBE_TIMEOUT_SECONDS` within their bounded ranges.

### Automated provider alerts

GreyAI sends rate-limited Telegram alerts to the configured administrators in `ADMIN_TELEGRAM_IDS` (or the private-mode administrator list). It reports two categories: quota exhaustion and model failure. Each category is deduplicated per model using `PROVIDER_ALERT_COOLDOWN_SECONDS`, which defaults to 900 seconds. A fallback success is reported as degraded service; a complete provider failure is reported as an incident. After a recorded incident, the next successful request can send one recovery notification. Alerts never include API keys, prompts, user IDs, URLs, raw exception text, response bodies, or authorization headers, and delivery failures never block the user request. Set `PROVIDER_ALERTS_ENABLED=false` to disable Telegram notifications while retaining in-process counters. `/health` exposes bounded provider-attempt, quota-failure, model-failure, fallback-success, alert, suppression, and recovery counters.

### Shared-chat invocation

GreyAI supports three Telegram invocation surfaces.

### Natural-language subreddit monitoring

Reddit subreddit references are supported without a literal URL. For example, `Head to Reddit r/forhire and watch every 1 hour for a new web developer post` resolves safely to `https://www.reddit.com/r/forhire`, creates a persistent watcher, and checks it hourly. `every hour` is accepted as shorthand for one hour. When the condition is detected, GreyAI sends the watcher alert and stops that watcher according to the existing watcher lifecycle. Reddit is explicitly allowlisted in the production configuration; all existing HTTPS, host, public-mode, and SSRF checks still apply.

GreyAI does not claim that a monitor exists unless the watcher is successfully created. Use `/watchers` to list active monitors and `/stopwatch <watcher_id>` to cancel one. **Inline mode** lets an authorized user type `@GreyBrowserBot your question` in any private chat, group, or channel and choose GreyAI’s answer. Enable this in [@BotFather](https://t.me/BotFather) with `/setinline`; inline results are intended for questions and read-only public-page explanations, while full browser tasks should remain in the private GreyAI chat [2] [3].

**Groups are opt-in.** When GreyAI joins a group, it remains disabled by default and sends an onboarding message explaining the opt-in flow. A group administrator or GreyAI administrator must run `/enablegreyai` to activate it for that chat. After activation, GreyAI ignores ordinary group messages and responds only to explicit `@GreyBrowserBot` mentions, replies to GreyAI messages, and `/ask <request>`. `/disablegreyai` turns group handling off. Authorization, quotas, rate limits, and the existing domain and SSRF protections still apply.

If you cannot add GreyAI to a group:
1. **Check group permissions:** Many groups restrict adding bots to administrators only. If you are not an administrator, you may need to ask one to add `@GreyBrowserBot`.
2. **Check bot settings:** Ensure "Allow Groups" is enabled in [@BotFather](https://t.me/BotFather) under **Bot Settings > Group Visibility**.
3. **Privacy Mode:** By default, Telegram’s **Privacy Mode** is enabled. This is why GreyAI only sees messages that mention it or start with a command. Do not disable Privacy Mode unless you want the bot to receive every message in the group (not recommended for this agent).

**Channels are allowlisted and disabled by default.** To enable them, set `CHANNEL_INVOCATION_ENABLED=true`, add GreyAI as a channel administrator, and have the GreyAI administrator run `/allowchannel <channel_id>`; static IDs may also be supplied through `ALLOWED_CHANNEL_IDS`. Use `/disallowchannel <channel_id>` to revoke access. Channel posts must explicitly mention `@GreyBrowserBot` and are limited to read-only webpage extraction. Login, form filling, saved sessions, schedules, and interactive browser actions are rejected. The bot does not silently read private conversations or unmentioned group/channel content. Telegram delivers channel-post updates to bots through the Bot API update stream, while inline results can be selected in chats, groups, and channels [2] [3] [4].

A referral is attributed through Telegram’s `/start` deep-link parameter and cannot be reassigned. It becomes qualified only after the invited user completes a verified Telegram Stars Pro purchase. The referrer and invited user then receive configurable one-time quota bonuses recorded in the referral reward ledger. Invalid codes, self-referrals, duplicate attribution, and referrals from banned accounts are rejected.

Telegram Stars are the in-Telegram payment rail for digital access. Crypto checkout is intentionally provider-gated through `CRYPTO_CHECKOUT_URL`; do not accept wallet addresses, seed phrases, or client-provided payment claims as proof of payment.

### Developer Mode and Telegram Integrations

Developer access is granted only by an administrator. Configured administrators automatically inherit developer capabilities while retaining the stored `admin` role and all administrator permissions. Ordinary users must send a direct request with `/devrequest <what you are building>`. The bot stores the request and notifies the configured administrator IDs. The administrator then approves with `/grantdeveloper <Telegram ID>` or denies it with `/denydeveloper <Telegram ID> [reason]`. Removing access with `/revokedeveloper <Telegram ID>` also revokes all active keys for that user.

After approval, a developer can create a scoped integration key with `/newkey <name> check`, list metadata with `/devkeys`, revoke a key with `/revokekey <key_id>`, and view usage with `/developerstats`. The plaintext key is shown once only. The database stores a keyed digest, never the secret itself, and all key lifecycle and authorization events are audited. The initial release enables only the `check` scope; `watch`, `schedule`, and `sessions` remain reserved until their ownership and delivery semantics are reviewed.

Other Telegram bots should send the key as a bearer credential to Grey’s versioned API. The live origin is `https://playwright-tg-mrphatom.fly.dev`; a redacted machine-readable contract is available at [`GET /api/v1/docs`](https://playwright-tg-mrphatom.fly.dev/api/v1/docs).

```http
POST https://playwright-tg-mrphatom.fly.dev/api/v1/check
Authorization: Bearer gai_live.key_...
Content-Type: application/json
```

```json
{
  "url": "https://example.com",
  "extract": "Return the current availability and price."
}
```

The response contains an operation ID, page title, validated URL, and redacted extraction results. It does not contain browser cookies, saved sessions, credentials, screenshots, or internal stack traces. The API enforces the same public-mode domain allowlist, SSRF protections, platform quota, browser timeout, and concurrency controls as Telegram commands. Each key also has a configurable per-minute limit, defaulting to 30 requests and capped server-side at 120.

Developers can ask Grey directly for a verified integration example with natural language, such as “give me Python code to integrate my GreyAI API key,” or use the administrator-approved `/help` and `/newkey` flows. Grey returns examples from the application-owned API contract rather than asking Gemini to invent an endpoint. Developers can manage keys through the authenticated dashboard at `GET /api/v1/keys`, `POST /api/v1/keys`, and `DELETE /api/v1/keys/{key_id}`. Usage is available at `GET /api/v1/developer/stats`. The owner-scoped developer event feed is available in Telegram through `/devevents [after_event_id]`; use the last returned event ID as the next cursor. Dashboard mutations require the existing secure session and CSRF token; bearer keys do not grant dashboard privileges. The only currently enabled bearer-key scope is `check`; watcher, schedule, session, login, form-filling, screenshot, and arbitrary Telegram endpoints are not part of the public API contract.

## References

[1]: https://ai.google.dev/gemini-api/docs/rate-limits "Gemini API rate limits"
[2]: https://core.telegram.org/bots/api "Telegram Bot API"
[3]: https://core.telegram.org/api/bots/inline "Telegram inline queries"
[4]: https://core.telegram.org/bots/features "Telegram bot features"

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, database schema, and advanced usage scenarios.

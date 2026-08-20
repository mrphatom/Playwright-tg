# 🤖 Playwright-tg: Enterprise Web Automation Agent

![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-Pipeline-blue?logo=githubactions&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google_Gemini-3.6_Flash-8E44AD?logo=googlegemini&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

Playwright-tg is an asynchronous, AI-powered Telegram bot for stealth web automation. It fuses Playwright's headless browsing with Google Gemini 3.6 Flash, allowing you to control browser sessions, extract structured data via AI, schedule recurring web briefings, and run continuous background watchers—all via natural language messages or explicit commands in Telegram.

---

## ✨ Core Features

- **👀 Continuous Watchers:** Monitor websites in the background. If a condition is met (e.g., "In Stock" or an AI evaluation), the bot alerts you and stops automatically. Watchers survive server reboots!
- **⏰ Scheduled Briefings:** Deliver timezone-aware daily or weekday summaries from multiple URLs, with persistent schedules restored after restarts.
- **💬 Conversational Chat:** Ask ordinary questions, brainstorm, discuss code, plan, or role-play without a command. Obvious chat messages use a single low-latency Gemini call and bypass the browser-task planner.
- **🎙️ Multimodal Telegram Input:** Send voice notes for transcription or photos/screenshots for visual identification, OCR, and image-aware answers. Captions and interpreted media can enter either chat mode or the authorized browser-agent path.
- **🔎 Website Discovery:** Say “go to Google News and summarize it” without manually typing a URL. Gemini may resolve a clearly named website, but the resulting HTTPS URL must still pass the public domain allowlist and SSRF-safe browser validation.
- **🧠 AI-Powered Extraction:** Query webpages using conversational prompts instead of fragile CSS selectors.
- **🔒 AES-Encrypted Sessions:** Login to sites once and save your session. Your cookies and tokens are encrypted at rest inside a local SQLite database.
- **⚡ Persistent Browser Pooling:** Maintains a warm background Chromium instance. Commands launch isolated tabs in milliseconds.
- **🛡️ Enterprise Security:** Role-aware authorization, rate limiting, server-side quotas, SSRF-resistant URL validation, encrypted sessions, strict command timeouts, audit records, and a required domain allowlist in public mode.
- **👥 Public User Lifecycle:** Persistent user records, user/developer/admin roles, active/limited/suspended/banned states, administrator search, ban/unban, role management, reports, and appeals.
- **🧩 Developer Mode:** Admin-granted developer access, Telegram approval requests, scoped one-time API keys, revocation, per-key rate limits, integration endpoints, and auditable developer activity.
- **💳 Entitlements:** Telegram Stars Pro upgrade flow with pre-checkout validation, idempotent receipts, durable entitlements, and an optional external HTTPS crypto checkout adapter.
- **🎁 Referrals:** Unique Telegram deep links, one-time attribution, self-referral and duplicate protection, verified-payment qualification, auditable quota rewards, user stats, and admin reporting.
- **📊 Operations Dashboard:** One-time Telegram-issued dashboard links, secure cookie sessions, CSRF-protected admin actions, redacted execution logs, saved-session metadata, health data, analytics, banned-user views, and live polling/websocket updates.
- **📬 Durable User Notifications:** Ban, unban, and appeal decisions enqueue bounded, secret-free Telegram notifications in an idempotent retryable SQLite outbox delivered by a background worker.
- **📰 Current-Fact Verification:** Questions such as “Have Cristiano Ronaldo officially announced his retirement?” are locally classified as verification tasks, converted into an allowlisted Google News search, and answered with extracted text and an optional screenshot instead of a false “I cannot access the internet” response.
- **📣 Role-Targeted Messaging:** Administrators can preview and confirm messages to users, developers, or administrators through `/massrole`, with server-side role resolution, banned-user exclusion, audit records, and revalidation at delivery time.
- **🟢 Maintenance Status:** Administrators can publish scheduled, degraded, or hard-maintenance updates with reasons. Users can read the current status and timestamped history through Telegram and the public dashboard status endpoints.
- **⚖️ Priority Queueing:** Browser work uses a bounded priority queue. Administrators, Max, developers, and Pro users receive progressively higher priority; free users remain accepted fairly with an estimated wait time, while full queues fail safely.
- **🚨 Crash Failsafe:** Unhandled runtime failures capture a sanitized SQLite snapshot, transition the service to hard maintenance, pause browser work, enqueue a public incident notice, and send administrators a diagnostic incident and snapshot reference without exposing secrets.
- **🧰 Confirmation-Gated Administration:** Announcements, private messages, mass ban/unban, and mass appeal decisions use preview-first jobs with bounded target counts, short-lived single-use confirmation tokens, audit records, and per-item success/failure counts.
- **🧪 Cautious Activity Review:** Advisory AI risk review with confidence calibration. Strong signals create human-review work; the model never automatically bans, suspends, or limits an account.
- **🐳 Production Docker Ready:** Built-in volume mapping and memory limits for 24/7 VPS hosting.

---

## GreyAI Telegram Profile and Command Reference

### Description

GreyAI is a fast Telegram assistant for ordinary conversation and authorized web work. Users can send text, short voice notes, or screenshots. Natural-language chat stays on the low-latency chat path, while browsing, named websites, extraction, monitoring, scheduling, login, and account-management requests enter the governed agent path. The agent can discover a clearly named website such as Google News, but every discovered URL still passes HTTPS, domain-allowlist, SSRF, quota, timeout, and concurrency checks before browser execution.

### Information and permissions

Free accounts receive the configured base quota. Pro and Max plans are purchased with Telegram Stars and provide 1,000 and 5,000 monthly execution units respectively. Active administrators can use administrator and developer capabilities. Ordinary users can request developer access with `/devrequest`; only an administrator can approve it. Developer API keys are scoped, rate-limited, owner-bound, hashed at rest, revocable, and never shown in listings.

When a new key is created, GreyAI sends a separate, clearly labeled message containing the key ID, label, scope, rate limit, and secret. That one-time message self-deletes after the configured copy window, which defaults to 90 seconds and is bounded between 30 and 300 seconds. The secret is not stored in plaintext and is never displayed again. If the message is exposed, revoke the key immediately with `/revokekey <key_id>` and create a replacement.

### User commands

| Command | Purpose | Example |
|---|---|---|
| `/start` | Start GreyAI and receive your referral link | `/start` |
| `/help` | Show the in-Telegram feature and command guide | `/help` |
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
| `/upgrade` | View or purchase Pro or Max with Telegram Stars | `/upgrade max` |
| `/referral` | Create or display your invite link | `/referral` |
| `/report` | Submit a support or safety report | `/report The browser task failed` |
| `/appeal` | Open an account review appeal | `/appeal Please review my limitation` |
| `/support` | Request platform support | `/support` |
| `/paysupport` | Request payment support | `/paysupport` |
| `/terms` | View the platform terms notice | `/terms` |

### Natural-language examples

```text
Summarize the latest Google News headlines

Check https://example.com and tell me whether Apple Pie is in stock

Have Cristiano Ronaldo officially announced his retirement?

Every weekday at 08:00 Europe/London, summarize Google News and send me one briefing

Log in to my saved session and extract the order status

What can you do?
```

### Voice notes and screenshots

A voice note is transcribed and then routed as either a normal chat message or an agent task. A photo or screenshot is analyzed for visible text, labels, prices, objects, and UI intent before the same routing decision. Media is authorized before download, size-limited, processed with the dedicated multimodal model, bounded as untrusted context, and deleted from temporary storage after processing.

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

Administrators can search users, inspect account state, ban and unban accounts, review reports and appeals, resolve tickets, inspect referral activity, grant and revoke administrator roles, review developer requests, approve or deny developer access, inspect platform health, publish maintenance status, and manage the domain policy. The available commands include `/admin`, `/admin_user`, `/grantadmin`, `/revokeadmin`, `/ban`, `/unban`, `/banned`, `/reports`, `/appeals`, `/review`, `/resolveappeal`, `/referrals`, `/analytics`, `/announce`, `/dm`, `/massdm`, `/massrole`, `/maintenance`, `/status`, `/maintenance_log`, `/massban`, `/massunban`, `/massappeals`, `/confirmbulk`, `/devrequests`, `/grantdeveloper`, `/denydeveloper`, `/revokedeveloper`, `/domains`, `/allowdomain`, `/disallowdomain`, and `/resetdomain`.

### Announcements, private messages, and bulk moderation

`/announce <message>` previews an announcement to active users. `/dm <telegram_id> <message>` previews a private message to one existing user, while `/massdm <id1,id2,...> | <message>` previews a bounded multi-recipient message. `/massrole <users|developers|admins> | <message>` resolves the selected role on the server and previews a role-targeted message. These commands do not deliver immediately. The preview includes a job ID and short-lived token; delivery starts only after the administrator sends `/confirmbulk <job_id> <token>`. Confirmation is single-use and expires after ten minutes.

The same workflow protects `/massban <id1,id2,...> | <reason>`, `/massunban <id1,id2,...>`, and `/massappeals <resolved|denied> <appeal_id1,appeal_id2,...> | <resolution>`. Administrator accounts are never valid mass-ban targets. A completed job reports processed, succeeded, and failed items, and every state change is written to the audit trail. `/banned` lists currently banned accounts, and `/analytics` shows banned users, suspicious users awaiting human review, top users by operations, top referrers, and the most risky accounts.

Ban, unban, and appeal decisions send the affected user a bounded notification through the durable outbox. Notifications use unique idempotency keys, bounded retries, exponential backoff, and HTML escaping; internal risk evidence, API keys, cookies, prompts, and administrator-only details are not included.

### Maintenance, queueing, and incident recovery

Administrators publish status updates with `/maintenance <mode> | <public message> | <reason>`, where mode is `operational`, `scheduled`, `degraded`, or `hard_maintenance`. Users can use `/status` and `/maintenance_log` to view the current state and timestamped history. The public dashboard exposes `GET /api/status` and `GET /api/status/events`; authenticated administrators can inspect queue depth and the latest sanitized crash snapshot at `/api/admin/runtime`.

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
   GEMINI_MODEL=gemini-3.6-flash
   MULTIMODAL_MODEL=gemini-3.5-flash-lite
   CHAT_TIMEOUT_SECONDS=20
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
   ALLOWED_DOMAINS=github.com,amazon.com,news.ycombinator.com,reddit.com
   SESSION_ENCRYPTION_KEY=your_aes_encryption_key
   ```

3. **Deploy with Docker Compose**
   ```bash
   docker compose up -d --build
   ```

---

## 🎮 Command Manual

Commands are chained using the pipe (`|`) character.

### Basic & AI Automation (`/check`)
Execute a one-off pipeline to interact with a page and take a screenshot.

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

Public mode is enabled only when `PUBLIC_MODE=true`. Before opening the bot to outside users, set a strong `SESSION_ENCRYPTION_KEY`, configure `ADMIN_TELEGRAM_IDS`, set `DASHBOARD_BASE_URL`, and replace the starter `ALLOWED_DOMAINS` list with the domains you are prepared to permit. Public mode rejects private and loopback IP targets and refuses to operate with an empty domain allowlist.

Users can request a one-time dashboard link with `/dashboard`, create an invite link with `/referral`, purchase Pro or Max access with `/upgrade pro` or `/upgrade max` using Telegram Stars, submit `/report` and `/appeal` tickets, request developer access with `/devrequest`, and use ordinary natural-language messages for the existing browser, watcher, schedule, session, chat, and developer-management capabilities. Ordinary conversation is routed directly to the chat path; browser-like wording, named-site requests, schedules, watchers, and management actions remain on the task path. Administrators can use `/admin`, `/admin_user`, `/ban`, `/unban`, `/grantadmin`, `/revokeadmin`, `/reports`, `/appeals`, `/referrals`, `/review`, `/resolveappeal`, `/devrequests`, `/grantdeveloper`, `/denydeveloper`, and `/revokedeveloper`.

The current plans are **Pro at 750 Stars for 30 days with 1,000 monthly execution units** and **Max at 1,000 Stars for 30 days with 5,000 monthly execution units**. Telegram payment validation checks the selected plan, amount, currency, invoice owner, and idempotent payment record before granting the matching entitlement.

Voice notes and photos are processed only after normal authorization checks. Media is size-limited, downloaded to a temporary file, sent to the dedicated `MULTIMODAL_MODEL` with a 45-second `MEDIA_TIMEOUT_SECONDS` deadline, and deleted in a `finally` cleanup path. Short Telegram voice notes use `audio/ogg`; screenshots use `image/jpeg` or `image/png`. Quota exhaustion is reported as provider capacity, not as a false “try a shorter voice note” message. The interpreted content is bounded and marked as untrusted before it reaches either chat or agent routing. The dashboard uses bounded requests, explicit degraded/error states, and retrying polling rather than leaving panels indefinitely stuck on “Loading…”.

Set `GEMINI_API_KEY_2`, `GEMINI_API_KEY_3`, and `GEMINI_API_KEY_4` to enable the ordered four-key provider pool. The primary key is used first; quota/rate-limit responses, timeouts, transport failures, and Gemini 5xx responses temporarily cool down that key and retry the text request with `TEXT_FALLBACK_MODEL` (default `gemini-3.5-flash-lite`) before advancing through the remaining healthy keys. Media uses the same four-key pool with the dedicated `MULTIMODAL_MODEL`. The failover is per model call, so an active Playwright page, saved session, operation ID, and task state are not restarted. Only the non-secret provider slot is retained for diagnostics; key values are never logged, displayed, or placed in request URLs. Invalid-request and authentication errors are not treated as quota exhaustion. Gemini rate limits are applied per project rather than per key, so independent projects are recommended when separate quota capacity is required [1].

### Automated provider alerts

GreyAI sends rate-limited Telegram alerts to the configured administrators in `ADMIN_TELEGRAM_IDS` (or the private-mode administrator list). It reports two categories: quota exhaustion and model failure. Each category is deduplicated per model using `PROVIDER_ALERT_COOLDOWN_SECONDS`, which defaults to 900 seconds. A fallback success is reported as degraded service; a complete provider failure is reported as an incident. After a recorded incident, the next successful request can send one recovery notification. Alerts never include API keys, prompts, user IDs, URLs, raw exception text, response bodies, or authorization headers, and delivery failures never block the user request. Set `PROVIDER_ALERTS_ENABLED=false` to disable Telegram notifications while retaining in-process counters. `/health` exposes bounded provider-attempt, quota-failure, model-failure, fallback-success, alert, suppression, and recovery counters.

### Shared-chat invocation

GreyAI supports three Telegram invocation surfaces.

### Natural-language subreddit monitoring

Reddit subreddit references are supported without a literal URL. For example, `Head to Reddit r/forhire and watch every 1 hour for a new web developer post` resolves safely to `https://www.reddit.com/r/forhire`, creates a persistent watcher, and checks it hourly. `every hour` is accepted as shorthand for one hour. When the condition is detected, GreyAI sends the watcher alert and stops that watcher according to the existing watcher lifecycle. Reddit is explicitly allowlisted in the production configuration; all existing HTTPS, host, public-mode, and SSRF checks still apply.

GreyAI does not claim that a monitor exists unless the watcher is successfully created. Use `/watchers` to list active monitors and `/stopwatch <watcher_id>` to cancel one. **Inline mode** lets an authorized user type `@GreyBrowserBot your question` in any private chat, group, or channel and choose GreyAI’s answer. Enable this in [@BotFather](https://t.me/BotFather) with `/setinline`; inline results are intended for questions and read-only public-page explanations, while full browser tasks should remain in the private GreyAI chat [2] [3].

**Groups are opt-in.** A group administrator must run `/enablegreyai`. After activation, GreyAI ignores ordinary group messages and responds only to explicit `@GreyBrowserBot` mentions, replies to GreyAI messages, and `/ask <request>`. `/disablegreyai` turns group handling off. Authorization, quotas, rate limits, and the existing domain and SSRF protections still apply.

**Channels are allowlisted and disabled by default.** To enable them, set `CHANNEL_INVOCATION_ENABLED=true`, add GreyAI as a channel administrator, and have the GreyAI administrator run `/allowchannel <channel_id>`; static IDs may also be supplied through `ALLOWED_CHANNEL_IDS`. Use `/disallowchannel <channel_id>` to revoke access. Channel posts must explicitly mention `@GreyBrowserBot` and are limited to read-only webpage extraction. Login, form filling, saved sessions, schedules, and interactive browser actions are rejected. The bot does not silently read private conversations or unmentioned group/channel content. Telegram delivers channel-post updates to bots through the Bot API update stream, while inline results can be selected in chats, groups, and channels [2] [3] [4].

A referral is attributed through Telegram’s `/start` deep-link parameter and cannot be reassigned. It becomes qualified only after the invited user completes a verified Telegram Stars Pro purchase. The referrer and invited user then receive configurable one-time quota bonuses recorded in the referral reward ledger. Invalid codes, self-referrals, duplicate attribution, and referrals from banned accounts are rejected.

Telegram Stars are the in-Telegram payment rail for digital access. Crypto checkout is intentionally provider-gated through `CRYPTO_CHECKOUT_URL`; do not accept wallet addresses, seed phrases, or client-provided payment claims as proof of payment.

### Developer Mode and Telegram Integrations

Developer access is granted only by an administrator. Configured administrators automatically inherit developer capabilities while retaining the stored `admin` role and all administrator permissions. Ordinary users must send a direct request with `/devrequest <what you are building>`. The bot stores the request and notifies the configured administrator IDs. The administrator then approves with `/grantdeveloper <Telegram ID>` or denies it with `/denydeveloper <Telegram ID> [reason]`. Removing access with `/revokedeveloper <Telegram ID>` also revokes all active keys for that user.

After approval, a developer can create a scoped integration key with `/newkey <name> check`, list metadata with `/devkeys`, revoke a key with `/revokekey <key_id>`, and view usage with `/developerstats`. The plaintext key is shown once only. The database stores a keyed digest, never the secret itself, and all key lifecycle and authorization events are audited. The initial release enables only the `check` scope; `watch`, `schedule`, and `sessions` remain reserved until their ownership and delivery semantics are reviewed.

Other Telegram bots should send the key as a bearer credential to the versioned dashboard API:

```http
POST /api/v1/check
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

Developers can manage keys through the authenticated dashboard at `GET /api/v1/keys`, `POST /api/v1/keys`, and `DELETE /api/v1/keys/{key_id}`. Usage is available at `GET /api/v1/developer/stats`. The owner-scoped developer event feed is available in Telegram through `/devevents [after_event_id]`; use the last returned event ID as the next cursor. Dashboard mutations require the existing secure session and CSRF token; bearer keys do not grant dashboard privileges.

## References

[1]: https://ai.google.dev/gemini-api/docs/rate-limits "Gemini API rate limits"
[2]: https://core.telegram.org/bots/api "Telegram Bot API"
[3]: https://core.telegram.org/api/bots/inline "Telegram inline queries"
[4]: https://core.telegram.org/bots/features "Telegram bot features"

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, database schema, and advanced usage scenarios.

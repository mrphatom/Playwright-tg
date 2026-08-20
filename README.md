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
- **📊 Operations Dashboard:** One-time Telegram-issued dashboard links, secure cookie sessions, CSRF-protected admin actions, redacted execution logs, saved-session metadata, health data, and live polling/websocket updates.
- **🧪 Cautious Activity Review:** Advisory AI risk review with confidence calibration. Strong signals create human-review work; the model never automatically bans, suspends, or limits an account.
- **🐳 Production Docker Ready:** Built-in volume mapping and memory limits for 24/7 VPS hosting.

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
   GEMINI_MODEL=gemini-3.6-flash
   MULTIMODAL_MODEL=gemini-3.6-flash
   CHAT_TIMEOUT_SECONDS=20
   MEDIA_MAX_BYTES=12000000
   MAX_MEDIA_CONTEXT_CHARS=6000
   ALLOWED_TELEGRAM_USERS=123456789,987654321
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

Voice notes and photos are processed only after normal authorization checks. Media is size-limited, downloaded to a temporary file, sent to Gemini for interpretation, and deleted in a `finally` cleanup path. The interpreted content is bounded and marked as untrusted before it reaches either chat or agent routing. The dashboard uses bounded requests, explicit degraded/error states, and retrying polling rather than leaving panels indefinitely stuck on “Loading…”.

Set `GEMINI_API_KEY_2` to enable the optional provider failover. The primary key is used first; quota/rate-limit responses, timeouts, transport failures, and Gemini 5xx responses temporarily cool down that key and retry the same model request with the secondary key. The failover is per model call, so an active Playwright page, saved session, operation ID, and task state are not restarted. Invalid-request and authentication errors are not treated as quota exhaustion. Keys are server-side secrets and are never logged or placed in request URLs.

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

Developers can manage keys through the authenticated dashboard at `GET /api/v1/keys`, `POST /api/v1/keys`, and `DELETE /api/v1/keys/{key_id}`. Usage is available at `GET /api/v1/developer/stats`. Dashboard mutations require the existing secure session and CSRF token; bearer keys do not grant dashboard privileges.

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, database schema, and advanced usage scenarios.

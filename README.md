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
- **💬 Conversational Chat:** Ask ordinary questions, brainstorm, discuss code, plan, or role-play without a command.
- **🧠 AI-Powered Extraction:** Query webpages using conversational prompts instead of fragile CSS selectors.
- **🔒 AES-Encrypted Sessions:** Login to sites once and save your session. Your cookies and tokens are encrypted at rest inside a local SQLite database.
- **⚡ Persistent Browser Pooling:** Maintains a warm background Chromium instance. Commands launch isolated tabs in milliseconds.
- **🛡️ Enterprise Security:** Role-aware authorization, rate limiting, server-side quotas, SSRF-resistant URL validation, encrypted sessions, strict command timeouts, audit records, and a required domain allowlist in public mode.
- **👥 Public User Lifecycle:** Persistent user records, user/admin roles, active/limited/suspended/banned states, administrator search, ban/unban, role management, reports, and appeals.
- **💳 Entitlements:** Telegram Stars Pro upgrade flow with pre-checkout validation, idempotent receipts, durable entitlements, and an optional external HTTPS crypto checkout adapter.
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
   GEMINI_MODEL=gemini-3.6-flash
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

Users can request a one-time dashboard link with `/dashboard`, purchase the Pro entitlement with `/upgrade` using Telegram Stars, submit `/report` and `/appeal` tickets, and use ordinary natural-language messages for the existing browser, watcher, schedule, session, and chat capabilities. Administrators can use `/admin`, `/admin_user`, `/ban`, `/unban`, `/grantadmin`, `/revokeadmin`, `/reports`, `/appeals`, `/review`, and `/resolveappeal`.

Telegram Stars are the in-Telegram payment rail for digital access. Crypto checkout is intentionally provider-gated through `CRYPTO_CHECKOUT_URL`; do not accept wallet addresses, seed phrases, or client-provided payment claims as proof of payment.

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, database schema, and advanced usage scenarios.

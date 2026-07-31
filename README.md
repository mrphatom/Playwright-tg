# 🤖 TeleScout AI: Enterprise Web Automation Agent

![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-Pipeline-blue?logo=githubactions&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google_Gemini-1.5_Flash-8E44AD?logo=googlegemini&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

TeleScout is an asynchronous, AI-powered Telegram bot for stealth web automation. It fuses Playwright's headless browsing with Google Gemini 1.5 Flash, allowing you to control browser sessions, extract structured data via AI, bypass CAPTCHAs, and run continuous background watchers—all via natural language commands in Telegram.

---

## ✨ Core Features

- **👀 Continuous Watchers:** Monitor websites in the background. If a condition is met (e.g., "In Stock" or an AI evaluation), the bot alerts you and stops automatically. Watchers survive server reboots!
- **🧠 AI-Powered Extraction:** Query webpages using conversational prompts instead of fragile CSS selectors.
- **🔒 AES-Encrypted Sessions:** Login to sites once and save your session. Your cookies and tokens are encrypted at rest inside a local SQLite database.
- **⚡ Persistent Browser Pooling:** Maintains a warm background Chromium instance. Commands launch isolated tabs in milliseconds.
- **🛡️ Enterprise Security:** Hard-locked to authorized Telegram IDs, strict command timeouts, rate limiting, and an optional domain whitelist.
- **🐳 Production Docker Ready:** Built-in volume mapping and memory limits for 24/7 VPS hosting.

---

## 🚀 Quickstart (VPS / Production)

1. **Clone the repository**
   ```bash
   git clone [https://github.com/mrphatom/TeleScout-AI.git](https://github.com/mrphatom/TeleScout-AI.git)
   cd TeleScout-AI
   ```

2. **Configure environment variables**  
   Create a `.env` file in the root directory:
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   GEMINI_API_KEY=your_gemini_api_key
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

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, database schema, and advanced usage scenarios.

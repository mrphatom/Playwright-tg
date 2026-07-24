# 🤖 Playwright-tg: Advanced Web Automation Bot

![CI/CD Pipeline](https://img.shields.io/badge/CI%2FCD-Pipeline-blue?logo=githubactions&logoColor=white)
![Playwright](https://img.shields.io/badge/Playwright-2EAD33?logo=playwright&logoColor=white)
![Gemini AI](https://img.shields.io/badge/Google_Gemini-1.5_Flash-8E44AD?logo=googlegemini&logoColor=white)

Playwright-tg is an enterprise-grade, asynchronous Telegram automation agent. It fuses Playwright's headless browsing capabilities with Google Gemini 1.5 Flash, allowing you to control browser sessions, extract structured data via AI, bypass CAPTCHAs, and save login sessions—all via natural language commands in Telegram.

---

## ✨ Core Features

- **🧠 AI-Powered Extraction:** Query webpages using conversational prompts instead of fragile CSS selectors.
- **⚡ Persistent Browser Pooling:** Maintains a warm background Chromium instance. Commands launch isolated tabs in milliseconds.
- **🛡️ Security & Access Control:** Hard-locked to authorized Telegram User IDs.
- **🚦 Concurrency Limits:** Semaphore-based queuing prevents server Out-Of-Memory (OOM) crashes.
- **🍪 Session Persistence:** Login once, save the session, and reuse it instantly on future commands.
- **🐳 Production Docker Compose:** Built-in volume mapping and memory limits for 24/7 VPS hosting.

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
   ALLOWED_TELEGRAM_USERS=123456789,987654321
   ```

3. **Deploy with Docker Compose**
   ```bash
   docker compose up -d --build
   ```

---

## 🎮 Command Syntax

Commands are chained using the pipe (`|`) character. Always start with `/check <URL>`.

### Example: AI Market Research
```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com) | ai_extract:Summarize the top 3 AI stories
```

### Example: Saving an Authenticated Session
```bash
/check [https://example.com/login](https://example.com/login) | type:#email=user@test.com | type:#pass=secret | click:#submit | save_session:user_login
```

---

## 📂 Documentation

Please refer to `GUIDE.md` for a comprehensive architectural breakdown, security model explanation, and advanced usage scenarios.

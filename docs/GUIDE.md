# 🌐 Playwright-tg: Architectural Narrative & Technical Guide

Welcome to the comprehensive technical documentation for **TeleScout AI**. This guide outlines the system architecture, security models, and advanced operational strategies for developers and users.

---

## 🏗️ System Architecture: The Browser Pool

Traditional scrapers launch a new browser process for every request. This adds 3–5 seconds of overhead and consumes massive amounts of RAM, quickly crashing small servers.

Playwright-tg utilizes a **Persistent Browser Pool Pattern**:

1. **Initialization:** On startup (via Telegram's `post_init` hook), one headless Chromium engine boots up.
2. **Context Spawning:** When an authorized user sends a `/check` command, a lightweight, isolated `BrowserContext` (essentially a sandboxed incognito tab) is spawned instantly.
3. **Guaranteed Cleanup:** Upon completion (or failure), a strict `try...finally` block destroys the context, instantly freeing RAM without killing the main Chromium engine.

---

## 🛡️ Security & Infrastructure Guardrails

When exposing a browser automation tool to the internet, security is paramount. TeleScout employs four primary defense layers:

### 1. Authorization Lock (`ALLOWED_TELEGRAM_USERS`)
The `@restricted` Python decorator intercepts every Telegram update. If the sender's User ID is not explicitly whitelisted in the `.env` file, the command is immediately dropped. This prevents strangers from discovering your bot and draining your server resources or API quotas.

### 2. Concurrency Throttling (Asyncio Semaphores)
Web browsers are memory-hungry. The `MAX_CONCURRENT_TASKS` variable defaults to `3`. If 5 commands are sent simultaneously, TeleScout will process the first 3, queue the remaining 2, and execute them only when memory slots free up.

### 3. Path Traversal Sanitation
When executing `save_session:name`, malicious users might attempt to inject paths like `save_session:../../etc/passwd`. TeleScout strictly sanitizes inputs using regex (`re.sub(r'[^a-zA-Z0-9_-]', '_', name)`), ensuring state files remain locked inside the `/sessions/` directory.

### 4. Guaranteed Resource Cleanup
The execution pipeline is wrapped in a tight error boundary:

```python
try:
    context = await browser.new_context()
    page = await context.new_page()
    # Execute automation steps...
finally:
    await context.close()
```

Even if an AI extraction times out, or a CSS selector causes a catastrophic failure, the `finally` block guarantees the browser tab is killed, preventing memory leaks.

---

## 🧠 Advanced Usage: AI Extraction vs. CSS Selectors

### The Fallacy of CSS Scrapers
Modern frameworks (React, Tailwind) generate dynamic CSS class names (e.g., `<div class="css-1a2b3c">`). Hardcoding scrapers to look for these classes means your bot breaks every time the website updates.

### The TeleScout AI Paradigm
Instead of using `extract:.price-tag`, use `ai_extract:prompt`.

Playwright-tg extracts the raw, rendered text payload of the entire webpage via `document.body.innerText`. It strips the HTML, limits the token count to fit context windows, and passes the raw text to **Google Gemini 1.5 Flash** alongside your prompt.

- **Immune to UI Redesigns:** Extracts data based on semantic meaning rather than layout structure.
- **Data Synthesis:** Can calculate, summarize, and synthesize information (e.g., *"Summarize the top 3 reviews"*).
- **Clean Formatting:** Returns highly readable responses directly back to your Telegram chat.

---

## 🐳 Docker Deployment Strategy

TeleScout uses `docker-compose.yml` to enforce deployment stability:

- **Memory Limits:** Hard-capped at 1.5GB to ensure the Linux OOM-killer targets the container, not your host OS.
- **Volume Persistence:** The `./sessions:/app/sessions` mapping ensures that even if you tear down the container to pull a GitHub update, your saved browser cookies and authenticated logins are preserved safely on your host drive.

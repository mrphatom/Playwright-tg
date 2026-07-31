# 🌐 Playwright-tg: Architectural Narrative & Technical Guide

Welcome to the comprehensive technical documentation and user manual for **Playwright-tg** — an enterprise-grade, multi-threaded Telegram automation agent powered by Playwright, Google Gemini AI, SQLite, and a persistent browser pooling pipeline.

This guide serves developers looking to scale or modify the codebase, as well as end-users seeking to master the natural-language automation and background watcher pipelines.

---

## 📖 Part 1: Executive Narrative & Architectural Overview

### The Problem It Solves
Traditional web scraping and browser automation tools are rigid. They break whenever a website updates its DOM (Document Object Model) class names, struggle with heavy client-side JavaScript rendering, get instantly blocked by basic anti-bot infrastructure, and run slowly because they spin up and tear down heavy browser binaries for every individual task.

### The Playwright-tg Solution
Playwright-tg solves these bottlenecks by fusing asynchronous event-driven Telegram communication with a persistent browser architecture and encrypted local state management.

1. **Persistent Browser Pooling:** Instead of launching Chromium on every request (which burns CPU and adds 3–5 seconds of latency), Playwright-tg spins up a single background browser instance on startup. User requests spawn isolated, lightweight browser contexts (tabs/incognito windows) concurrently.
2. **AI-Driven Data Extraction:** Traditional scrapers rely on brittle CSS selectors (e.g., `div > span.price`). Playwright-tg dumps the entire text payload of a rendered page directly into Google Gemini 1.5 Flash, allowing users to query webpage data using conversational prompts (e.g., *“What is the discount percentage of this item?”*).
3. **Encrypted Session Persistence:** Cookies and local storage states are encrypted at rest using AES in a persistent SQLite database, allowing authenticated sessions to survive bot restarts safely.
4. **Resilient Evasion & Continuous Watchers:** Through inline script masking (`navigator.webdriver` spoofing), optional proxy routing, and persistent background watchers, the bot monitors pages silently and alerts you only when key conditions are met.

---

## 🛠️ Part 2: Developer Guide & System Architecture

### Core Design Patterns

#### 1. Lifecycle Hooks (`post_init` & `post_stop`)
The Telegram bot utilizes `python-telegram-bot`'s asynchronous lifecycle hooks to bind the browser pool directly to the event loop lifecycle.

This guarantees that Chromium initializes before any updates are polled and gracefully terminates when the application shuts down, preventing zombie browser processes.

#### 2. The Action Pipeline Interpreter
When a user sends a command string separated by pipes (`|`), the command handler parses it into an ordered execution array:

- `type:selector=value` $\rightarrow$ Locates input element and triggers `.fill()`
- `click:selector` $\rightarrow$ Locates interactive node and triggers `.click()`
- `wait:seconds` $\rightarrow$ Suspends async task execution for dynamic JS rendering
- `extract:selector` $\rightarrow$ Scrapes standard structural inner text nodes
- `ai_extract:prompt` $\rightarrow$ Passes raw text body to Gemini via Google GenAI SDK
- `save_session:name` / `load_session:name` $\rightarrow$ Encrypts/Decrypts and saves/restores state via SQLite

---

## 🛡️ Part 3: Security & Infrastructure Guardrails

When exposing a browser automation tool to Telegram, security is paramount. Playwright-tg employs four primary defense layers:

### 1. Authorization Lock (`ALLOWED_TELEGRAM_USERS`)
The `@restricted` Python decorator intercepts every Telegram update. If the sender's User ID is not explicitly whitelisted in the `.env` file, the command is immediately dropped.

### 2. Concurrency Throttling (Asyncio Semaphores)
The `MAX_CONCURRENT_TASKS` variable defaults to `3`. If multiple commands arrive simultaneously, Playwright-tg queues them and executes as slots free up to prevent memory spikes.

### 3. Path Traversal Sanitation
Inputs for session names are sanitized using strict regex (`re.sub(r'[^a-zA-Z0-9_-]', '_', name)`), ensuring database keys and session references remain completely isolated.

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

---

## 👤 Part 4: End-User Manual & Operational Guide

### Basic Navigation

To test the bot's baseline functionality, send a basic inspection URL:

```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com)
```

---

### Advanced Command Pipeline Manual

You can chain multiple instructions using the pipe (`|`) delimiter. Every `/check` pipeline starts with `/check <URL>`.

#### 1. Form Interactions
```bash
/check [https://example.com/login](https://example.com/login) | type:#username=myuser | type:#password=mypass | click:#login-btn | wait:3
```

#### 2. AI Extraction
```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com) | ai_extract:Summarize the top 3 trending AI stories on this page
```

#### 3. Continuous Background Watchers (`/watch`)
```bash
/watch 300 [https://example.com/store](https://example.com/store) | condition_contains:In Stock
```

#### 4. Encrypted Sessions
```bash
/check [https://example.com/login](https://example.com/login) | type:#user=admin | type:#pass=123 | click:#submit | save_session:my_session
```

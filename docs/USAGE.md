# 🌐 Playwright-tg: Architectural Narrative & Technical Guide

Welcome to the comprehensive technical documentation and user manual for **TeleScout AI** — an autonomous, multi-threaded Telegram automation bridge powered by Playwright, Google Gemini AI, and a persistent browser pooling pipeline.

This guide serves developers looking to scale or modify the codebase, as well as end-users seeking to master the natural-language automation pipeline.

---

## 📖 Part 1: Executive Narrative & Architectural Overview

### The Problem It Solves
Traditional web scraping and browser automation tools are rigid. They break whenever a website updates its DOM (Document Object Model) class names, struggle with heavy client-side JavaScript rendering, get instantly blocked by basic anti-bot infrastructure, and run slowly because they spin up and tear down heavy browser binaries for every individual task.

### The TeleScout Solution
TeleScout solves these bottlenecks by fusing asynchronous event-driven Telegram communication with a persistent browser architecture.

1. **Persistent Browser Pooling:** Instead of launching Chromium on every request (which burns CPU and adds 3–5 seconds of latency), TeleScout spins up a single background browser instance on startup. User requests spawn isolated, lightweight browser contexts (tabs/incognito windows) concurrently.
2. **AI-Driven Data Extraction:** Traditional scrapers rely on brittle CSS selectors (e.g., `div > span.price`). TeleScout dumps the entire text payload of a rendered page directly into Google Gemini 1.5 Flash, allowing users to query webpage data using conversational prompts (e.g., *“What is the discount percentage of this item?”*).
3. **Resilient Evasion & Sessions:** Through inline script masking (`navigator.webdriver` spoofing), optional proxy routing, and local session-state caching (`storage_state`), the bot bypasses routine bot detection flags and maintains active user logins securely across tasks.

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
- `save_session:name` / `load_session:name` $\rightarrow$ Serializes/Deserializes cookies & localStorage

---

## 👤 Part 3: End-User Manual & Operational Guide

### Basic Navigation

To test the bot's baseline functionality, send a basic inspection URL:

```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com)
```

**Expected Output:** The bot returns a status ticker, navigates to Hacker News, captures a high-resolution full-page screenshot, extracts the page title, and sends it directly to your chat.

---

### Advanced Command Pipeline Manual

You can chain multiple instructions using the pipe (`|`) delimiter. Every pipeline starts with `/check <URL>`.

#### 1. Interacting with Forms & Buttons
To fill out a search bar or log into a portal:

```bash
/check [https://example.com/login](https://example.com/login) | type:#username=myuser | type:#password=mypass | click:#login-btn | wait:3
```

#### 2. AI-Powered Natural Language Scraping
Bypass complicated CSS structures entirely by letting Gemini read the page layout:

```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com) | ai_extract:Summarize the top 3 trending AI stories on this page
```

#### 3. Persistent Authentication (Sessions)
Save or load login sessions across runs:

```bash
/check [https://example.com/login](https://example.com/login) | type:#user=admin | type:#pass=123 | click:#submit | save_session:my_session
```

#### 4. Stealth & Proxy Routing
If a target platform aggressively blocks data center IP addresses, inject residential proxies into your pipeline:

```bash
/check [https://target-website.com](https://target-website.com) | proxy:[http://user:pass@proxy.example.com:8080](http://user:pass@proxy.example.com:8080) | ai_extract:Extract product details
```

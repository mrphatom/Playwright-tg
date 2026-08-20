# 🕹️ Playwright-tg: Practical Usage & Examples

Playwright-tg operates using a pipeline syntax. You start with a base command (like `/check` or `/watch`), provide the target URL, and then chain a series of "actions" together using the pipe character `|`.

**Basic Structure:**
```bash
/command [https://example.com](https://example.com) | action_1 | action_2 | action_3
```

---

## 💬 Conversational and Plain-Language Requests

You can send ordinary sentences instead of slash commands. Messages without an explicit URL-based web request are answered as normal conversation, so you can ask questions, brainstorm, discuss code, plan your day, or role-play naturally.

For example:

```text
What do you think about making a small app that helps me plan my week?
```

Every authorized non-command message is interpreted before it is treated as chat. A message with a clear supported command, URL, session operation, watcher operation, schedule, or login workflow is routed into the corresponding validated pipeline. Ordinary questions remain conversational. Include an explicit `http://` or `https://` URL for web actions; the interpreter will not invent a target.

For a one-time check:

```text
Check https://example.com and summarize the page title and main product details
```

For a persistent watcher:

```text
Check https://example.com/store and tell me when Apple Pie is in stock
```

The bot converts the message into a validated plan using Gemini and deterministic recovery rules, then reuses the same browser pipeline and persistent SQLite engines as the structured commands. Credential-bearing login messages are parsed locally and are never sent to Gemini. Existing slash commands continue to work unchanged. Plain-language requests are subject to the same authorized-user check, domain whitelist, concurrency limit, and timeout controls.

For a recurring briefing, you can write:

```text
Every weekday at 08:00 Europe/London, summarize https://example.com/news and https://example.org/releases and send me one combined morning briefing
```

Schedules are stored in SQLite and restored when the bot restarts. If you omit a timezone, the default is UTC; if you omit the day pattern, the default is weekdays. A schedule can deliver one combined message or one message per source.

The same natural-language interpreter also covers the other command families:

```text
Show my saved sessions
List active watchers
Stop watcher abc123
Cancel schedule qwe789
Delete session x_login
Open https://example.com/dashboard using the saved session x_login, wait 2 seconds, and extract .headline
Create a session called x_login, then log in to https://x.com, Username = 'your_username' Password = 'your_password'
```

A named session in a login request is persisted as encrypted browser state after the login pipeline finishes. You can also select a saved session for the next browser operation without repeating the session name:

```text
Load session 'x_login'
Open https://example.com/dashboard and summarize the account page
```

The bot confirms whether the session exists, applies it to the next browser command, and clears the selection when that session is deleted. Each natural-language operation receives a short reference ID in its progress message for troubleshooting. Transient browser failures use a bounded retry policy; permanent validation failures are not retried indefinitely. `/health` and “show system health” report browser readiness, resource usage, active schedules/watchers, command counts, browser attempts, and failures. Sites requiring CAPTCHA or MFA may still require manual completion.

---

## ⏰ Scheduled Briefings

The explicit schedule syntax is:

```text
/schedule <HH:MM> <IANA timezone> <daily|weekdays|weekends|days> <combined|separate> <url1,url2> | <summary prompt>
```

Example:

```text
/schedule 08:00 Europe/London weekdays combined https://example.com/news,https://example.org/releases | Summarize the important updates and mention anything that requires attention
```

Use `/schedules` to list active briefings and `/unschedule <ID>` to stop one. The scheduler runs inside the existing Fly.io bot process and uses the persistent `/data/telescout.db` volume.

---

## 🛠️ Action Glossary

Here are all the building blocks you can use in your pipelines:

| Action | Syntax | Description |
| :--- | :--- | :--- |
| **Type** | `type:<css_selector>=<text>` | Types text into an input field (e.g., search bar or login form). |
| **Click** | `click:<css_selector>` | Clicks a button, link, or interactive element. |
| **Wait** | `wait:<seconds>` | Pauses the pipeline. Crucial for letting dynamic Javascript or loaders finish. |
| **Extract** | `extract:<css_selector>` | Scrapes raw text from all elements matching the CSS selector. |
| **AI Extract** | `ai_extract:<prompt>` | Passes the page content to Gemini AI to answer your natural language prompt. |
| **Save Session** | `save_session:<name>` | Encrypts and saves your current cookies/login state to the database. |
| **Load Session** | `load_session:<name>` | Injects a previously saved session before navigating to the URL. |
| **Proxy** | `proxy:on` | Routes this specific task through the proxy configured in your `.env`. |

---

## 👀 Watcher Conditions (For `/watch` only)

When running a background watcher, you must tell the bot when to alert you and stop.

| Condition | Syntax | Description |
| :--- | :--- | :--- |
| **Interval** | `every:<seconds>` | How often to check the page (Minimum: 30 seconds). |
| **Text Check** | `condition_contains:<text>` | Triggers if the specified text appears anywhere on the page (case-insensitive). |
| **AI Check** | `condition_ai:<prompt>` | Triggers if the AI evaluates your prompt as 'TRUE'. |

---

## 📚 Real-World Scenarios & Examples

### 1. The Simple Screenshot
Just want to see what a webpage looks like right now?
```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com)
```
*Result:* Returns a full-page screenshot and the page title.

### 2. Standard Data Extraction (CSS)
Grab specific text elements, like the trending repositories on GitHub.
```bash
/check [https://github.com/trending](https://github.com/trending) | extract:h2.h3 a
```

### 3. AI-Powered Market Research (Recommended)
Don't want to dig for CSS selectors? Let Gemini do the reading for you.
```bash
/check [https://news.ycombinator.com](https://news.ycombinator.com) | ai_extract:Summarize the top 3 trending tech discussions on this page
```

### 4. Logging In and Saving a Session
Automate a login flow, wait for the redirect, and save the authenticated state for future use.
```bash
/check [https://example.com/login](https://example.com/login) | type:#username=admin | type:#password=secret | click:#submit | wait:5 | save_session:admin_main
```

### 5. Using a Saved Session
Skip the login screen completely by loading the session you saved in Scenario 4.
```bash
/check [https://example.com/dashboard](https://example.com/dashboard) | load_session:admin_main | ai_extract:What is my current account balance?
```

### 6. The Continuous Watcher (Stock/Price Checker)
Check an Amazon product page every 60 seconds and alert you when it's back in stock.
```bash
/watch [https://example.com/store-item](https://example.com/store-item) | every:60 | condition_contains:In Stock
```

### 7. The AI Watcher (Smart Alerts)
Use AI logic for complex watcher conditions. Check every 2 minutes (120 seconds).
```bash
/watch [https://news.ycombinator.com](https://news.ycombinator.com) | every:120 | condition_ai:Is there any news about artificial intelligence breakthroughs today?
```

---

## 🤖 Full Command List

Type these directly into your Telegram chat to manage your bot:

- `/start` — Shows the welcome message and basic syntax.
- `/health` — Displays VPS Server CPU, RAM usage, and active browser pool status.
- `/check <url> | <actions>` — Runs a one-off automation pipeline.
- `/watch <url> | every:<sec> | <condition>` — Starts a persistent background watcher.
- `/schedule <time> <timezone> <days> <delivery> <urls> | <prompt>` — Creates a recurring briefing.
- `/schedules` — Lists active recurring briefings.
- `/unschedule <ID>` — Stops a recurring briefing.
- `/watchers` — Lists all currently running background watchers and their IDs.
- `/stopwatch <ID>` — Manually stops a running watcher.
- `/sessions` — Lists the names of your saved, encrypted browser sessions.
- `/deletesession <name>` — Permanently deletes a saved session from the database.

---

## 💡 Pro-Tips for Success

1. **Wait for Loaders:** If a site has a slow loading animation after you click a button, always add a `wait:` action before taking a screenshot or extracting data (e.g., `| click:#submit | wait:3 | extract:.result`).
2. **Selector Specificity:** When using `type:` or `click:`, use exact IDs (`#element`) or name attributes (`input[name="email"]`) whenever possible. Broad classes (like `.btn`) might click the wrong button if there are multiple elements on the page.
3. **AI Limits:** The `ai_extract:` action sends the visible text of the page to Gemini. If a webpage is infinitely long (like a social media feed), the AI only sees what loaded during the initial render. Use a `wait:` action to let the page settle first.

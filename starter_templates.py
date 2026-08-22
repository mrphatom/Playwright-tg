"""Verified starter repositories for integrating GreyAI into another Telegram bot."""
from __future__ import annotations

import ast
import re
from html import escape as html_escape
import zipfile
from pathlib import Path

from api_contract import DEFAULT_GREY_PUBLIC_BASE_URL


def _safe_project_name(raw: str | None) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(raw or "greyai-telegram-integration").strip()).strip(".-_")
    return (value.lower() or "greyai-telegram-integration")[:80]


def _python_files(project_name: str, base_url: str) -> dict[str, str]:
    return {
        "README.md": f'''# {project_name}

A minimal production-oriented Telegram bot that calls GreyAI's verified developer API.

## What this starter does

The bot listens for `/start`, `/help`, and `/check <url> [| extraction request]`. It sends a bounded HTTPS request to GreyAI's `POST /api/v1/check` endpoint and returns the extracted result. GreyAI applies the developer-key scope, account quota, per-key rate limit, URL/domain policy, SSRF protections, queue, timeout, and maintenance gates.

This starter does not contain a GreyAI key or Telegram token. Store both in environment variables or a secret manager.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Telegram token and GreyAI developer key.
python bot.py
```

Create a GreyAI developer key with `/newkey greyai-telegram check`. The plaintext key is shown once. Never commit `.env` or print the key.

The exact live API contract is available at `{base_url}/api/v1/docs`.
''',
        ".env.example": f'''TELEGRAM_BOT_TOKEN=replace_with_your_telegram_bot_token
GREY_API_KEY=replace_with_your_greyai_developer_key
GREY_API_BASE_URL={base_url}
''',
        ".gitignore": ".env\n.venv/\n__pycache__/\n*.pyc\n",
        "requirements.txt": "python-telegram-bot==22.8\naiohttp>=3.9,<4\npython-dotenv>=1.0,<2\n",
        "bot.py": '''from __future__ import annotations

import logging
import os
from html import escape

import aiohttp
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
GREY_API_KEY = os.environ["GREY_API_KEY"]
GREY_API_BASE_URL = os.getenv("GREY_API_BASE_URL", "https://playwright-tg-mrphatom.fly.dev").rstrip("/")
GREY_CHECK_ENDPOINT = f"{GREY_API_BASE_URL}/api/v1/check"


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "I’m connected to GreyAI. Use /check https://example.com | summarize the important facts."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Usage: /check <https-url> | <bounded extraction request>\\n"
        "Example: /check https://example.com | summarize the page."
    )


async def check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    raw = " ".join(context.args).strip()
    if not raw:
        await update.message.reply_text("Usage: /check <https-url> | <extraction request>")
        return
    url, separator, extract = raw.partition("|")
    url = url.strip()
    extract = (extract.strip() if separator else "Summarize the important facts on this page.")[:500]
    if not url.startswith(("https://", "http://")):
        await update.message.reply_text("Use a complete HTTPS URL that GreyAI’s domain policy allows.")
        return

    headers = {
        "Authorization": f"Bearer {GREY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {"url": url[:2048], "extract": extract}
    try:
        timeout = aiohttp.ClientTimeout(total=110)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(GREY_CHECK_ENDPOINT, json=payload, headers=headers) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    error = escape(str(data.get("error", "grey_api_request_failed")))
                    await update.message.reply_text(f"GreyAI returned HTTP {response.status}: {error}")
                    return
        extracted = data.get("extracted") or ["No extracted result returned."]
        text = "\\n\\n".join(str(item)[:4000] for item in extracted[:10])
        await update.message.reply_text(text[:4096])
    except (aiohttp.ClientError, TimeoutError) as exc:
        logging.warning("GreyAI request failed: %s", type(exc).__name__)
        await update.message.reply_text("GreyAI could not complete the request. Check the URL, quota, and API status.")


def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("check", check))
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
''',
    }


def build_telegram_bot_starter_archive(
    project_name: str | None = None,
    base_url: str | None = None,
    output_dir: str | Path | None = None,
) -> Path:
    """Build a small runnable ZIP and return its path; callers own cleanup."""
    safe_name = _safe_project_name(project_name)
    public_base = str(base_url or DEFAULT_GREY_PUBLIC_BASE_URL).strip().rstrip("/")
    target_dir = Path(output_dir) if output_dir is not None else Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{safe_name}.zip"
    files = _python_files(safe_name, public_base)
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path, content in files.items():
            archive.writestr(f"{safe_name}/{relative_path}", content)
    return target


_ALLOWED_CODE_ARCHIVE_SUFFIXES = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".json", ".toml", ".yaml", ".yml",
    ".txt", ".md", ".css", ".html", ".sh", ".env.example", ".gitignore",
}
_MAX_CODE_ARCHIVE_FILES = 24
_MAX_CODE_ARCHIVE_FILE_BYTES = 120_000
_MAX_CODE_ARCHIVE_TOTAL_BYTES = 500_000
_REAL_SECRET_PATTERNS = (
    re.compile(r"\b\d{9,10}:[A-Za-z0-9_-]{30,}\b"),
    re.compile(r"\b(?:gai_live|AIza|sk-|ghp-)[A-Za-z0-9._:/+-]{12,}\b"),
)


def _safe_code_archive_path(raw_path: str) -> str:
    value = str(raw_path or "").replace("\\", "/").strip().lstrip("/")
    parts = [part for part in value.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("unsafe_code_archive_path")
    relative = "/".join(parts)
    suffix = Path(relative).suffix.lower()
    if suffix not in _ALLOWED_CODE_ARCHIVE_SUFFIXES and not relative.endswith(".env.example"):
        raise ValueError("unsupported_code_archive_file")
    return relative[:160]


def validate_code_archive_files(files: dict[str, str]) -> dict[str, str]:
    """Validate generated source as inert text before it is placed in a ZIP."""
    if not isinstance(files, dict) or not files:
        raise ValueError("code_archive_empty")
    if len(files) > _MAX_CODE_ARCHIVE_FILES:
        raise ValueError("code_archive_too_many_files")
    safe_files: dict[str, str] = {}
    total_bytes = 0
    for raw_path, raw_content in files.items():
        path = _safe_code_archive_path(raw_path)
        content = str(raw_content or "")
        encoded_size = len(content.encode("utf-8"))
        if encoded_size > _MAX_CODE_ARCHIVE_FILE_BYTES:
            raise ValueError("code_archive_file_too_large")
        if any(pattern.search(content) for pattern in _REAL_SECRET_PATTERNS):
            raise ValueError("code_archive_secret_detected")
        if path.endswith(".py"):
            try:
                ast.parse(content, filename=path)
            except SyntaxError as exc:
                raise ValueError("code_archive_python_syntax") from exc
        total_bytes += encoded_size
        if total_bytes > _MAX_CODE_ARCHIVE_TOTAL_BYTES:
            raise ValueError("code_archive_total_too_large")
        if path in safe_files:
            raise ValueError("code_archive_duplicate_path")
        safe_files[path] = content
    return safe_files


def build_landing_page_files(project_name: str | None, brief: str | None = None) -> dict[str, str]:
    """Return a dependency-free responsive landing page project as inert source."""
    safe_name = _safe_project_name(project_name or "greyai-landing-page")
    user_brief = re.sub(r"\s+", " ", str(brief or "").strip())[:240]
    escaped_name = html_escape(safe_name.replace("-", " ").title())
    escaped_brief = html_escape(user_brief or "A focused landing page for your next idea.")
    return {
        "index.html": f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="{escaped_brief}">
  <title>{escaped_name}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="site-header">
    <a class="brand" href="#top" aria-label="{escaped_name} home">{escaped_name}</a>
    <a class="header-link" href="#contact">Get started</a>
  </header>
  <main id="top">
    <section class="hero" aria-labelledby="hero-title">
      <p class="eyebrow">A clearer way forward</p>
      <h1 id="hero-title">Turn a good idea into a great first impression.</h1>
      <p class="hero-copy">{escaped_brief}</p>
      <div class="hero-actions">
        <a class="button button-primary" href="#contact">Start a conversation</a>
        <a class="button button-secondary" href="#features">Explore the details</a>
      </div>
    </section>
    <section id="features" class="feature-grid" aria-label="Highlights">
      <article class="feature-card"><span class="feature-number">01</span><h2>Focused</h2><p>Clear hierarchy keeps attention on the action that matters.</p></article>
      <article class="feature-card"><span class="feature-number">02</span><h2>Responsive</h2><p>A fluid layout stays comfortable on phones, tablets, and desktops.</p></article>
      <article class="feature-card"><span class="feature-number">03</span><h2>Ready</h2><p>Clean HTML, CSS, and JavaScript give you a practical starting point.</p></article>
    </section>
    <section id="contact" class="contact-card" aria-labelledby="contact-title">
      <div><p class="eyebrow">Ready when you are</p><h2 id="contact-title">Let’s build something people remember.</h2></div>
      <a class="button button-primary" href="mailto:hello@example.com">Say hello</a>
    </section>
  </main>
  <footer class="site-footer"><span>{escaped_name}</span><span>Built with semantic HTML and no dependencies.</span></footer>
  <script src="script.js" defer></script>
</body>
</html>
''',
        "styles.css": '''@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&family=Space+Grotesk:wght@500;600;700&display=swap');
:root { --ink:#15231f; --muted:#62716d; --paper:#f5f7f2; --accent:#b8f36b; --line:#dce4dc; }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; color:var(--ink); background:var(--paper); font:16px/1.6 'DM Sans',system-ui,sans-serif; }
.site-header,.site-footer { width:min(1120px,calc(100% - 48px)); margin:auto; display:flex; justify-content:space-between; align-items:center; padding:28px 0; }
.site-header { border-bottom:1px solid var(--line); }
.brand { color:var(--ink); font-family:'Space Grotesk',sans-serif; font-weight:700; text-decoration:none; letter-spacing:-.03em; }
.header-link { color:var(--ink); font-weight:700; text-decoration:none; }
main { width:min(1120px,calc(100% - 48px)); margin:auto; }
.hero { min-height:650px; display:flex; flex-direction:column; justify-content:center; max-width:850px; padding:80px 0; }
.eyebrow { color:#5e7d37; font-size:.78rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase; }
h1,h2 { font-family:'Space Grotesk',sans-serif; letter-spacing:-.055em; line-height:1.04; margin:.25em 0; }
h1 { font-size:clamp(3.2rem,8vw,7.2rem); max-width:850px; }
h2 { font-size:clamp(1.7rem,3vw,2.5rem); }
.hero-copy { color:var(--muted); font-size:1.2rem; max-width:580px; margin:28px 0; }
.hero-actions { display:flex; flex-wrap:wrap; gap:12px; margin-top:12px; }
.button { display:inline-block; border:1px solid var(--ink); border-radius:999px; padding:12px 20px; color:var(--ink); font-weight:700; text-decoration:none; transition:transform .2s,box-shadow .2s; }
.button:hover,.button:focus-visible { transform:translateY(-2px); box-shadow:4px 4px 0 var(--ink); outline:none; }
.button-primary { background:var(--accent); }
.button-secondary { background:transparent; }
.feature-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:16px; padding:48px 0 120px; }
.feature-card { min-height:240px; border:1px solid var(--line); border-radius:24px; padding:28px; background:#fff; }
.feature-number { color:#91a29b; font-family:'Space Grotesk',sans-serif; font-weight:700; }
.feature-card p { color:var(--muted); }
.contact-card { display:flex; align-items:center; justify-content:space-between; gap:24px; border-radius:28px; padding:48px; background:var(--ink); color:#fff; }
.contact-card .eyebrow { color:var(--accent); }
.contact-card .button { border-color:#fff; color:#fff; }
.site-footer { color:var(--muted); font-size:.85rem; border-top:1px solid var(--line); margin-top:120px; }
@media (max-width:700px) { .site-header,.site-footer,main { width:min(100% - 32px,1120px); } .hero { min-height:560px; padding:48px 0; } .feature-grid { grid-template-columns:1fr; padding-bottom:72px; } .contact-card { align-items:flex-start; flex-direction:column; padding:32px; } .site-footer { align-items:flex-start; flex-direction:column; gap:8px; } }
''',
        "script.js": '''document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', () => {
    const target = document.querySelector(link.getAttribute('href'));
    if (target) target.setAttribute('tabindex', '-1');
  });
});
''',
        "README.md": f'''# {safe_name.replace("-", " ").title()}\n\nA dependency-free responsive landing page generated by GreyAI.\n\n## Files\n\n- `index.html` — semantic page structure\n- `styles.css` — responsive visual system\n- `script.js` — small progressive-enhancement interaction\n\nOpen `index.html` locally or serve this folder with any static web server. Review the content and replace the example contact address before publishing.\n''',
    }


def build_code_archive(
    project_name: str | None,
    files: dict[str, str],
    output_dir: str | Path | None = None,
) -> Path:
    """Build a validated inert source archive; never executes generated files."""
    safe_name = _safe_project_name(project_name or "greyai-code-project")
    safe_files = validate_code_archive_files(files)
    target_dir = Path(output_dir) if output_dir is not None else Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{safe_name}.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative_path, content in safe_files.items():
            archive.writestr(f"{safe_name}/{relative_path}", content)
    return target

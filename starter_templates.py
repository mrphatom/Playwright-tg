"""Verified starter repositories for integrating GreyAI into another Telegram bot."""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Dict

from api_contract import DEFAULT_GREY_PUBLIC_BASE_URL


def _safe_project_name(raw: str | None) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(raw or "greyai-telegram-integration").strip()).strip(".-_")
    return (value.lower() or "greyai-telegram-integration")[:80]


def _python_files(project_name: str, base_url: str) -> Dict[str, str]:
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

import asyncio
import os
import logging
import re
import time
import uuid
import json
import sqlite3
import base64
from typing import List, Dict, Optional, Any
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.error import TelegramError

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Browser, Playwright, BrowserContext
import google.generativeai as genai
from cryptography.fernet import Fernet
import psutil

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

ALLOWED_USERS = set(int(uid.strip()) for uid in os.getenv("ALLOWED_TELEGRAM_USERS", "").split(",") if uid.strip().isdigit())
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
COMMAND_TIMEOUT = int(os.getenv("COMMAND_TIMEOUT", "90"))
task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

# Domain Whitelist (Comma separated domains, e.g. "github.com,amazon.com". Leave empty to allow all)
ALLOWED_DOMAINS = [d.strip().lower() for d in os.getenv("ALLOWED_DOMAINS", "").split(",") if d.strip()]

# Proxies
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

# Encryption Key for Sessions at Rest
ENCRYPTION_KEY = os.getenv("SESSION_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    token_seed = (TELEGRAM_BOT_TOKEN or "default_secret_seed").encode("utf-8")
    ENCRYPTION_KEY = base64.urlsafe_b64encode(token_seed.ljust(32)[:32]).decode("utf-8")

cipher_suite = Fernet(ENCRYPTION_KEY.encode("utf-8"))

# AI Setup
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

def get_db_path() -> str:
    """Returns the current database path dynamically."""
    return os.getenv("DB_PATH", "telescout.db")

# State Management
class BrowserPool:
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None

pool = BrowserPool()
active_watchers: Dict[int, Dict[str, asyncio.Task]] = {}
user_cooldowns: Dict[int, float] = {}

# ==========================================
# DATABASE ENGINE (SQLITE)
# ==========================================
def init_db():
    """Initializes the SQLite database tables."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        
        # Sessions table (encrypted storage)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                encrypted_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, name)
            )
        """)
        
        # Watchers table (persisted across restarts)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS watchers (
                watcher_id TEXT PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                url TEXT NOT NULL,
                actions_json TEXT NOT NULL,
                interval_seconds INTEGER NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Audit Logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                target_url TEXT,
                status TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
    logger.info("Database initialized successfully.")

def log_audit(user_id: int, command: str, target_url: Optional[str], status: str):
    """Inserts a command log entry into SQLite."""
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO audit_logs (user_id, command, target_url, status) VALUES (?, ?, ?, ?)",
                (user_id, command, target_url, status)
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to record audit log: {e}")

def save_encrypted_session(user_id: int, name: str, session_data: dict):
    """Encrypts browser storage state JSON and saves to SQLite."""
    json_str = json.dumps(session_data)
    encrypted_bytes = cipher_suite.encrypt(json_str.encode("utf-8"))
    encrypted_str = encrypted_bytes.decode("utf-8")
    
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO sessions (user_id, name, encrypted_data) 
            VALUES (?, ?, ?) 
            ON CONFLICT(user_id, name) DO UPDATE SET encrypted_data = excluded.encrypted_data
        """, (user_id, name, encrypted_str))
        conn.commit()

def load_encrypted_session(user_id: int, name: str) -> Optional[dict]:
    """Retrieves and decrypts a browser session from SQLite."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT encrypted_data FROM sessions WHERE user_id = ? AND name = ?", (user_id, name))
        row = cursor.fetchone()
        if not row:
            return None
        try:
            decrypted_bytes = cipher_suite.decrypt(row[0].encode("utf-8"))
            return json.loads(decrypted_bytes.decode("utf-8"))
        except Exception as e:
            logger.error(f"Failed to decrypt session '{name}': {e}")
            return None

def list_user_sessions(user_id: int) -> List[str]:
    """Lists all active session names for a user."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sessions WHERE user_id = ?", (user_id,))
        return [row[0] for row in cursor.fetchall()]

def delete_user_session(user_id: int, name: str) -> bool:
    """Deletes a saved session from SQLite."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE user_id = ? AND name = ?", (user_id, name))
        conn.commit()
        return cursor.rowcount > 0

def save_watcher_to_db(watcher_id: str, chat_id: int, url: str, actions: List[str], interval: int):
    """Persists a watcher configuration to SQLite."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO watchers (watcher_id, chat_id, url, actions_json, interval_seconds, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (watcher_id, chat_id, url, json.dumps(actions), interval))
        conn.commit()

def deactivate_watcher_in_db(watcher_id: str):
    """Marks a watcher as inactive in SQLite."""
    with sqlite3.connect(get_db_path()) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE watchers SET is_active = 0 WHERE watcher_id = ?", (watcher_id,))
        conn.commit()

# ==========================================
# UTILITIES & SECURITY
# ==========================================
def is_valid_url(url: str) -> bool:
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

def is_domain_allowed(url: str) -> bool:
    if not ALLOWED_DOMAINS:
        return True
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain == d or domain.endswith("." + d) for d in ALLOWED_DOMAINS)
    except Exception:
        return False


def normalize_natural_language_plan(raw_plan: Any) -> Optional[Dict[str, Any]]:
    """Validate and convert an AI-produced intent into allowlisted pipeline actions."""
    if not isinstance(raw_plan, dict):
        return None

    mode = str(raw_plan.get("mode", "")).strip().lower()
    url = str(raw_plan.get("url", "")).strip()
    if mode not in {"check", "watch"} or not is_valid_url(url) or not is_domain_allowed(url):
        return None

    request = str(raw_plan.get("request", "")).strip()[:500]
    condition = str(raw_plan.get("condition", "")).strip()[:500]
    condition_type = str(raw_plan.get("condition_type", "ai")).strip().lower()
    if condition_type not in {"ai", "contains"}:
        condition_type = "ai"

    try:
        interval_seconds = int(raw_plan.get("interval_seconds", 60))
    except (TypeError, ValueError):
        interval_seconds = 60
    interval_seconds = max(30, min(interval_seconds, 86400))

    if mode == "watch":
        if not condition:
            return None
        prefix = "condition_contains" if condition_type == "contains" else "condition_ai"
        actions = [f"{prefix}:{condition}"]
    else:
        actions = [f"ai_extract:{request}"] if request else []

    return {
        "mode": mode,
        "url": url,
        "actions": actions,
        "condition": condition,
        "condition_type": condition_type,
        "interval_seconds": interval_seconds,
    }


NATURAL_LANGUAGE_SYSTEM_PROMPT = """
You translate a user's plain-language web automation request into JSON only.
Never return Markdown, code, or extra keys. Use exactly this object shape:
{
  "mode": "check" | "watch" | "unknown",
  "url": "http or https URL, or empty string",
  "request": "information to extract for a one-time check",
  "condition": "condition to monitor for a watcher",
  "condition_type": "ai" | "contains",
  "interval_seconds": integer,
  "reply_summary": "short confirmation"
}
Rules:
- Extract only an explicit http:// or https:// URL from the user message.
- Use mode watch when the user asks to be told, alerted, notified, or checked until a condition happens.
- Use mode check for a one-time lookup, extraction, summary, or screenshot.
- Use condition_type contains only when a literal text match is clearly requested; otherwise use ai.
- Default interval_seconds to 60 and never choose less than 30.
- If there is no valid URL or no clear web request, use mode unknown.
""".strip()


async def parse_natural_language_intent(user_text: str) -> Optional[Dict[str, Any]]:
    """Ask Gemini for a JSON intent, then validate it before execution."""
    if not ai_model:
        return None

    prompt = f"{NATURAL_LANGUAGE_SYSTEM_PROMPT}\n\nUser request:\n{user_text[:2000]}"
    try:
        response = await asyncio.to_thread(
            ai_model.generate_content,
            prompt,
            generation_config={"temperature": 0.1, "max_output_tokens": 512},
        )
        raw_plan = json.loads((response.text or "").strip())
        return normalize_natural_language_plan(raw_plan)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        logger.warning("Natural-language intent parsing failed: %s", exc)
        return None
    except Exception:
        logger.exception("Unexpected natural-language intent parsing error")
        return None


def sanitize_session_name(name: str) -> str:
    return re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())

def truncate_text(text: str, max_length: int = 4000) -> str:
    return text if len(text) <= max_length else text[:max_length - 15] + "\n...[Truncated]"

def mask_sensitive_action(action: str) -> str:
    if action.startswith("type:"):
        parts = action.split("=", 1)
        if len(parts) == 2: return f"{parts[0]}=***MASKED***"
    return action

# ==========================================
# DECORATORS
# ==========================================
def restricted(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if not ALLOWED_USERS or user_id not in ALLOWED_USERS:
            logger.warning(f"Unauthorized access by ID {user_id}")
            log_audit(user_id, func.__name__, None, "DENIED_UNAUTHORIZED")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

def rate_limited(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        now = time.time()
        if user_id in user_cooldowns and now - user_cooldowns[user_id] < 5:
            await update.message.reply_text("⏳ Please wait a few seconds before sending another command.")
            return
        user_cooldowns[user_id] = now
        return await func(update, context, *args, **kwargs)
    return wrapper

# ==========================================
# BROWSER & AI INTEGRATIONS
# ==========================================
async def start_browser_pool(application: Application):
    init_db()
    logger.info("Initializing Global Browser Pool...")
    pool.playwright = await async_playwright().start()
    pool.browser = await pool.playwright.chromium.launch(
        headless=True, args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
    )
    logger.info("Browser Pool Ready.")
    
    await restore_watchers_from_db(application.bot)

async def restore_watchers_from_db(context_bot):
    try:
        with sqlite3.connect(get_db_path()) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT watcher_id, chat_id, url, actions_json, interval_seconds FROM watchers WHERE is_active = 1")
            rows = cursor.fetchall()
            
        restored_count = 0
        for w_id, chat_id, url, actions_json, interval in rows:
            actions = json.loads(actions_json)
            task = asyncio.create_task(watcher_loop(chat_id, url, actions, interval, w_id, context_bot))
            if chat_id not in active_watchers:
                active_watchers[chat_id] = {}
            active_watchers[chat_id][w_id] = task
            restored_count += 1
            
        if restored_count > 0:
            logger.info(f"Successfully restored {restored_count} active watcher(s) from SQLite database.")
    except Exception as e:
        logger.error(f"Failed to restore watchers from DB: {e}")

async def stop_browser_pool(application: Application):
    logger.info("Shutting down Browser Pool...")
    for user_watchers in active_watchers.values():
        for task in user_watchers.values():
            task.cancel()
    if pool.browser: await pool.browser.close()
    if pool.playwright: await pool.playwright.stop()

async def evaluate_ai_condition(prompt: str, page_text: str) -> bool:
    if not ai_model: return False
    try:
        query = f"Evaluate this condition: '{prompt}'. Return EXACTLY 'TRUE' if met, or 'FALSE' if not.\n\nData:\n{page_text[:30000]}"
        response = await asyncio.to_thread(ai_model.generate_content, query)
        return "TRUE" in response.text.upper()
    except Exception as e:
        logger.error(f"AI Condition Error: {e}")
        return False

# ==========================================
# CORE PIPELINE ENGINE
# ==========================================
async def execute_pipeline(page, browser_context, actions: List[str], user_id: int, status_msg=None) -> Dict[str, Any]:
    result = {"extracted": [], "condition_met": False, "screenshot_needed": True}
    
    for action in actions:
        if not action: continue
        
        safe_log = mask_sensitive_action(action)
        if status_msg: await status_msg.edit_text(f"⚡ Running: `{safe_log}`", parse_mode='Markdown')
        logger.info(f"Pipeline Action: {safe_log}")
        
        try:
            if action.startswith("type:"):
                selector, text = action.replace("type:", "", 1).split("=", 1)
                await page.locator(selector.strip()).fill(text.strip())
                
            elif action.startswith("click:"):
                await page.locator(action.replace("click:", "", 1).strip()).click(timeout=10000)
                
            elif action.startswith("wait:"):
                await page.wait_for_timeout(min(int(float(action.replace("wait:", "", 1).strip()) * 1000), 30000))
                
            elif action.startswith("extract:"):
                selector = action.replace("extract:", "", 1).strip()
                elements = await page.locator(selector).all_inner_texts()
                if elements:
                    cleaned = [t.strip() for t in elements if t.strip()]
                    result["extracted"].append(f"**Target `{selector}`:**\n" + "\n".join(f"• {t}" for t in cleaned[:10]))

            elif action.startswith("save_session:"):
                safe_name = sanitize_session_name(action.replace("save_session:", ""))
                session_state = await browser_context.storage_state()
                save_encrypted_session(user_id, safe_name, session_state)
                result["extracted"].append(f"🔒💾 **Encrypted session saved:** `{safe_name}`")

            elif action.startswith("condition_contains:"):
                target_text = action.replace("condition_contains:", "", 1).strip().lower()
                page_text = (await page.evaluate("document.body.innerText")).lower()
                if target_text in page_text:
                    result["condition_met"] = True
                    result["extracted"].append(f"🔔 **Condition Met:** Found '{target_text}'")

            elif action.startswith("condition_ai:"):
                prompt = action.replace("condition_ai:", "", 1).strip()
                page_text = await page.evaluate("document.body.innerText")
                if await evaluate_ai_condition(prompt, page_text):
                    result["condition_met"] = True
                    result["extracted"].append(f"🧠🔔 **AI Condition Met:** '{prompt}'")

        except Exception as e:
            logger.warning(f"Action Failed [{safe_log}]: {e}")
            result["extracted"].append(f"⚠️ Action failed: `{safe_log}`")
            
    return result

async def run_browser_task(url: str, actions: List[str], user_id: int, status_msg=None) -> Dict[str, Any]:
    context_opts = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {'width': 1280, 'height': 800}
    }

    if "proxy:on" in actions and PROXY_SERVER:
        context_opts["proxy"] = {"server": PROXY_SERVER, "username": PROXY_USERNAME, "password": PROXY_PASSWORD}

    for action in actions:
        if action.startswith("load_session:"):
            safe_name = sanitize_session_name(action.replace("load_session:", ""))
            session_state = load_encrypted_session(user_id, safe_name)
            if session_state:
                context_opts["storage_state"] = session_state

    browser_context = None
    page = None
    try:
        browser_context = await pool.browser.new_context(**context_opts)
        page = await browser_context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        
        if status_msg: await status_msg.edit_text(f"🌐 Navigating...")
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        await page.wait_for_timeout(2000)

        pipeline_res = await execute_pipeline(page, browser_context, actions, user_id, status_msg)
        
        screenshot_path = f"screenshot_{uuid.uuid4().hex}.png"
        await page.mouse.wheel(delta_x=0, delta_y=600)
        pipeline_res["title"] = await page.title()
        await page.screenshot(path=screenshot_path, full_page=True)
        pipeline_res["screenshot"] = screenshot_path
        
        return pipeline_res
    finally:
        if page: await page.close()
        if browser_context: await browser_context.close()

# ==========================================
# WATCHER ENGINE
# ==========================================
async def watcher_loop(chat_id: int, url: str, actions: List[str], interval: int, watcher_id: str, context_bot):
    logger.info(f"Started watcher {watcher_id} for {chat_id} on {url} (Interval: {interval}s)")
    
    try:
        while True:
            async with task_semaphore:
                try:
                    res = await asyncio.wait_for(run_browser_task(url, actions, chat_id), timeout=COMMAND_TIMEOUT)
                    
                    if res.get("condition_met"):
                        caption = truncate_text(f"🚨 *WATCHER ALERT* [{watcher_id}]\n📄 *Title:* {res['title']}\n🔗 {url}", 1024)
                        with open(res["screenshot"], 'rb') as photo:
                            await context_bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode='Markdown')
                        
                        if res["extracted"]:
                            await context_bot.send_message(chat_id=chat_id, text=truncate_text("\n\n".join(res["extracted"]), 4000), parse_mode='Markdown')
                        
                        await context_bot.send_message(chat_id=chat_id, text=f"✅ Condition met. Auto-stopping watcher `{watcher_id}`.")
                        deactivate_watcher_in_db(watcher_id)
                        break
                    
                    if os.path.exists(res.get("screenshot", "")): os.remove(res["screenshot"])
                        
                except asyncio.TimeoutError:
                    logger.warning(f"Watcher {watcher_id} timed out. Retrying next cycle.")
                except Exception as e:
                    logger.error(f"Watcher {watcher_id} error: {e}")
            
            await asyncio.sleep(interval)
            
    except asyncio.CancelledError:
        logger.info(f"Watcher {watcher_id} was cancelled.")
        deactivate_watcher_in_db(watcher_id)
    finally:
        if chat_id in active_watchers and watcher_id in active_watchers[chat_id]:
            del active_watchers[chat_id][watcher_id]

# ==========================================
# TELEGRAM HANDLERS
# ==========================================
@restricted
@rate_limited
async def check_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cmd_str = " ".join(context.args)
    if not cmd_str: return await update.message.reply_text("⚠️ Provide a URL.")

    parts = [p.strip() for p in cmd_str.split("|") if p.strip()]
    url = 'https://' + parts[0] if not parts[0].startswith(('http://', 'https://')) else parts[0]
    
    if not is_valid_url(url): 
        return await update.message.reply_text("⚠️ Invalid URL format.")
        
    if not is_domain_allowed(url):
        log_audit(user_id, "/check", url, "BLOCKED_DOMAIN_NOT_WHITELISTED")
        return await update.message.reply_text("⛔ *Domain Blocked:* This domain is not in the allowed whitelist.", parse_mode='Markdown')

    status_msg = await update.message.reply_text("⏳ Queued...")
    
    try:
        async with task_semaphore:
            res = await asyncio.wait_for(run_browser_task(url, parts[1:], user_id, status_msg), timeout=COMMAND_TIMEOUT)
            
            caption = truncate_text(f"📄 *Title:* {res.get('title')}\n🔗 *URL:* {url}", 1024)
            with open(res["screenshot"], 'rb') as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode='Markdown')
                
            if res["extracted"]:
                await context.bot.send_message(chat_id=chat_id, text=truncate_text("\n\n".join(res["extracted"]), 4000), parse_mode='Markdown')
                
            os.remove(res["screenshot"])
            await status_msg.delete()
            log_audit(user_id, "/check", url, "SUCCESS")
            
    except asyncio.TimeoutError:
        log_audit(user_id, "/check", url, "TIMEOUT")
        await status_msg.edit_text(f"❌ *Timeout:* The command exceeded the {COMMAND_TIMEOUT}s limit.", parse_mode='Markdown')
    except Exception as e:
        logger.exception("Task Error")
        log_audit(user_id, "/check", url, f"ERROR: {str(e)}")
        await status_msg.edit_text("❌ An error occurred.")

@restricted
async def watch_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    cmd_str = " ".join(context.args)
    
    if not cmd_str: return await update.message.reply_text("⚠️ Usage: `/watch https://site.com | every:60 | condition_contains:Stock`", parse_mode='Markdown')
    
    parts = [p.strip() for p in cmd_str.split("|") if p.strip()]
    url = 'https://' + parts[0] if not parts[0].startswith(('http://', 'https://')) else parts[0]
    
    if not is_domain_allowed(url):
        log_audit(user_id, "/watch", url, "BLOCKED_DOMAIN_NOT_WHITELISTED")
        return await update.message.reply_text("⛔ *Domain Blocked:* Domain not in whitelist.", parse_mode='Markdown')

    interval = 60
    actions = []
    for p in parts[1:]:
        if p.startswith("every:"):
            try: interval = max(int(p.replace("every:", "").strip()), 30)
            except: pass
        else:
            actions.append(p)
            
    watcher_id = uuid.uuid4().hex[:6]
    
    save_watcher_to_db(watcher_id, chat_id, url, actions, interval)
    
    task = asyncio.create_task(watcher_loop(chat_id, url, actions, interval, watcher_id, context.bot))
    
    if chat_id not in active_watchers: active_watchers[chat_id] = {}
    active_watchers[chat_id][watcher_id] = task
    
    log_audit(user_id, "/watch", url, f"CREATED_WATCHER_{watcher_id}")
    await update.message.reply_text(f"👀 *Watcher Started & Persisted*\nID: `{watcher_id}`\nInterval: `{interval}s`\nTarget: {url}", parse_mode='Markdown')

@restricted
async def list_watchers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    watchers = active_watchers.get(chat_id, {})
    if not watchers: return await update.message.reply_text("You have no active watchers.")
    msg = "*Active Watchers:*\n" + "\n".join(f"• ID: `{w_id}`" for w_id in watchers.keys())
    await update.message.reply_markdown(msg)

@restricted
async def stop_watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not context.args: return await update.message.reply_text("⚠️ Provide a watcher ID.")
    w_id = context.args[0]
    
    if chat_id in active_watchers and w_id in active_watchers[chat_id]:
        active_watchers[chat_id][w_id].cancel()
        deactivate_watcher_in_db(w_id)
        log_audit(user_id, "/stopwatch", None, f"STOPPED_WATCHER_{w_id}")
        await update.message.reply_text(f"🛑 Watcher `{w_id}` stopped.")
    else:
        await update.message.reply_text("⚠️ Watcher ID not found.")

@restricted
async def list_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    sessions = list_user_sessions(user_id)
    if not sessions: return await update.message.reply_text("No encrypted sessions found.")
    await update.message.reply_markdown("*Saved Encrypted Sessions:*\n" + "\n".join(f"• `{s}`" for s in sessions))

@restricted
async def delete_session(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not context.args: return await update.message.reply_text("⚠️ Usage: `/deletesession <name>`")
    safe_name = sanitize_session_name(context.args[0])
    if delete_user_session(user_id, safe_name):
        log_audit(user_id, "/deletesession", None, f"DELETED_SESSION_{safe_name}")
        await update.message.reply_text(f"🗑️ Encrypted session `{safe_name}` deleted.")
    else:
        await update.message.reply_text("⚠️ Session not found.")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("CRITICAL: TELEGRAM_BOT_TOKEN is missing!")
        return
        
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(start_browser_pool).post_stop(stop_browser_pool).build()
    
    app.add_handler(CommandHandler("check", check_url))
    app.add_handler(CommandHandler("watch", watch_url))
    app.add_handler(CommandHandler("watchers", list_watchers))
    app.add_handler(CommandHandler("stopwatch", stop_watch))
    app.add_handler(CommandHandler("sessions", list_sessions))
    app.add_handler(CommandHandler("deletesession", delete_session))
    
    logger.info("🚀 TeleScout Enterprise SQLite Engine Online.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()


import asyncio
import os
import logging
import re
import aiohttp
import psutil
from typing import List, Dict, Optional, Tuple
from urllib.parse import urlparse

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.error import TelegramError

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Browser, Playwright, BrowserContext
import google.generativeai as genai

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Security: Authorized Users
ALLOWED_USERS = set(
    int(uid.strip()) for uid in os.getenv("ALLOWED_TELEGRAM_USERS", "").split(",") if uid.strip().isdigit()
)

# Concurrency & Timeouts
MAX_CONCURRENT_TASKS = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))
task_semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)
DEFAULT_PAGE_TIMEOUT = 45000  # 45 seconds

# Proxies
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USERNAME = os.getenv("PROXY_USERNAME")
PROXY_PASSWORD = os.getenv("PROXY_PASSWORD")

# AI Setup
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')
else:
    ai_model = None

# Ensure persistence directories exist securely
SESSION_DIR = "sessions"
os.makedirs(SESSION_DIR, exist_ok=True)

# Global Browser Pool State
class BrowserPool:
    playwright: Optional[Playwright] = None
    browser: Optional[Browser] = None

pool = BrowserPool()

# ==========================================
# UTILITY & SECURITY FUNCTIONS
# ==========================================
def is_valid_url(url: str) -> bool:
    """Strict URL validation to prevent malformed requests."""
    try:
        result = urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except Exception:
        return False

def sanitize_session_name(name: str) -> str:
    """Prevents Path Traversal attacks by sanitizing filenames."""
    # Strip whitespace and replace any non-alphanumeric character (except _ and -) with underscore
    sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', name.strip())
    # Additionally, replace any leading dashes with underscores to prevent issues
    sanitized = re.sub(r'^-+', '_', sanitized)
    return sanitized
    
def truncate_text(text: str, max_length: int = 4000) -> str:
    """Safely truncates text for Telegram message limits."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 15] + "\n...[Truncated]"

# ==========================================
# EXTERNAL INTEGRATIONS
# ==========================================
async def solve_recaptcha_v2(site_url: str, site_key: str) -> Optional[str]:
    """Asynchronous CapSolver integration with tight error boundaries."""
    if not CAPSOLVER_API_KEY:
        return None
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "clientKey": CAPSOLVER_API_KEY, 
                "task": {"type": "ReCaptchaV2TaskProxyLess", "websiteURL": site_url, "websiteKey": site_key}
            }
            async with session.post("https://api.capsolver.com/createTask", json=payload, timeout=10) as resp:
                data = await resp.json()
                if data.get("errorId", 0) != 0:
                    logger.warning(f"CapSolver Error: {data}")
                    return None
                task_id = data.get("taskId")

            # Polling loop with hard limit
            for _ in range(25):  # Max 50 seconds wait
                await asyncio.sleep(2)
                async with session.post("https://api.capsolver.com/getTaskResult", json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id}, timeout=10) as resp:
                    res = await resp.json()
                    status = res.get("status")
                    if status == "ready":
                        return res.get("solution", {}).get("gRecaptchaResponse")
                    elif status == "failed":
                        return None
    except Exception as e:
        logger.error(f"CapSolver Network Error: {e}")
    return None

async def extract_via_ai(prompt: str, page_text: str) -> str:
    """Handles AI text extraction cleanly."""
    if not ai_model:
        return "⚠️ AI Extraction failed: GEMINI_API_KEY missing."
    try:
        # Cap text payload to avoid hitting token limits
        safe_text = page_text[:45000]
        response = await asyncio.to_thread(
            ai_model.generate_content, 
            f"Extract strictly based on the prompt. Be concise.\nPrompt: {prompt}\nContent:\n{safe_text}"
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"AI Generation Error: {e}")
        return f"⚠️ AI Error: {str(e)}"

# ==========================================
# BROWSER LIFECYCLE MANAGEMENT
# ==========================================
async def start_browser_pool(application: Application):
    """Initializes the background Chromium engine safely."""
    logger.info("Initializing Global Browser Pool...")
    pool.playwright = await async_playwright().start()
    pool.browser = await pool.playwright.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled", 
            "--no-sandbox", 
            "--disable-dev-shm-usage",
            "--disable-gpu"
        ]
    )
    logger.info("Browser Pool Ready & Awaiting Tasks.")

async def stop_browser_pool(application: Application):
    """Graceful shutdown sequence."""
    logger.info("Shutting down Browser Pool...")
    if pool.browser:
        await pool.browser.close()
    if pool.playwright:
        await pool.playwright.stop()
    logger.info("Shutdown complete.")

# ==========================================
# ACTION PIPELINE ENGINE
# ==========================================
async def execute_pipeline(page, browser_context: BrowserContext, actions: List[str], status_message) -> List[str]:
    """Executes structural commands and returns extracted data strings."""
    extracted_data = []
    
    for action in actions:
        if not action: continue
        await status_message.edit_text(f"⚡ Running action: `{action}`", parse_mode='Markdown')
        
        try:
            if action.startswith("type:"):
                # Split only on the first '=' to allow '=' in the text being typed
                selector, text = action.replace("type:", "", 1).split("=", 1)
                await page.locator(selector.strip()).fill(text.strip())
                
            elif action.startswith("click:"):
                selector = action.replace("click:", "", 1).strip()
                await page.locator(selector).click(timeout=10000)
                
            elif action.startswith("wait:"):
                seconds = float(action.replace("wait:", "", 1).strip())
                # Cap wait times to prevent malicious hanging
                await page.wait_for_timeout(min(int(seconds * 1000), 30000))
                
            elif action.startswith("extract:"):
                selector = action.replace("extract:", "", 1).strip()
                elements = await page.locator(selector).all_inner_texts()
                if elements:
                    cleaned = [t.strip() for t in elements if t.strip()]
                    formatted_res = "\n".join(f"• {t}" for t in cleaned[:10])
                    extracted_data.append(f"**Target `{selector}`:**\n{formatted_res}")

            elif action.startswith("ai_extract:"):
                prompt = action.replace("ai_extract:", "", 1).strip()
                page_text = await page.evaluate("document.body.innerText")
                ai_result = await extract_via_ai(prompt, page_text)
                extracted_data.append(f"🧠 **AI Result:**\n{ai_result}")

            elif action.startswith("save_session:"):
                raw_name = action.replace("save_session:", "").strip()
                safe_name = sanitize_session_name(raw_name)
                await browser_context.storage_state(path=f"{SESSION_DIR}/{safe_name}.json")
                extracted_data.append(f"💾 **Session saved as:** `{safe_name}`")

        except Exception as action_err:
            logger.warning(f"Pipeline Action Failed [{action}]: {action_err}")
            extracted_data.append(f"⚠️ Action failed: `{action}`")
            
    return extracted_data

# ==========================================
# TELEGRAM HANDLERS
# ==========================================
def restricted(func):
    """Access control decorator."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        if ALLOWED_USERS and user_id not in ALLOWED_USERS:
            logger.warning(f"Unauthorized access by ID {user_id}")
            await update.message.reply_text("⛔ *Access Denied.*", parse_mode='Markdown')
            return
        return await func(update, context, *args, **kwargs)
    return wrapper

@restricted
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = (
        "🤖 *TeleScout AI Automation Agent*\n\n"
        "Commands:\n"
        "• `/check <URL> | <actions>` — Execute pipeline\n"
        "• `/health` — Diagnostics"
    )
    await update.message.reply_markdown(welcome)

@restricted
async def health_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = psutil.virtual_memory()
    cpu = psutil.cpu_percent(interval=0.5)
    b_status = "🟢 Active" if pool.browser and pool.browser.is_connected() else "🔴 Offline"
    
    msg = (
        "📊 *Server Diagnostics*\n"
        f"• *Engine:* {b_status}\n"
        f"• *CPU:* `{cpu}%`\n"
        f"• *RAM:* `{mem.percent}%` ({mem.used // 1048576}MB / {mem.total // 1048576}MB)\n"
        f"• *Queue Limit:* `{MAX_CONCURRENT_TASKS} max tabs`"
    )
    await update.message.reply_markdown(msg)

@restricted
async def check_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    full_command = " ".join(context.args)
    
    if not full_command:
        await update.message.reply_text("⚠️ Please provide a URL.")
        return

    # Parse command safely
    parts = [p.strip() for p in full_command.split("|") if p.strip()]
    url = parts[0]
    actions = parts[1:] if len(parts) > 1 else []

    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    if not is_valid_url(url):
        await update.message.reply_text("⚠️ Invalid URL provided.")
        return

    status_msg = await update.message.reply_text("⏳ Queued (waiting for concurrency slot)...")
    screenshot_path = f"screenshot_{chat_id}.png"
    extracted_data = []

    # Acquire concurrency slot
    async with task_semaphore:
        browser_context = None
        page = None
        
        try:
            await status_msg.edit_text(f"⏳ Processing {url}...")
            
            # Setup context options (Proxies & Sessions)
            context_opts = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "viewport": {'width': 1280, 'height': 800},
                "locale": "en-US"
            }

            if "proxy:on" in actions and PROXY_SERVER:
                context_opts["proxy"] = {"server": PROXY_SERVER, "username": PROXY_USERNAME, "password": PROXY_PASSWORD}

            for action in actions:
                if action.startswith("load_session:"):
                    safe_name = sanitize_session_name(action.replace("load_session:", ""))
                    s_path = f"{SESSION_DIR}/{safe_name}.json"
                    if os.path.exists(s_path):
                        context_opts["storage_state"] = s_path

            # Isolate browser context and page
            browser_context = await pool.browser.new_context(**context_opts)
            page = await browser_context.new_page()
            
            # Evasion script
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            
            # Navigation
            await status_msg.edit_text(f"🌐 Navigating to URL...")
            await page.goto(url, wait_until="domcontentloaded", timeout=DEFAULT_PAGE_TIMEOUT)
            await page.wait_for_timeout(2000)

            # Execute actions
            if actions:
                extracted_data = await execute_pipeline(page, browser_context, actions, status_msg)

            # CAPTCHA Inspection Post-Actions
            captcha_frame = page.locator('iframe[src*="recaptcha/api2/anchor"]')
            if await captcha_frame.count() > 0 and CAPSOLVER_API_KEY:
                await status_msg.edit_text("🧩 CAPTCHA detected. Solving...")
                sitekey_el = page.locator('.g-recaptcha, [data-sitekey]')
                if await sitekey_el.count() > 0:
                    sitekey = await sitekey_el.first.get_attribute("data-sitekey")
                    token = await solve_recaptcha_v2(page.url, sitekey)
                    if token:
                        await page.evaluate(f'document.getElementById("g-recaptcha-response").value="{token}";')
                        await page.evaluate('if(typeof recaptchaCallback === "function") { recaptchaCallback(); }')
                        await page.wait_for_timeout(3000)

            # Capture Snapshot
            await page.mouse.wheel(delta_x=0, delta_y=600)
            page_title = await page.title()
            await status_msg.edit_text("📸 Capturing screenshot...")
            await page.screenshot(path=screenshot_path, full_page=True)

        except PlaywrightTimeoutError:
            await status_msg.edit_text("❌ Timeout: The site took too long to load or respond.")
            return # Exit safely, context will be cleaned in finally block
            
        except Exception as e:
            logger.exception("Critical error during browser automation phase.")
            await status_msg.edit_text("❌ An unexpected automation error occurred.")
            return

        finally:
            # STRICT RESOURCE CLEANUP: Always runs, even if exceptions occur
            if page: await page.close()
            if browser_context: await browser_context.close()

    # --- TELEGRAM UPLOAD PHASE ---
    try:
        if os.path.exists(screenshot_path):
            caption = truncate_text(f"📄 *Title:* {page_title}\n🔗 *URL:* {url}", 1024) # Telegram photo caption limit
            with open(screenshot_path, 'rb') as photo:
                await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode='Markdown')
            os.remove(screenshot_path)
            
        if extracted_data:
            data_msg = truncate_text("\n\n".join(extracted_data), 4000) # Telegram text message limit
            await context.bot.send_message(chat_id=chat_id, text=data_msg, parse_mode='Markdown')
            
        await status_msg.delete()
        
    except TelegramError as e:
        logger.error(f"Failed to send messages to Telegram: {e}")

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("CRITICAL: TELEGRAM_BOT_TOKEN is missing! Exiting.")
        return
        
    app = Application.builder().token(TELEGRAM_BOT_TOKEN) \
        .post_init(start_browser_pool) \
        .post_stop(stop_browser_pool) \
        .build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("health", health_check))
    app.add_handler(CommandHandler("check", check_url))
    
    logger.info("🚀 TeleScout Core Online. Polling Telegram...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()



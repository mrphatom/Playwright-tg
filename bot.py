import asyncio
import os
import logging
import json
from urllib.parse import urlparse
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import google.generativeai as genai

# ==========================================
# CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CAPSOLVER_API_KEY = os.environ.get("CAPSOLVER_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

# Proxy Configuration (Optional, for anti-ban)
PROXY_SERVER = os.environ.get("PROXY_SERVER")
PROXY_USERNAME = os.environ.get("PROXY_USERNAME")
PROXY_PASSWORD = os.environ.get("PROXY_PASSWORD")

# Initialize Gemini AI if available
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    ai_model = genai.GenerativeModel('gemini-1.5-flash')

# Ensure sessions directory exists for login persistence
os.makedirs("sessions", exist_ok=True)

# Global Playwright variables for pooling
playwright_manager = None
global_browser = None

# ==========================================
# BACKGROUND SERVICES
# ==========================================
async def start_browser_pool(application: Application):
    """Starts a single, persistent browser instance to save RAM and time."""
    global playwright_manager, global_browser
    logger.info("Initializing Global Browser Pool...")
    playwright_manager = await async_playwright().start()
    global_browser = await playwright_manager.chromium.launch(
        headless=True,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
    )
    logger.info("Browser Pool Ready.")

async def stop_browser_pool(application: Application):
    """Cleans up the browser when the bot shuts down."""
    global global_browser, playwright_manager
    if global_browser:
        await global_browser.close()
    if playwright_manager:
        await playwright_manager.stop()
    logger.info("Browser Pool Closed.")

async def solve_recaptcha_v2(site_url: str, site_key: str) -> str:
    """Solves reCAPTCHA v2 using CapSolver API."""
    if not CAPSOLVER_API_KEY:
        return None
    async with aiohttp.ClientSession() as session:
        payload = {"clientKey": CAPSOLVER_API_KEY, "task": {"type": "ReCaptchaV2TaskProxyLess", "websiteURL": site_url, "websiteKey": site_key}}
        async with session.post("https://api.capsolver.com/createTask", json=payload) as resp:
            data = await resp.json()
            if data.get("errorId", 0) != 0: return None
            task_id = data.get("taskId")

        for _ in range(30):
            await asyncio.sleep(2)
            async with session.post("https://api.capsolver.com/getTaskResult", json={"clientKey": CAPSOLVER_API_KEY, "taskId": task_id}) as resp:
                res = await resp.json()
                if res.get("status") == "ready": return res.get("solution", {}).get("gRecaptchaResponse")
                elif res.get("status") == "failed": return None
    return None

# ==========================================
# BOT COMMANDS
# ==========================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 *Welcome to the Ultimate Web Automation Bot!*\n\n"
        "*Advanced Commands (Chain with `|`):*\n"
        "• `type:<selector>=<text>` - Type into fields\n"
        "• `click:<selector>` - Click buttons\n"
        "• `wait:<seconds>` - Pause execution\n"
        "• `extract:<selector>` - Get text from elements\n"
        "• `ai_extract:<prompt>` - Use AI to read the page and answer your prompt\n"
        "• `save_session:<name>` - Save cookies/login\n"
        "• `load_session:<name>` - Load cookies/login\n"
        "• `proxy:on` - Use residential proxies\n\n"
        "*Example AI Extraction:*\n"
        "`/check https://apple.com/iphone | ai_extract:What is the starting price?`"
    )
    await update.message.reply_markdown(welcome_text)

async def check_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global global_browser
    chat_id = update.effective_chat.id
    
    full_command = " ".join(context.args)
    if not full_command:
        await update.message.reply_text("⚠️ Please provide a URL.")
        return

    parts = [p.strip() for p in full_command.split("|")]
    url = parts[0]
    actions = parts[1:] if len(parts) > 1 else []

    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    status_message = await update.message.reply_text(f"⏳ Processing {url}...")
    screenshot_path = f"screenshot_{chat_id}.png"
    extracted_data = []
    
    # 1. Pre-computation: Check for Proxies & Sessions before creating context
    context_options = {
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "viewport": {'width': 1280, 'height': 800}
    }

    if "proxy:on" in actions and PROXY_SERVER:
        context_options["proxy"] = {
            "server": PROXY_SERVER,
            "username": PROXY_USERNAME,
            "password": PROXY_PASSWORD
        }
        await status_message.edit_text("🛡️ Utilizing proxy network...")

    for action in actions:
        if action.startswith("load_session:"):
            session_name = action.replace("load_session:", "").strip()
            session_path = f"sessions/{session_name}.json"
            if os.path.exists(session_path):
                context_options["storage_state"] = session_path
                await status_message.edit_text(f"🍪 Loaded session: `{session_name}`", parse_mode='Markdown')

    try:
        # Create a fresh isolated context from the pooled browser
        browser_context = await global_browser.new_context(**context_options)
        page = await browser_context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
        
        await status_message.edit_text(f"🌐 Loading {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=40000)
        await page.wait_for_timeout(2000)

        # 2. Execute Action Pipeline
        for action in actions:
            await status_message.edit_text(f"⚡ Executing: `{action}`", parse_mode='Markdown')
            try:
                if action.startswith("type:"):
                    selector, text = action.replace("type:", "", 1).split("=", 1)
                    await page.locator(selector).fill(text)
                    
                elif action.startswith("click:"):
                    selector = action.replace("click:", "", 1)
                    await page.locator(selector).click()
                    
                elif action.startswith("wait:"):
                    seconds = float(action.replace("wait:", "", 1))
                    await page.wait_for_timeout(int(seconds * 1000))
                    
                elif action.startswith("extract:"):
                    selector = action.replace("extract:", "", 1)
                    elements = await page.locator(selector).all_inner_texts()
                    if elements:
                        cleaned = [t.strip() for t in elements if t.strip()]
                        extracted_data.append(f"**Target `{selector}`:**\n" + "\n".join(f"• {t}" for t in cleaned[:10]))

                elif action.startswith("ai_extract:"):
                    if not GEMINI_API_KEY:
                        extracted_data.append("⚠️ AI Extraction failed: GEMINI_API_KEY missing.")
                        continue
                        
                    prompt = action.replace("ai_extract:", "", 1)
                    await status_message.edit_text("🧠 AI is analyzing the page content...")
                    page_text = await page.evaluate("document.body.innerText")
                    
                    # Send text to LLM
                    response = ai_model.generate_content(
                        f"Extract information based on the user's prompt. Be concise.\n\n"
                        f"User Prompt: {prompt}\n\n"
                        f"Page Content:\n{page_text[:50000]}" # Limit chars to avoid hitting max limits
                    )
                    extracted_data.append(f"🧠 **AI Result for** '{prompt}':\n{response.text.strip()}")

                elif action.startswith("save_session:"):
                    session_name = action.replace("save_session:", "").strip()
                    await browser_context.storage_state(path=f"sessions/{session_name}.json")
                    extracted_data.append(f"💾 **Session saved successfully as:** `{session_name}`")

            except Exception as action_err:
                logger.error(f"Action failed: {action} - {action_err}")
                extracted_data.append(f"⚠️ Action failed: `{action}`")

        # 3. Handle CAPTCHAs silently if triggered
        captcha_frame = page.locator('iframe[src*="recaptcha/api2/anchor"]')
        if await captcha_frame.count() > 0 and CAPSOLVER_API_KEY:
            await status_message.edit_text("🧩 CAPTCHA detected! Solving...")
            sitekey_el = page.locator('.g-recaptcha, [data-sitekey]')
            if await sitekey_el.count() > 0:
                token = await solve_recaptcha_v2(page.url, await sitekey_el.first.get_attribute("data-sitekey"))
                if token:
                    await page.evaluate(f'document.getElementById("g-recaptcha-response").value="{token}";')
                    await page.evaluate('if(typeof recaptchaCallback === "function") { recaptchaCallback(); }')
                    await page.wait_for_timeout(3000)

        # 4. Final Screenshot
        await page.mouse.wheel(delta_x=0, delta_y=600)
        page_title = await page.title()
        await status_message.edit_text("📸 Capturing screenshot...")
        await page.screenshot(path=screenshot_path, full_page=True)
        
        # 5. Cleanup context (NOT the global browser)
        await browser_context.close()

        # Send Data to Telegram
        caption = f"📄 *Title:* {page_title}\n🔗 *URL:* {url}"
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode='Markdown')
            
        if extracted_data:
            data_message = "\n\n".join(extracted_data)
            if len(data_message) > 4000: data_message = data_message[:4000] + "\n...[Truncated]"
            await context.bot.send_message(chat_id=chat_id, text=data_message, parse_mode='Markdown')

        await status_message.delete()
        os.remove(screenshot_path)

    except PlaywrightTimeoutError:
        await status_message.edit_text("❌ Timed out.")
    except Exception as e:
        logger.error(f"Error checking URL: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN is missing!")
        return
        
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(start_browser_pool).post_stop(stop_browser_pool).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_url))
    
    logger.info("Starting Advanced Bot Event Loop...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()


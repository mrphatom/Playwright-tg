import asyncio
import os
import logging
from urllib.parse import urlparse
import aiohttp
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CAPSOLVER_API_KEY = os.environ.get("CAPSOLVER_API_KEY")

def is_valid_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🤖 *Welcome to the Advanced Web Automation Bot!*\n\n"
        "*Basic Usage:*\n`/check https://example.com`\n\n"
        "*Advanced Usage (Action Pipeline):*\n"
        "You can chain commands using the `|` character.\n"
        "Available actions: `type:<selector>=<text>`, `click:<selector>`, `wait:<seconds>`\n\n"
        "*Example:*\n`/check https://wikipedia.org | type:#searchInput=Python | click:button[type='submit'] | wait:2`"
    )
    await update.message.reply_markdown(welcome_text)

async def check_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    
    # Reconstruct the full message string so we can parse the pipe (|) separators
    full_command = " ".join(context.args)
    
    if not full_command:
        await update.message.reply_text("⚠️ Please provide a URL. Example: /check https://example.com")
        return

    # Split the command into the URL and the subsequent actions
    parts = [p.strip() for p in full_command.split("|")]
    url = parts[0]
    actions = parts[1:] if len(parts) > 1 else []

    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    if not is_valid_url(url):
        await update.message.reply_text("⚠️ Invalid URL provided.")
        return

    status_message = await update.message.reply_text(f"⏳ Launching browser for {url}...")
    screenshot_path = f"screenshot_{chat_id}.png"
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            browser_context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            page = await browser_context.new_page()

            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
            
            await status_message.edit_text(f"🌐 Loading {url}...")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(2000) # Initial buffer for JS

            # -- ACTION PIPELINE EXECUTION --
            if actions:
                for action in actions:
                    await status_message.edit_text(f"⚡ Executing: `{action}`", parse_mode='Markdown')
                    try:
                        if action.startswith("type:"):
                            # Format: type:#username=my_user
                            selector_and_text = action.replace("type:", "", 1)
                            selector, text = selector_and_text.split("=", 1)
                            await page.locator(selector).fill(text)
                            
                        elif action.startswith("click:"):
                            # Format: click:#submitBtn
                            selector = action.replace("click:", "", 1)
                            await page.locator(selector).click()
                            
                        elif action.startswith("wait:"):
                            # Format: wait:3
                            seconds = float(action.replace("wait:", "", 1))
                            await page.wait_for_timeout(int(seconds * 1000))
                            
                    except Exception as action_err:
                        logger.error(f"Action failed: {action} - {action_err}")
                        await update.message.reply_text(f"⚠️ Action failed: `{action}`\nCheck your CSS selector.", parse_mode='Markdown')

            # -- CAPTCHA CHECK (Post-Actions) --
            # Sometimes an action (like clicking login) triggers a captcha
            captcha_frame = page.locator('iframe[src*="recaptcha/api2/anchor"]')
            if await captcha_frame.count() > 0 and CAPSOLVER_API_KEY:
                await status_message.edit_text("🧩 CAPTCHA detected! Solving...")
                sitekey_el = page.locator('.g-recaptcha, [data-sitekey]')
                if await sitekey_el.count() > 0:
                    sitekey = await sitekey_el.first.get_attribute("data-sitekey")
                    token = await solve_recaptcha_v2(page.url, sitekey)
                    if token:
                        await page.evaluate(f'document.getElementById("g-recaptcha-response").value="{token}";')
                        await page.evaluate('if(typeof recaptchaCallback === "function") { recaptchaCallback(); }')
                        await page.wait_for_timeout(3000)

            await page.mouse.wheel(delta_x=0, delta_y=600)
            await page.wait_for_timeout(1000)
            page_title = await page.title()
            
            await status_message.edit_text("📸 Capturing final screenshot...")
            await page.screenshot(path=screenshot_path, full_page=True)
            await browser.close()

        caption = f"📄 *Title:* {page_title}\n🔗 *URL:* {url}"
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(chat_id=chat_id, photo=photo, caption=caption, parse_mode='Markdown')
            
        await status_message.delete()
        os.remove(screenshot_path)

    except PlaywrightTimeoutError:
        await status_message.edit_text("❌ Timed out loading page or finding elements.")
    except Exception as e:
        logger.error(f"Error checking URL: {e}")
        await status_message.edit_text(f"❌ Error: {str(e)}")
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_url))
    logger.info("Bot with Action Pipeline is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()



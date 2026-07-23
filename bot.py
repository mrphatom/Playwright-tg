import asyncio
import os
import logging
from urllib.parse import urlparse
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Set up logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Fetch the token from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

def is_valid_url(url):
    """Basic URL validation."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the command /start is issued."""
    welcome_text = (
        "🤖 *Welcome to the Web Automation Bot!*\n\n"
        "Send me a link using the `/check` command, and I will spin up a browser, "
        "visit the site, and send you back a screenshot and data.\n\n"
        "*Example:* `/check https://en.wikipedia.org/wiki/Web_scraping`"
    )
    await update.message.reply_markdown(welcome_text)

async def check_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /check command, runs Playwright, and returns the result."""
    chat_id = update.effective_chat.id
    
    if not context.args:
        await update.message.reply_text("⚠️ Please provide a URL. Example: /check https://example.com")
        return

    url = context.args[0]
    
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    if not is_valid_url(url):
        await update.message.reply_text("⚠️ Invalid URL provided. Please include http:// or https://")
        return

    status_message = await update.message.reply_text(f"⏳ Spinning up browser and navigating to {url}...")
    screenshot_path = f"screenshot_{chat_id}.png"
    
    try:
        async with async_playwright() as p:
            # Headless chromium launch
            browser = await p.chromium.launch(headless=True)
            
            # Create a context with a realistic user agent and viewport
            browser_context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1280, 'height': 800}
            )
            
            page = await browser_context.new_page()
            
            await status_message.edit_text(f"🌐 Loading {url}...")
            # Wait until network is mostly idle to ensure JS renders
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # --- INTERACTION ---
            await page.mouse.wheel(delta_x=0, delta_y=1000)
            await page.wait_for_timeout(1000)
            
            page_title = await page.title()
            
            # --- CAPTCHA PLACEHOLDER ---
            # e.g., send sitekey to Anti-Captcha/CapSolver, wait for token, inject, and submit.
            
            await status_message.edit_text(f"📸 Capturing screenshot...")
            await page.screenshot(path=screenshot_path, full_page=True)
            
            await browser.close()

        await status_message.edit_text("✅ Scraping complete! Uploading results...")
        
        caption = f"📄 *Title:* {page_title}\n🔗 *URL:* {url}"
        
        with open(screenshot_path, 'rb') as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption,
                parse_mode='Markdown'
            )
            
        await status_message.delete()
        os.remove(screenshot_path)

    except PlaywrightTimeoutError:
        await status_message.edit_text("❌ Timed out. The site might be down, loading too slowly, or blocking bots.")
    except Exception as e:
        logger.error(f"Error checking URL: {e}")
        await status_message.edit_text(f"❌ An error occurred: {str(e)}")
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("check", check_url))

    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()


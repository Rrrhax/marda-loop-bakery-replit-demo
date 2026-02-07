"""
Marda Loop Bakery Telegram Bot - Optimized
Supports polling mode (webhook requires SSL)
"""
import os
import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.enums import ParseMode
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

API_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'https://your-app.onrender.com')

if not API_TOKEN:
    logger.error("Set TELEGRAM_TOKEN env var")
    exit(1)

if 'your-app' in WEBAPP_URL:
    logger.warning("Update WEBAPP_URL to your actual deployed URL!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Handle /start command with WebApp button"""
    kb = [
        [KeyboardButton(
            text="🛒 Open Bakery Shop", 
            web_app=WebAppInfo(url=WEBAPP_URL)
        )]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    
    welcome_text = (
        "🥐 <b>Welcome to Marda Loop Bakery!</b>\n\n"
        "Click the button below to browse our menu and place orders.\n"
        "Fresh pastries, artisan coffee, and more!"
    )
    
    await message.answer(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)


@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def web_app_data_handler(message: types.Message):
    """Handle order confirmation from WebApp"""
    try:
        import json
        data = json.loads(message.web_app_data.data)
        items = data.get('items', [])
        total = data.get('total', 0)
        
        # Format order summary
        items_str = '\n'.join(f"• {item}" for item in items) if isinstance(items, list) else str(items)
        
        order_summary = (
            f"✅ <b>Order Received!</b>\n\n"
            f"<b>Items:</b>\n{items_str}\n\n"
            f"<b>Total:</b> ${total:.2f}\n\n"
            f"🕐 <i>Pickup in 15 minutes!</i>"
        )
        
        # Add confirmation buttons
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📞 Call Bakery", url="tel:+14035551234"),
                InlineKeyboardButton(text="📍 Directions", url="https://maps.google.com/?q=Marda+Loop+Calgary")
            ]
        ])
        
        await message.answer(order_summary, reply_markup=kb, parse_mode=ParseMode.HTML)
        logger.info(f"Order confirmed for user {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Error processing WebApp data: {e}")
        await message.answer("❌ Sorry, there was an error processing your order. Please try again.")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Show help information"""
    help_text = (
        "<b>🥐 Marda Loop Bakery Bot</b>\n\n"
        "<b>Commands:</b>\n"
        "/start - Open the bakery shop\n"
        "/help - Show this help message\n"
        "/status - Check your recent orders\n\n"
        "<b>How to order:</b>\n"
        "1. Click '🛒 Open Bakery Shop'\n"
        "2. Browse the menu\n"
        "3. Add items to your cart\n"
        "4. Confirm your order\n"
        "5. Pick up in 15 minutes!"
    )
    await message.answer(help_text, parse_mode=ParseMode.HTML)


@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    """Check order status - would connect to DB in full implementation"""
    await message.answer(
        "📊 <b>Order Status</b>\n\n"
        "Feature coming soon! You'll be able to see your recent orders here.",
        parse_mode=ParseMode.HTML
    )


@dp.message()
async def handle_other(message: types.Message):
    """Handle any other messages"""
    await message.answer(
        "👋 Hi! I'm the Marda Loop Bakery bot.\n\n"
        "Use /start to open the shop or /help for more info."
    )


async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

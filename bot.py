import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import WebAppInfo, ReplyKeyboardMarkup, KeyboardButton
from aiogram import F

API_TOKEN = os.getenv('TELEGRAM_TOKEN')
WEBAPP_URL = os.getenv('WEBAPP_URL', 'http://localhost:5000')

if not API_TOKEN:
    print("Set TELEGRAM_TOKEN env var")
    exit(1)

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message(F.text == "/start")
async def cmd_start(message: types.Message):
    kb = [
        [KeyboardButton(text="🛒 Open Bakery Shop", web_app=WebAppInfo(url=WEBAPP_URL))]
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
    await message.answer("Welcome to Marda Loop Bakery! Click to order.", reply_markup=keyboard)

@dp.message(F.content_type == types.ContentType.WEB_APP_DATA)
async def web_app_data_handler(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        items = data.get('items', [])
        total = data.get('total', 0)
        items_str = ', '.join(items) if isinstance(items, list) else str(items)
        await message.answer(f"✅ Order #{len(items) or 0} items\nItems: {items_str}\nTotal: ${total:.2f}\n\nPickup in 15min!")
    except json.JSONDecodeError:
        await message.answer("❌ Invalid order data.")

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())

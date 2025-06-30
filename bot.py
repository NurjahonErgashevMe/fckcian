import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import settings  # Импортируем обработчики настроек
from utils import file_utils

# Инициализация бота
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def setup_handlers():
    dp.include_router(settings.router)

async def main():
    setup_handlers()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
import asyncio
import logging
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN
from core.database import init_db
from services.notifier import check_coupons_today
from handlers.commands import register_handlers

logging.basicConfig(level=logging.INFO)

async def main():
    await init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    register_handlers(dp)

    scheduler = AsyncIOScheduler()

    async def job():
        await check_coupons_today(bot)

    # Проверка каждый день в 10:00 утра
    scheduler.add_job(job, "cron", hour=10, minute=0)
    scheduler.start()

    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
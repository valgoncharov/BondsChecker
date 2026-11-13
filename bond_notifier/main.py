import asyncio
import contextlib
import logging
import ssl

import aiohttp
import certifi
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, TIMEZONE
from core.database import init_db
from handlers.commands import register_handlers
from handlers.errors import register_error_handlers
from services.cache import refresh_all
from services.notifier import REMINDER_HOUR, catch_up_reminders, send_reminders

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=30)


def build_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context


async def main() -> None:
    await init_db()

    session = aiohttp.ClientSession(
        timeout=REQUEST_TIMEOUT,
        connector=aiohttp.TCPConnector(ssl=build_ssl_context()),
    )
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    register_handlers(dp, session)
    register_error_handlers(dp)

    scheduler = AsyncIOScheduler(
        timezone=TIMEZONE,
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 3600,
        },
    )

    async def refresh_job() -> None:
        await refresh_all(session)

    async def day_before_job() -> None:
        await send_reminders(bot, "day_before")

    async def day_of_job() -> None:
        await send_reminders(bot, "day_of")

    scheduler.add_job(day_before_job, "cron", hour=REMINDER_HOUR, minute=0)
    scheduler.add_job(day_of_job, "cron", hour=REMINDER_HOUR, minute=0)
    scheduler.add_job(refresh_job, "cron", day_of_week="mon", hour=3, minute=0)
    scheduler.start()

    async def startup_job() -> None:
        try:
            await refresh_all(session)
            await catch_up_reminders(bot)
        except Exception:
            logger.exception("Ошибка стартового обновления кэша и напоминаний")

    startup_task = asyncio.create_task(startup_job())

    try:
        await dp.start_polling(bot)
    finally:
        if not startup_task.done():
            startup_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await startup_task
        scheduler.shutdown(wait=False)
        await session.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

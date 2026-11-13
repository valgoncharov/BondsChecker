import asyncio
import logging

import aiohttp

from core.database import (
    get_secids_to_refresh,
    mark_security_fetched,
    replace_coupons,
    upsert_security,
)
from services.moex import fetch_coupons

logger = logging.getLogger(__name__)

MAX_CONCURRENCY = 5


async def refresh_one(session: aiohttp.ClientSession, secid: str) -> bool:
    coupons = await fetch_coupons(session, secid)

    if coupons is None:
        await upsert_security(secid)
        await mark_security_fetched(secid, "ошибка запроса к MOEX ISS")
        logger.warning("Не удалось обновить купоны для %s", secid)
        return False

    await replace_coupons(secid, coupons)

    if coupons:
        first = coupons[0]
        await upsert_security(secid, first.isin, first.name, first.faceunit)
    else:
        await upsert_security(secid)

    await mark_security_fetched(secid)
    logger.info("Обновлено купонов для %s: %d", secid, len(coupons))
    return True


async def refresh_all(
    session: aiohttp.ClientSession, max_age_days: int = 7
) -> int:
    secids: list[str] = await get_secids_to_refresh(max_age_days)
    if not secids:
        logger.info("Кэш купонов актуален, обновление не требуется")
        return 0

    semaphore = asyncio.Semaphore(MAX_CONCURRENCY)

    async def worker(secid: str) -> bool:
        async with semaphore:
            return await refresh_one(session, secid)

    results = await asyncio.gather(*(worker(secid) for secid in secids))
    updated = sum(1 for ok in results if ok)
    logger.info("Обновление кэша завершено: %d/%d", updated, len(secids))
    return updated

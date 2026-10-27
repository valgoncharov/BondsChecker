import aiohttp
import logging
from datetime import datetime, date
from typing import List, Optional

from config import MOEX_ISS_BASE
from core.models import CouponPayment

logger = logging.getLogger(__name__)


async def get_coupons(session: aiohttp.ClientSession, secid: str) -> List[CouponPayment]:
    """
    Получает график купонов по облигации из MOEX ISS.
    Эндпоинт: /statistics/engines/stock/markets/bonds/bondization/{secid}
    Возвращает список купонов, отсортированный по дате.
    """
    url = f"{MOEX_ISS_BASE}/statistics/engines/stock/markets/bonds/bondization/{secid}.json"
    try:
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning(f"MOEX ISS вернул {resp.status} для {secid}")
                return []

            data = await resp.json()
            coupons_block = data.get("coupons", {})
            columns = coupons_block.get("columns", [])
            rows = coupons_block.get("data", [])

            if not columns or not rows:
                logger.info(f"Нет данных по купонам для {secid}")
                return []

            # Строим индекс колонок по имени, чтобы не зависеть от порядка
            col_idx = {name: i for i, name in enumerate(columns)}

            payments = []
            for row in rows:
                date_str = row[col_idx["coupondate"]]
                if not date_str:
                    continue
                try:
                    c_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue

                value = row[col_idx["value"]] if "value" in col_idx else None
                value_pct = row[col_idx["valueprc"]] if "valueprc" in col_idx else None

                payments.append(CouponPayment(
                    secid=secid,
                    coupon_date=c_date,
                    value=float(value) if value not in (None, "") else None,
                    value_percent=float(value_pct) if value_pct not in (None, "") else None,
                ))

            payments.sort(key=lambda p: p.coupon_date)
            return payments

    except Exception as e:
        logger.exception(f"Ошибка получения купонов для {secid}")
        return []


async def get_next_coupon(session: aiohttp.ClientSession, secid: str) -> Optional[CouponPayment]:
    """Возвращает ближайший будущий купон (или сегодняшний)."""
    coupons = await get_coupons(session, secid)
    today = date.today()
    for c in coupons:
        if c.coupon_date >= today:
            return c
    return None
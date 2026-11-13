import logging
from datetime import date, datetime

import aiohttp

from config import MOEX_ISS_BASE
from core.models import CouponPayment, SecurityInfo

logger = logging.getLogger(__name__)


def _block(data: dict, name: str) -> tuple:
    block = data.get(name, {}) or {}
    return block.get("columns", []) or [], block.get("data", []) or []


async def fetch_coupons(
    session: aiohttp.ClientSession, secid: str
) -> list[CouponPayment] | None:
    """
    Возвращает график купонов или None при ошибке запроса.
    Пустой список — валидный ответ «купонов нет» (например, флоатер без графика).
    """
    url = f"{MOEX_ISS_BASE}/statistics/engines/stock/markets/bonds/bondization/{secid}.json"
    try:
        async with session.get(url, params={"iss.meta": "off"}) as resp:
            if resp.status != 200:
                logger.warning("MOEX ISS вернул %s для %s", resp.status, secid)
                return None

            data = await resp.json()
            columns, rows = _block(data, "coupons")
            if not columns:
                logger.info("Нет блока coupons для %s", secid)
                return []

            col = {name: i for i, name in enumerate(columns)}
            payments: list[CouponPayment] = []
            for row in rows:
                date_str = row[col["coupondate"]] if "coupondate" in col else None
                if not date_str:
                    continue
                try:
                    coupon_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                except ValueError:
                    continue

                recorddate = None
                if "recorddate" in col and row[col["recorddate"]]:
                    try:
                        recorddate = datetime.strptime(
                            row[col["recorddate"]], "%Y-%m-%d"
                        ).date()
                    except ValueError:
                        recorddate = None

                value = row[col["value"]] if "value" in col else None
                value_pct = row[col["valueprc"]] if "valueprc" in col else None
                value_rub = row[col["value_rub"]] if "value_rub" in col else None

                payments.append(
                    CouponPayment(
                        secid=secid,
                        coupon_date=coupon_date,
                        value=_to_float(value),
                        value_percent=_to_float(value_pct),
                        value_rub=_to_float(value_rub),
                        faceunit=row[col["faceunit"]] if "faceunit" in col else None,
                        recorddate=recorddate,
                        name=row[col["name"]] if "name" in col else None,
                        isin=row[col["isin"]] if "isin" in col else None,
                    )
                )

            payments.sort(key=lambda p: p.coupon_date)
            return payments

    except Exception:
        logger.exception("Ошибка получения купонов для %s", secid)
        return None


async def get_coupons(
    session: aiohttp.ClientSession, secid: str
) -> list[CouponPayment]:
    coupons = await fetch_coupons(session, secid)
    return coupons or []


async def get_next_coupon(
    session: aiohttp.ClientSession, secid: str
) -> CouponPayment | None:
    coupons = await get_coupons(session, secid)
    today = date.today()
    for coupon in coupons:
        if coupon.coupon_date >= today:
            return coupon
    return None


async def search_securities(
    session: aiohttp.ClientSession, query: str, limit: int = 8
) -> list[SecurityInfo]:
    """Ищет торгуемые облигации MOEX по названию, ISIN или тикеру."""
    query = (query or "").strip()
    if not query:
        return []

    url = f"{MOEX_ISS_BASE}/securities.json"
    params = {"q": query, "iss.meta": "off", "limit": 100}
    try:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                logger.warning("MOEX search вернул %s для %r", resp.status, query)
                return []
            data = await resp.json()
    except Exception:
        logger.exception("Ошибка поиска бумаги по запросу %r", query)
        return []

    columns, rows = _block(data, "securities")
    if not columns:
        return []
    col = {name: i for i, name in enumerate(columns)}

    found: list[SecurityInfo] = []
    for row in rows:
        group = row[col["group"]] if "group" in col else None
        is_traded = bool(row[col["is_traded"]]) if "is_traded" in col else False
        if group != "stock_bonds" or not is_traded:
            continue
        found.append(
            SecurityInfo(
                secid=row[col["secid"]],
                shortname=row[col["shortname"]] if "shortname" in col else None,
                isin=row[col["isin"]] if "isin" in col else None,
                type=row[col["type"]] if "type" in col else None,
                group=group,
                is_traded=is_traded,
                emitent_title=(
                    row[col["emitent_title"]] if "emitent_title" in col else None
                ),
            )
        )

    needle = query.casefold()

    def rank(item: SecurityInfo) -> tuple:
        exact = (item.secid or "").casefold() == needle or (
            item.isin or ""
        ).casefold() == needle
        starts = (item.shortname or "").casefold().startswith(needle)
        return (0 if exact else 1, 0 if starts else 1, item.secid or "")

    found.sort(key=rank)
    return found[:limit]


def _to_float(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

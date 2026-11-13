from datetime import date

from core import database as db
from core.models import CouponPayment
from services import cache


async def test_refresh_one_stores_coupons(monkeypatch):
    await db.init_db()
    secid = "TESTCACHE1"

    await db.add_bond(secid, 6101)

    async def fake_fetch(session, secid):
        return [
            CouponPayment(
                secid=secid,
                coupon_date=date(2031, 5, 1),
                value=10.0,
                value_percent=1.0,
                value_rub=10.0,
                faceunit="RUB",
                name="Кэш",
                isin="RU000CACHE01",
            )
        ]

    monkeypatch.setattr(cache, "fetch_coupons", fake_fetch)

    assert await cache.refresh_one(None, secid) is True
    assert secid not in await db.get_secids_to_refresh(7)

    security = await db.get_security(secid)
    assert security is not None
    assert security.shortname == "Кэш"


async def test_refresh_one_accepts_empty_schedule(monkeypatch):
    await db.init_db()
    secid = "TESTCACHE2"

    await db.add_bond(secid, 6102)

    async def empty_fetch(session, secid):
        return []

    monkeypatch.setattr(cache, "fetch_coupons", empty_fetch)

    assert await cache.refresh_one(None, secid) is True
    assert secid not in await db.get_secids_to_refresh(7)


async def test_refresh_one_keeps_error_for_retry(monkeypatch):
    await db.init_db()
    secid = "TESTCACHE3"

    await db.add_bond(secid, 6103)

    async def failing_fetch(session, secid):
        return None

    monkeypatch.setattr(cache, "fetch_coupons", failing_fetch)

    assert await cache.refresh_one(None, secid) is False
    assert secid in await db.get_secids_to_refresh(7)

from datetime import date

from core import database as db
from core.models import CouponPayment


async def test_add_bond_is_idempotent():
    await db.init_db()

    assert await db.add_bond("TESTBOND1", 5101) is True
    assert await db.add_bond("TESTBOND1", 5101) is False


async def test_upcoming_coupons_and_notification_journal():
    await db.init_db()
    user_id = 5102
    secid = "TESTBOND2"
    coupon_day = date(2030, 1, 15)

    await db.upsert_subscription(user_id, user_id, "private")
    await db.add_bond(secid, user_id)
    await db.upsert_security(secid, "RU000TEST002", "Тестовая бумага")
    await db.replace_coupons(
        secid,
        [
            CouponPayment(
                secid=secid,
                coupon_date=coupon_day,
                value=12.5,
                value_percent=2.0,
                value_rub=12.5,
                faceunit="RUB",
            )
        ],
    )

    upcoming = await db.get_upcoming_coupons(user_id, "2030-01-01", "2030-02-01")
    assert [item.secid for item in upcoming] == [secid]
    assert upcoming[0].shortname == "Тестовая бумага"
    assert upcoming[0].value_rub == 12.5

    due = await db.get_due_notifications("2030-01-15", "day_of")
    assert len(due) == 1
    assert due[0].chat_id == user_id

    await db.mark_notification_sent(user_id, user_id, secid, "2030-01-15", "day_of")
    assert await db.get_due_notifications("2030-01-15", "day_of") == []


async def test_replace_coupons_overwrites_schedule():
    await db.init_db()
    user_id = 5103
    secid = "TESTBOND3"

    await db.upsert_subscription(user_id, user_id, "private")
    await db.add_bond(secid, user_id)

    first = date(2030, 3, 1)
    await db.replace_coupons(
        secid,
        [CouponPayment(secid, first, 1.0, 0.1, 1.0, "RUB")],
    )
    await db.replace_coupons(
        secid,
        [CouponPayment(secid, date(2030, 4, 1), 2.0, 0.2, 2.0, "RUB")],
    )

    upcoming = await db.get_upcoming_coupons(user_id, "2030-01-01", "2030-12-31")
    assert [item.coupondate for item in upcoming] == ["2030-04-01"]


async def test_failed_fetch_keeps_security_for_retry():
    await db.init_db()
    secid = "TESTBOND4"

    await db.add_bond(secid, 5104)
    await db.upsert_security(secid)

    await db.mark_security_fetched(secid, "ошибка запроса")
    assert secid in await db.get_secids_to_refresh(7)

    await db.mark_security_fetched(secid)
    assert secid not in await db.get_secids_to_refresh(7)

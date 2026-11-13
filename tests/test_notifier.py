from datetime import date, datetime, timedelta

from config import TIMEZONE
from core import database as db
from core.models import CouponPayment, DueNotification
from services import notifier
from services.notifier import _format_digest, _target_date, catch_up_reminders


class RecordingBot:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))


class ExplodingBot:
    async def send_message(self, chat_id, text):
        raise AssertionError("до 10:00 напоминания отправляться не должны")


def fixed_datetime(year, month, day, hour, minute=0):
    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(year, month, day, hour, minute, tzinfo=tz)

    return FixedDatetime


def test_target_date():
    today = datetime.now(TIMEZONE).date()
    assert _target_date("day_of") == today
    assert _target_date("day_before") == today + timedelta(days=1)


def test_digest_shows_zero_amount():
    item = DueNotification(
        user_id=1,
        chat_id=1,
        secid="SU26238RMFS4",
        shortname="ОФЗ 26238",
        coupondate="2026-11-15",
        value_rub=0.0,
        value=0.0,
        faceunit="RUB",
    )

    text = _format_digest("day_of", [item])

    assert "0.00 руб." in text
    assert "SU26238RMFS4" in text
    assert "e-disclosure.ru" in text


async def test_catch_up_skips_before_reminder_hour(monkeypatch):
    monkeypatch.setattr(notifier, "datetime", fixed_datetime(2031, 3, 10, 9))

    assert await catch_up_reminders(ExplodingBot()) == 0


async def test_catch_up_sends_missed_reminders_once(monkeypatch):
    await db.init_db()
    user_id = 7101
    secid = "TESTCATCHUP1"
    today = date(2031, 3, 10)

    await db.upsert_subscription(user_id, user_id, "private")
    await db.add_bond(secid, user_id)
    await db.upsert_security(secid, "RU000TESTC01", "Тестовая бумага")
    await db.replace_coupons(
        secid,
        [
            CouponPayment(
                secid=secid,
                coupon_date=today,
                value=10.0,
                value_percent=1.0,
                value_rub=10.0,
                faceunit="RUB",
            )
        ],
    )

    monkeypatch.setattr(notifier, "datetime", fixed_datetime(2031, 3, 10, 11))

    bot = RecordingBot()
    assert await catch_up_reminders(bot) == 1
    assert len(bot.messages) == 1
    assert "Сегодня ожидается выплата купона" in bot.messages[0][1]

    assert await catch_up_reminders(bot) == 0
    assert len(bot.messages) == 1

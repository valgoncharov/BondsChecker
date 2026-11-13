import logging
from collections import defaultdict
from datetime import datetime, timedelta

from aiogram import Bot

from config import TIMEZONE
from core.database import get_due_notifications, mark_notification_sent
from core.models import DueNotification
from services.formatting import format_amount

logger = logging.getLogger(__name__)

REMINDER_HOUR = 10

HEADERS = {
    "day_before": "📅 Завтра ожидается выплата купона",
    "day_of": "🔔 Сегодня ожидается выплата купона",
}

FOOTERS = {
    "day_before": (
        "💡 Завтра проверьте поступление выплаты. Если её нет, эмитент мог "
        "опубликовать сообщение о невыплате на e-disclosure.ru."
    ),
    "day_of": (
        "💡 Проверьте e-disclosure.ru: если выплата не пришла, возможно, "
        "эмитент опубликовал сообщение о невыплате (существенный факт). "
        "Ищите по названию эмитента в ленте раскрытия."
    ),
}


def _target_date(kind: str):
    today = datetime.now(TIMEZONE).date()
    if kind == "day_before":
        return today + timedelta(days=1)
    return today


def _format_digest(kind: str, items: list[DueNotification]) -> str:
    lines = [HEADERS[kind], ""]
    for item in items:
        title = item.shortname or item.secid
        lines.append(
            f"• {title} ({item.secid}) — "
            f"{format_amount(item.value_rub, item.value, item.faceunit)}"
        )
    lines.append("")
    lines.append(FOOTERS[kind])
    return "\n".join(lines)


async def send_reminders(bot: Bot, kind: str) -> int:
    if kind not in HEADERS:
        raise ValueError(f"Неизвестный тип напоминания: {kind}")

    target = _target_date(kind).isoformat()
    rows = await get_due_notifications(target, kind)
    if not rows:
        logger.info("Напоминаний %s на %s нет", kind, target)
        return 0

    by_chat = defaultdict(list)
    for row in rows:
        by_chat[row.chat_id].append(row)

    sent = 0
    for chat_id, items in by_chat.items():
        text = _format_digest(kind, items)
        try:
            await bot.send_message(chat_id, text)
        except Exception:
            logger.exception("Не удалось отправить напоминание в чат %s", chat_id)
            continue

        for item in items:
            await mark_notification_sent(
                item.user_id,
                item.chat_id,
                item.secid,
                item.coupondate,
                kind,
            )
        sent += len(items)
        logger.info(
            "Напоминание %s отправлено в чат %s: %d купонов",
            kind,
            chat_id,
            len(items),
        )
    return sent


async def catch_up_reminders(bot: Bot) -> int:
    """Досылает напоминания, пропущенные из-за простоя бота."""
    if datetime.now(TIMEZONE).hour < REMINDER_HOUR:
        return 0

    sent = await send_reminders(bot, "day_of")
    sent += await send_reminders(bot, "day_before")
    if sent:
        logger.info("Догнано напоминаний при старте: %d", sent)
    return sent

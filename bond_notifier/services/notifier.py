import logging
from datetime import date
from aiogram import Bot
import aiohttp

from core.database import get_all_bonds
from services.moex import get_coupons

logger = logging.getLogger(__name__)


async def check_coupons_today(bot: Bot):
    """
    Проверяет, у каких облигаций из списка пользователей сегодня дата купона.
    Отправляет уведомление с напоминанием проверить e-disclosure.
    """
    bonds = await get_all_bonds()
    if not bonds:
        logger.info("Список облигаций пуст, проверка не требуется")
        return

    # Группируем по пользователям, чтобы не спамить одним и тем же
    user_bonds: dict[int, set[str]] = {}
    for b in bonds:
        user_bonds.setdefault(b.user_id, set()).add(b.secid)

    today = date.today()

    async with aiohttp.ClientSession() as session:
        for user_id, secids in user_bonds.items():
            notifications = []

            for secid in secids:
                coupons = await get_coupons(session, secid)
                today_coupons = [c for c in coupons if c.coupon_date == today]

                for c in today_coupons:
                    sum_str = f"{c.value:.2f} руб." if c.value else "сумма не указана"
                    notifications.append(
                        f"• `{secid}` — купон {sum_str}"
                    )

            if notifications:
                text = (
                    "🔔 **Сегодня ожидается выплата купона**\n\n"
                    + "\n".join(notifications)
                    + "\n\n"
                    "💡 **Проверьте e-disclosure.ru**: если выплата не пришла, "
                    "возможно, эмитент опубликовал сообщение о невыплате "
                    "(существенный факт). Ищите по названию эмитента в ленте раскрытия."
                )
                try:
                    await bot.send_message(user_id, text)
                    logger.info(f"Уведомление отправлено {user_id}: {len(notifications)} купонов")
                except Exception as e:
                    logger.error(f"Не удалось отправить {user_id}: {e}")
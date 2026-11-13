import logging
import re
from datetime import datetime, timedelta

from aiogram import Dispatcher
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import TIMEZONE
from core.database import (
    add_bond,
    get_upcoming_coupons,
    get_user_portfolio,
    upsert_security,
    upsert_subscription,
)
from core.models import SecurityInfo
from services.cache import refresh_one
from services.formatting import format_amount, format_date
from services.moex import search_securities

logger = logging.getLogger(__name__)

PENDING: dict[int, dict[str, SecurityInfo]] = {}

MAX_PENDING_PER_USER = 50

SECID_RE = re.compile(r"^[A-Za-z0-9]{4,20}$")
SPLIT_RE = re.compile(r"[,;\n]+")


def _remember_options(user_id: int, options: list[SecurityInfo]) -> None:
    pending = PENDING.setdefault(user_id, {})
    for info in options:
        pending.pop(info.secid, None)
        pending[info.secid] = info
    while len(pending) > MAX_PENDING_PER_USER:
        pending.pop(next(iter(pending)))


def _forget_option(user_id: int, secid: str) -> SecurityInfo | None:
    pending = PENDING.get(user_id)
    if not pending:
        return None
    info = pending.pop(secid, None)
    if not pending:
        PENDING.pop(user_id, None)
    return info


def _parse_candidates(raw: str) -> list[str]:
    parts = [part.strip() for part in SPLIT_RE.split(raw) if part.strip()]
    if len(parts) == 1:
        tokens = parts[0].split()
        if len(tokens) > 1 and all(SECID_RE.match(token) for token in tokens):
            return tokens
    return parts


def _title(info: SecurityInfo) -> str:
    if not info.shortname:
        return info.secid
    if info.isin and info.isin != info.secid:
        return f"{info.shortname} ({info.secid}, {info.isin})"
    return f"{info.shortname} ({info.secid})"


def _selection_keyboard(options: list[SecurityInfo]) -> InlineKeyboardMarkup:
    buttons = []
    for info in options:
        label = info.shortname or info.secid
        if info.isin:
            label = f"{label} · {info.isin}"
        buttons.append(
            [InlineKeyboardButton(text=label, callback_data=f"add:{info.secid}")]
        )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


async def cmd_start(message: Message):
    user = message.from_user
    if user is None:
        return
    if message.chat.type == "private":
        await upsert_subscription(user.id, message.chat.id, "private")
    await message.answer(
        "👋 Бот для отслеживания дат купонов по облигациям.\n\n"
        "Добавить бумагу: /add <название, ISIN или тикер>\n"
        "Несколько бумаг сразу: /add RU000A10B4L9, SU26238RMFS4\n"
        "Список: /list\n"
        "Ближайшие выплаты: /next\n\n"
        "📌 За день и в день купона бот пришлёт напоминание. "
        "Если выплата не пришла — проверьте e-disclosure.ru на предмет "
        "сообщения о невыплате."
    )


async def cmd_add(message: Message, session):
    user = message.from_user
    if user is None:
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "Укажите название, ISIN или тикер.\n"
            "Примеры:\n"
            "/add ОФЗ 26238\n"
            "/add RU000A10B4L9, SU26238RMFS4"
        )
        return

    candidates = _parse_candidates(parts[1])
    if not candidates:
        await message.answer("Не удалось разобрать запрос.")
        return

    added: list[SecurityInfo] = []
    already: list[SecurityInfo] = []
    not_found: list[str] = []
    ambiguous: list[tuple[str, list[SecurityInfo]]] = []

    for candidate in candidates:
        results = await search_securities(session, candidate)
        if not results:
            not_found.append(candidate)
            continue

        needle = candidate.casefold()
        exact = [
            item
            for item in results
            if (item.secid or "").casefold() == needle
            or (item.isin or "").casefold() == needle
        ]

        if exact:
            chosen = exact[0]
        elif len(results) == 1:
            chosen = results[0]
        else:
            ambiguous.append((candidate, results[:6]))
            continue

        was_added = await add_bond(chosen.secid, user.id)
        await upsert_security(chosen.secid, chosen.isin, chosen.shortname)
        if was_added:
            added.append(chosen)
            try:
                await refresh_one(session, chosen.secid)
            except Exception:
                logger.exception("Не удалось обновить купоны для %s", chosen.secid)
        else:
            already.append(chosen)

    blocks: list[str] = []
    if added:
        blocks.append(
            "✅ Добавлено:\n" + "\n".join(f"• {_title(info)}" for info in added)
        )
    if already:
        blocks.append(
            "ℹ️ Уже в списке:\n"
            + "\n".join(f"• {_title(info)}" for info in already)
        )
    if not_found:
        blocks.append(
            "❌ Не найдено:\n" + "\n".join(f"• {item}" for item in not_found)
        )
    if ambiguous:
        blocks.append("👇 Уточните выбор по найденным вариантам ниже.")

    if blocks:
        await message.answer("\n\n".join(blocks))

    for query, options in ambiguous:
        _remember_options(user.id, options)
        await message.answer(
            f"Найдено несколько вариантов по запросу «{query}»:",
            reply_markup=_selection_keyboard(options),
        )


async def cmd_list(message: Message):
    user = message.from_user
    if user is None:
        return

    bonds = await get_user_portfolio(user.id)
    if not bonds:
        await message.answer("📭 Список пуст. Добавьте бумагу через /add.")
        return

    lines = ["📋 Ваши облигации:", ""]
    for info in bonds:
        lines.append(f"• {_title(info)}")
    await message.answer("\n".join(lines))


async def cmd_next(message: Message):
    user = message.from_user
    if user is None:
        return

    today = datetime.now(TIMEZONE).date()
    end = today + timedelta(days=30)
    coupons = await get_upcoming_coupons(
        user.id, today.isoformat(), end.isoformat(), limit=20
    )

    if not coupons:
        await message.answer(
            "📭 Ближайших выплат на 30 дней нет.\n\n"
            "Если бумаги добавлены только что, кэш мог не успеть заполниться. "
            "Данные по бумаге обновляются при добавлении и раз в неделю."
        )
        return

    lines = ["📅 Ближайшие выплаты (30 дней):", ""]
    for coupon in coupons:
        title = coupon.shortname or coupon.secid
        lines.append(
            f"• {format_date(coupon.coupondate)} — {title} "
            f"({coupon.secid}) — "
            f"{format_amount(coupon.value_rub, coupon.value, coupon.faceunit)}"
        )
    lines.append("")
    lines.append("💡 Суммы плановые; факт выплаты проверяйте у брокера.")
    await message.answer("\n".join(lines))


async def on_add_callback(callback: CallbackQuery, session):
    if not callback.data or not callback.data.startswith("add:"):
        await callback.answer()
        return

    user = callback.from_user
    secid = callback.data.split(":", 1)[1].upper()
    info: SecurityInfo | None = _forget_option(user.id, secid)

    if info is None:
        results = await search_securities(session, secid)
        info = next((item for item in results if item.secid == secid), None)
        if info is None:
            info = SecurityInfo(secid=secid)

    was_added = await add_bond(secid, user.id)
    await upsert_security(secid, info.isin, info.shortname)
    if was_added:
        try:
            await refresh_one(session, secid)
        except Exception:
            logger.exception("Не удалось обновить купоны для %s", secid)

    status = "Добавлено" if was_added else "Уже в списке"
    await callback.answer(status)
    if callback.message is not None:
        try:
            await callback.message.edit_text(f"{status}: {_title(info)}")
        except Exception:
            logger.exception("Не удалось обновить сообщение выбора")


def register_handlers(dp: Dispatcher, session) -> None:
    async def add_handler(message: Message):
        await cmd_add(message, session)

    async def callback_handler(callback: CallbackQuery):
        await on_add_callback(callback, session)

    dp.message.register(cmd_start, Command("start"))
    dp.message.register(add_handler, Command("add"))
    dp.message.register(cmd_list, Command("list"))
    dp.message.register(cmd_next, Command("next"))
    dp.callback_query.register(callback_handler)

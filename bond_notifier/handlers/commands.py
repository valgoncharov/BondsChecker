from aiogram import types
from aiogram.filters import Command
from aiogram.types import Message

from core.database import add_bond, get_user_bonds

async def cmd_start(message: Message):
    await message.answer(
        "👋 Бот для отслеживания дат купонов по облигациям.\n\n"
        "Добавьте бумагу: `/add <ISIN или тикер>`\n"
        "Список: `/list`\n\n"
        "📌 В день купона бот пришлёт напоминание. "
        "Если выплата не пришла — проверьте e-disclosure.ru на предмет "
        "сообщения о невыплате."
    )

async def cmd_add(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Укажите ISIN или тикер. Пример: `/add RU000A10B4L9`")
        return
    secid = args[1].upper()
    await add_bond(secid, message.from_user.id)
    await message.answer(f"✅ `{secid}` добавлена. Проверка купонов — раз в день.")

async def cmd_list(message: Message):
    bonds = await get_user_bonds(message.from_user.id)
    if not bonds:
        await message.answer("📭 Список пуст.")
        return
    text = "📋 Ваши облигации:\n" + "\n".join(f"• `{b.secid}`" for b in bonds)
    await message.answer(text)

def register_handlers(dp):
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_add, Command("add"))
    dp.message.register(cmd_list, Command("list"))
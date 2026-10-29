from contextlib import asynccontextmanager
from typing import AsyncIterator, List

import aiosqlite

from config import DB_PATH
from core.models import Bond

# Применяются на каждом соединении: WAL повышает параллелизм чтения/записи,
# busy_timeout даёт шанс дождаться блокировки вместо мгновенной ошибки.
PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
)


@asynccontextmanager
async def connect() -> AsyncIterator[aiosqlite.Connection]:
    db = await aiosqlite.connect(DB_PATH)
    try:
        for pragma in PRAGMAS:
            await db.execute(pragma)
        yield db
    finally:
        await db.close()


async def init_db():
    async with connect() as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bonds (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                secid TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(secid, user_id)
            )
        """)
        await db.commit()

async def add_bond(secid: str, user_id: int):
    async with connect() as db:
        await db.execute(
            "INSERT OR IGNORE INTO bonds (secid, user_id) VALUES (?, ?)",
            (secid.upper(), user_id)
        )
        await db.commit()

async def get_user_bonds(user_id: int) -> List[Bond]:
    async with connect() as db:
        async with db.execute(
            "SELECT secid, user_id, added_at FROM bonds WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]

async def get_all_bonds() -> List[Bond]:
    async with connect() as db:
        async with db.execute("SELECT secid, user_id, added_at FROM bonds") as cursor:
            rows = await cursor.fetchall()
            return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]

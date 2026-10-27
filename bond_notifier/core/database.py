import aiosqlite
from typing import List
from core.models import Bond

DB_PATH = "bonds.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
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
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO bonds (secid, user_id) VALUES (?, ?)",
            (secid.upper(), user_id)
        )
        await db.commit()

async def get_user_bonds(user_id: int) -> List[Bond]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT secid, user_id, added_at FROM bonds WHERE user_id = ?",
            (user_id,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]

async def get_all_bonds() -> List[Bond]:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT secid, user_id, added_at FROM bonds") as cursor:
            rows = await cursor.fetchall()
            return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]
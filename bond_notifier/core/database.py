from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager

import aiosqlite

from config import DB_PATH
from core.models import (
    Bond,
    CouponPayment,
    DueNotification,
    SecurityInfo,
    UpcomingCoupon,
)

PRAGMAS = (
    "PRAGMA journal_mode=WAL",
    "PRAGMA busy_timeout=5000",
    "PRAGMA foreign_keys=ON",
    "PRAGMA synchronous=NORMAL",
)

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS bonds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        secid TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(secid, user_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS subscriptions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        chat_type TEXT NOT NULL
            CHECK (chat_type IN ('private', 'group', 'supergroup', 'channel')),
        enabled INTEGER NOT NULL DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, chat_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS coupons (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        secid TEXT NOT NULL,
        coupondate TEXT NOT NULL,
        recorddate TEXT,
        value REAL,
        valueprc REAL,
        value_rub REAL,
        faceunit TEXT,
        fetched_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(secid, coupondate)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_coupons_secid_date ON coupons(secid, coupondate)",
    "CREATE INDEX IF NOT EXISTS idx_coupons_date ON coupons(coupondate)",
    """
    CREATE TABLE IF NOT EXISTS notifications_sent (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        chat_id INTEGER NOT NULL,
        secid TEXT NOT NULL,
        coupondate TEXT NOT NULL,
        kind TEXT NOT NULL
            CHECK (kind IN ('day_before', 'day_of')),
        sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, chat_id, secid, coupondate, kind)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_notif_chat_date
        ON notifications_sent(chat_id, coupondate)
    """,
    """
    CREATE TABLE IF NOT EXISTS securities (
        secid TEXT PRIMARY KEY,
        isin TEXT,
        shortname TEXT,
        faceunit TEXT,
        fetched_at TIMESTAMP,
        fetch_error TEXT
    )
    """,
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


async def init_db() -> None:
    async with connect() as db:
        for statement in SCHEMA:
            await db.execute(statement)
        await db.commit()


async def upsert_subscription(user_id: int, chat_id: int, chat_type: str) -> None:
    async with connect() as db:
        await db.execute(
            """
            INSERT INTO subscriptions (user_id, chat_id, chat_type)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, chat_id) DO UPDATE SET
                chat_type = excluded.chat_type,
                enabled = 1
            """,
            (user_id, chat_id, chat_type),
        )
        await db.commit()


async def add_bond(secid: str, user_id: int) -> bool:
    async with connect() as db:
        cursor = await db.execute(
            "INSERT OR IGNORE INTO bonds (secid, user_id) VALUES (?, ?)",
            (secid.upper(), user_id),
        )
        await db.commit()
        return cursor.rowcount == 1


async def get_user_bonds(user_id: int) -> list[Bond]:
    async with connect() as db, db.execute(
        "SELECT secid, user_id, added_at FROM bonds WHERE user_id = ? ORDER BY secid",
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]


async def get_all_bonds() -> list[Bond]:
    async with (
        connect() as db,
        db.execute("SELECT secid, user_id, added_at FROM bonds") as cursor,
    ):
        rows = await cursor.fetchall()
        return [Bond(secid=r[0], user_id=r[1], added_at=r[2]) for r in rows]


async def get_user_portfolio(user_id: int) -> list[SecurityInfo]:
    async with connect() as db, db.execute(
        """
            SELECT b.secid, s.isin, s.shortname
            FROM bonds b
            LEFT JOIN securities s ON s.secid = b.secid
            WHERE b.user_id = ?
            ORDER BY s.shortname, b.secid
            """,
        (user_id,),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            SecurityInfo(secid=r[0], isin=r[1], shortname=r[2] or r[0])
            for r in rows
        ]


async def upsert_security(
    secid: str,
    isin: str | None = None,
    shortname: str | None = None,
    faceunit: str | None = None,
) -> None:
    async with connect() as db:
        await db.execute(
            """
            INSERT INTO securities (secid, isin, shortname, faceunit)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(secid) DO UPDATE SET
                isin = COALESCE(securities.isin, excluded.isin),
                shortname = COALESCE(securities.shortname, excluded.shortname),
                faceunit = COALESCE(securities.faceunit, excluded.faceunit)
            """,
            (secid.upper(), isin, shortname, faceunit),
        )
        await db.commit()


async def save_security_info(info: SecurityInfo) -> None:
    await upsert_security(info.secid, info.isin, info.shortname)


async def mark_security_fetched(secid: str, error: str | None = None) -> None:
    async with connect() as db:
        await db.execute(
            """
            UPDATE securities
            SET fetched_at = CASE
                    WHEN ? IS NULL THEN CURRENT_TIMESTAMP
                    ELSE fetched_at
                END,
                fetch_error = ?
            WHERE secid = ?
            """,
            (error, error, secid.upper()),
        )
        await db.commit()


async def get_security(secid: str) -> SecurityInfo | None:
    async with connect() as db, db.execute(
        "SELECT secid, isin, shortname, faceunit, fetched_at, fetch_error "
        "FROM securities WHERE secid = ?",
        (secid.upper(),),
    ) as cursor:
        row = await cursor.fetchone()
        if not row:
            return None
        return SecurityInfo(secid=row[0], isin=row[1], shortname=row[2])


async def get_secids_to_refresh(max_age_days: int) -> list[str]:
    async with connect() as db, db.execute(
        """
            SELECT DISTINCT b.secid
            FROM bonds b
            LEFT JOIN securities s ON s.secid = b.secid
            WHERE s.secid IS NULL
               OR s.fetched_at IS NULL
               OR s.fetched_at < datetime('now', ?)
            ORDER BY b.secid
            """,
        (f"-{int(max_age_days)} days",),
    ) as cursor:
        rows = await cursor.fetchall()
        return [r[0] for r in rows]


async def replace_coupons(secid: str, coupons: Sequence[CouponPayment]) -> None:
    secid = secid.upper()
    async with connect() as db:
        await db.execute("DELETE FROM coupons WHERE secid = ?", (secid,))
        await db.executemany(
            """
            INSERT OR REPLACE INTO coupons
                (secid, coupondate, recorddate, value, valueprc, value_rub,
                 faceunit, fetched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            [
                (
                    secid,
                    c.coupon_date.isoformat(),
                    c.recorddate.isoformat() if c.recorddate else None,
                    c.value,
                    c.value_percent,
                    c.value_rub,
                    c.faceunit,
                )
                for c in coupons
            ],
        )
        await db.commit()


async def get_upcoming_coupons(
    user_id: int, start_iso: str, end_iso: str, limit: int = 20
) -> list[UpcomingCoupon]:
    async with connect() as db, db.execute(
        """
            SELECT b.secid, s.shortname, s.isin, c.coupondate,
                   c.value_rub, c.value, c.faceunit
            FROM bonds b
            JOIN coupons c ON c.secid = b.secid
            LEFT JOIN securities s ON s.secid = b.secid
            WHERE b.user_id = ?
              AND c.coupondate >= ?
              AND c.coupondate <= ?
            ORDER BY c.coupondate, b.secid
            LIMIT ?
            """,
        (user_id, start_iso, end_iso, limit),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            UpcomingCoupon(
                secid=r[0],
                shortname=r[1],
                isin=r[2],
                coupondate=r[3],
                value_rub=r[4],
                value=r[5],
                faceunit=r[6],
            )
            for r in rows
        ]


async def get_due_notifications(target_iso: str, kind: str) -> list[DueNotification]:
    async with connect() as db, db.execute(
        """
            SELECT b.user_id, sub.chat_id, c.secid, s.shortname, c.coupondate,
                   c.value_rub, c.value, c.faceunit
            FROM bonds b
            JOIN coupons c ON c.secid = b.secid
            JOIN subscriptions sub
                 ON sub.user_id = b.user_id AND sub.enabled = 1
            LEFT JOIN securities s ON s.secid = b.secid
            LEFT JOIN notifications_sent n
                 ON n.user_id = b.user_id
                AND n.chat_id = sub.chat_id
                AND n.secid = c.secid
                AND n.coupondate = c.coupondate
                AND n.kind = ?
            WHERE c.coupondate = ? AND n.id IS NULL
            ORDER BY sub.chat_id, c.coupondate, c.secid
            """,
        (kind, target_iso),
    ) as cursor:
        rows = await cursor.fetchall()
        return [
            DueNotification(
                user_id=r[0],
                chat_id=r[1],
                secid=r[2],
                shortname=r[3],
                coupondate=r[4],
                value_rub=r[5],
                value=r[6],
                faceunit=r[7],
            )
            for r in rows
        ]


async def mark_notification_sent(
    user_id: int, chat_id: int, secid: str, coupondate: str, kind: str
) -> None:
    async with connect() as db:
        await db.execute(
            """
            INSERT OR IGNORE INTO notifications_sent
                (user_id, chat_id, secid, coupondate, kind)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, chat_id, secid, coupondate, kind),
        )
        await db.commit()

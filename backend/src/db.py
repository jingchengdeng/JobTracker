import os
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


def get_db_path() -> str:
    return os.environ.get(
        "JOBTRACKER_DB_PATH",
        str(Path(__file__).parent.parent.parent / "jobtracker.db"),
    )


@asynccontextmanager
async def get_connection():
    """Async context manager returning an aiosqlite connection.

    Usage:
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT ...")
            row = await cursor.fetchone()
    """
    conn = await aiosqlite.connect(get_db_path())
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA busy_timeout=5000")
    await conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        await conn.close()


def get_sync_connection() -> sqlite3.Connection:
    """Sync connection for startup-only use (before event loop serves requests).

    Caller is responsible for closing.
    """
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

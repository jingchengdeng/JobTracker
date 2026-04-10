import sqlite3
import pytest


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE test_tbl (id INTEGER PRIMARY KEY, val TEXT)")
    conn.execute("INSERT INTO test_tbl (val) VALUES ('hello')")
    conn.commit()
    conn.close()
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


class TestAsyncGetConnection:
    async def test_read_row(self, test_db):
        from src.db import get_connection

        async with get_connection() as conn:
            cursor = await conn.execute("SELECT val FROM test_tbl WHERE id = 1")
            row = await cursor.fetchone()
        assert row["val"] == "hello"

    async def test_write_and_read(self, test_db):
        from src.db import get_connection

        async with get_connection() as conn:
            await conn.execute("INSERT INTO test_tbl (val) VALUES ('world')")
            await conn.commit()

        async with get_connection() as conn:
            cursor = await conn.execute("SELECT COUNT(*) as cnt FROM test_tbl")
            row = await cursor.fetchone()
        assert row["cnt"] == 2

    async def test_wal_mode_enabled(self, test_db):
        from src.db import get_connection

        async with get_connection() as conn:
            cursor = await conn.execute("PRAGMA journal_mode")
            row = await cursor.fetchone()
        assert row[0] == "wal"

    async def test_row_factory_returns_dicts(self, test_db):
        from src.db import get_connection

        async with get_connection() as conn:
            cursor = await conn.execute("SELECT val FROM test_tbl WHERE id = 1")
            row = await cursor.fetchone()
        assert row["val"] == "hello"


class TestSyncGetConnection:
    def test_sync_connection_works(self, test_db):
        from src.db import get_sync_connection

        conn = get_sync_connection()
        try:
            row = conn.execute("SELECT val FROM test_tbl WHERE id = 1").fetchone()
            assert row["val"] == "hello"
        finally:
            conn.close()

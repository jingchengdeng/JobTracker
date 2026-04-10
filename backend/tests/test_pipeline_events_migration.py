import asyncio
import os
import tempfile

import aiosqlite
import pytest

from src.db_migrations import migrate_ai_steps_to_pipeline_events


@pytest.fixture
def temp_db(monkeypatch):
    """Fresh SQLite file for each test."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", path)
    yield path
    os.unlink(path)


async def _seed_legacy_schema(path, with_round_number=True):
    async with aiosqlite.connect(path) as conn:
        await conn.execute(
            "CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT)"
        )
        await conn.execute(
            "CREATE TABLE ai_runs (id INTEGER PRIMARY KEY, job_id INTEGER, "
            "resume_id INTEGER, status TEXT, error TEXT, created_at TEXT, completed_at TEXT, "
            "FOREIGN KEY (job_id) REFERENCES jobs(id))"
        )
        cols = (
            "id INTEGER PRIMARY KEY, run_id INTEGER, step_type TEXT, status TEXT, "
            "result TEXT, version INTEGER DEFAULT 1, completed_at TEXT"
        )
        if with_round_number:
            cols += ", round_number INTEGER DEFAULT 0"
        await conn.execute(f"CREATE TABLE ai_steps ({cols})")
        await conn.commit()


async def _insert_row(path, table, values):
    async with aiosqlite.connect(path) as conn:
        placeholders = ",".join("?" * len(values))
        await conn.execute(f"INSERT INTO {table} VALUES ({placeholders})", values)
        await conn.commit()


@pytest.mark.asyncio
async def test_migration_backfills_valid_rows(temp_db):
    await _seed_legacy_schema(temp_db)
    await _insert_row(temp_db, "jobs", (1, "Engineer", "Acme"))
    await _insert_row(
        temp_db, "ai_runs",
        (1, 1, 1, "completed", None, "2026-01-01", "2026-01-01"),
    )
    await _insert_row(
        temp_db, "ai_steps",
        (1, 1, "jd_analysis", "completed", "result-json", 1, "2026-01-01", 0),
    )

    await migrate_ai_steps_to_pipeline_events()

    async with aiosqlite.connect(temp_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT * FROM pipeline_events")
        rows = [dict(r) for r in await cursor.fetchall()]
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_steps'"
        )
        ai_steps_still_exists = await cursor.fetchone()

    assert len(rows) == 1
    assert rows[0]["workflow_run_id"] == "legacy-1"
    assert rows[0]["job_id"] == 1
    assert rows[0]["graph"] == "resume"
    assert rows[0]["node_name"] == "jd_analysis"
    assert rows[0]["status"] == "completed"
    assert rows[0]["attempt"] == 1
    assert rows[0]["result"] == "result-json"
    assert rows[0]["run_id"] == 1
    assert rows[0]["step_type"] == "jd_analysis"
    assert rows[0]["version"] == 1
    assert rows[0]["round_number"] == 0
    assert ai_steps_still_exists is None


@pytest.mark.asyncio
async def test_migration_skips_orphans(temp_db):
    await _seed_legacy_schema(temp_db)
    await _insert_row(temp_db, "jobs", (1, "Engineer", "Acme"))
    await _insert_row(
        temp_db, "ai_runs",
        (1, 1, 1, "completed", None, "2026-01-01", "2026-01-01"),
    )
    await _insert_row(
        temp_db, "ai_steps",
        (1, 1, "jd_analysis", "completed", "ok", 1, "2026-01-01", 0),
    )
    await _insert_row(
        temp_db, "ai_runs",
        (2, 99, 1, "completed", None, "2026-01-01", "2026-01-01"),
    )
    await _insert_row(
        temp_db, "ai_steps",
        (2, 2, "gap_analysis", "completed", "dropped", 1, "2026-01-01", 0),
    )

    await migrate_ai_steps_to_pipeline_events()

    async with aiosqlite.connect(temp_db) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM pipeline_events")
        (count,) = await cursor.fetchone()
    assert count == 1


@pytest.mark.asyncio
async def test_migration_is_idempotent(temp_db):
    await _seed_legacy_schema(temp_db)
    await _insert_row(temp_db, "jobs", (1, "Engineer", "Acme"))
    await _insert_row(
        temp_db, "ai_runs",
        (1, 1, 1, "completed", None, "2026-01-01", "2026-01-01"),
    )
    await _insert_row(
        temp_db, "ai_steps",
        (1, 1, "jd_analysis", "completed", "ok", 1, "2026-01-01", 0),
    )

    await migrate_ai_steps_to_pipeline_events()
    await migrate_ai_steps_to_pipeline_events()

    async with aiosqlite.connect(temp_db) as conn:
        cursor = await conn.execute("SELECT COUNT(*) FROM pipeline_events")
        (count,) = await cursor.fetchone()
    assert count == 1


@pytest.mark.asyncio
async def test_migration_handles_legacy_schema_without_round_number(temp_db):
    await _seed_legacy_schema(temp_db, with_round_number=False)
    await _insert_row(temp_db, "jobs", (1, "Engineer", "Acme"))
    await _insert_row(
        temp_db, "ai_runs",
        (1, 1, 1, "completed", None, "2026-01-01", "2026-01-01"),
    )
    await _insert_row(
        temp_db, "ai_steps",
        (1, 1, "jd_analysis", "completed", "ok", 1, "2026-01-01"),
    )

    await migrate_ai_steps_to_pipeline_events()

    async with aiosqlite.connect(temp_db) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute("SELECT round_number FROM pipeline_events")
        row = await cursor.fetchone()
    assert row["round_number"] == 0

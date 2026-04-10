import os
import tempfile

import aiosqlite
import pytest


@pytest.fixture(autouse=True)
def _disable_langsmith(monkeypatch):
    """Prevent all tests from leaving traces in LangSmith."""
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
async def migrated_db(monkeypatch):
    """Fresh SQLite file with pipeline_events + minimal FK targets."""
    from src.db_migrations import PIPELINE_EVENTS_DDL

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", path)
    async with aiosqlite.connect(path) as conn:
        await conn.execute("CREATE TABLE jobs (id INTEGER PRIMARY KEY)")
        await conn.execute(
            "CREATE TABLE ai_runs (id INTEGER PRIMARY KEY, job_id INTEGER, resume_id INTEGER)"
        )
        await conn.executescript(PIPELINE_EVENTS_DDL)
        await conn.commit()
    yield path
    os.unlink(path)

import asyncio
import time
import sqlite3
import pytest
from unittest.mock import patch, MagicMock

from src.memory.reindex import (
    start_reindex_job,
    get_job,
    active_job,
    ReindexJob,
    _jobs,
)
from src.memory.embedding_state import ensure_row, get_active_signature


@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE embedding_state ("
        "id INTEGER PRIMARY KEY, active_signature TEXT, updated_at TEXT)"
    )
    conn.execute(
        "CREATE TABLE resumes ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, version TEXT, "
        "file_path TEXT, file_type TEXT, extracted_text TEXT, "
        "last_index_signature TEXT, last_index_status TEXT, last_index_error TEXT, "
        "created_at TEXT DEFAULT (datetime('now')))"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def mock_db(test_db, monkeypatch):
    def make_conn():
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        return conn
    monkeypatch.setattr("src.memory.embedding_state.get_connection", make_conn)
    monkeypatch.setattr("src.memory.reindex.get_connection", make_conn)
    monkeypatch.setattr("src.memory.rag.get_connection", make_conn)
    _jobs.clear()
    ensure_row()
    yield
    _jobs.clear()


@pytest.fixture
def seed_resumes(test_db):
    conn = sqlite3.connect(test_db)
    for name, text in [("A.pdf", "alpha text"), ("B.pdf", "beta text"), ("C.pdf", None)]:
        conn.execute(
            "INSERT INTO resumes (name, file_path, file_type, extracted_text) "
            "VALUES (?, 'p', 'pdf', ?)",
            (name, text),
        )
    conn.commit()
    conn.close()


@pytest.fixture
def mock_collection_for_signature():
    with patch("src.memory.reindex.collection_for_signature") as m:
        m.return_value = MagicMock(name="fake_collection")
        yield m


async def test_full_reindex_partial_failure_does_not_flip_pointer(
    seed_resumes, mock_collection_for_signature
):
    """Resume C has NULL extracted_text → fails → pointer stays."""
    def fake_index(collection, rid, name, text):
        pass
    with patch("src.memory.reindex.index_resume_into", side_effect=fake_index):
        job_id = await start_reindex_job(
            target_signature="openai__model_x",
            provider="openai",
            model="model-x",
            resume_ids=None,
        )
        await get_job(job_id).task
    job = get_job(job_id)
    assert job.status == "completed"
    assert len(job.succeeded) == 2
    assert len(job.failed) == 1
    assert get_active_signature() is None


async def test_full_reindex_no_failures_flips_pointer(
    seed_resumes, mock_collection_for_signature, test_db
):
    """All 3 succeed → pointer flips to target."""
    conn = sqlite3.connect(test_db)
    conn.execute("UPDATE resumes SET extracted_text = 'gamma text' WHERE name = 'C.pdf'")
    conn.commit()
    conn.close()

    def fake_index(collection, rid, name, text):
        pass
    with patch("src.memory.reindex.index_resume_into", side_effect=fake_index):
        job_id = await start_reindex_job(
            target_signature="openai__model_x",
            provider="openai",
            model="model-x",
            resume_ids=None,
        )
        await get_job(job_id).task
    job = get_job(job_id)
    assert job.status == "completed"
    assert len(job.succeeded) == 3
    assert len(job.failed) == 0
    assert get_active_signature() == "openai__model_x"


async def test_per_resume_subset_does_not_flip_pointer(
    seed_resumes, mock_collection_for_signature
):
    def fake_index(collection, rid, name, text):
        pass
    with patch("src.memory.reindex.index_resume_into", side_effect=fake_index):
        job_id = await start_reindex_job(
            target_signature="openai__model_x",
            provider="openai",
            model="model-x",
            resume_ids=[1],
        )
        await get_job(job_id).task
    assert get_active_signature() is None


async def test_second_concurrent_job_rejected(
    seed_resumes, mock_collection_for_signature
):
    def slow_index(collection, rid, name, text):
        time.sleep(0.05)
    with patch("src.memory.reindex.index_resume_into", side_effect=slow_index):
        job_id = await start_reindex_job(
            target_signature="sig_a",
            provider="openai",
            model="m",
            resume_ids=None,
        )
        with pytest.raises(RuntimeError, match="already running"):
            await start_reindex_job(
                target_signature="sig_b",
                provider="openai",
                model="m2",
                resume_ids=None,
            )
        await get_job(job_id).task


async def test_retry_after_failures_flips_pointer_when_all_converged(
    seed_resumes, mock_collection_for_signature, test_db
):
    # Give C text so the only failure is B's flakiness
    conn = sqlite3.connect(test_db)
    conn.execute("UPDATE resumes SET extracted_text = 'gamma' WHERE name = 'C.pdf'")
    conn.commit()
    conn.close()

    call_count = {"n": 0}
    def sometimes_fail(collection, rid, name, text):
        call_count["n"] += 1
        if name == "B.pdf":
            raise RuntimeError("flaky")
    with patch("src.memory.reindex.index_resume_into", side_effect=sometimes_fail):
        job_id = await start_reindex_job(
            target_signature="sig_target",
            provider="openai",
            model="m",
            resume_ids=None,
        )
        await get_job(job_id).task
        assert get_active_signature() is None

    def ok(collection, rid, name, text):
        return None
    with patch("src.memory.reindex.index_resume_into", side_effect=ok):
        retry_id = await start_reindex_job(
            target_signature="sig_target",
            provider="openai",
            model="m",
            resume_ids=[2],
        )
        await get_job(retry_id).task
        assert get_active_signature() == "sig_target"

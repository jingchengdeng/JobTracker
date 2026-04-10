import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.embedding_state import ensure_row, get_active_signature, set_active_signature
from src.memory.legacy_migration import migrate_legacy_collection


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
    conn.execute(
        "INSERT INTO resumes (id, name, file_path, file_type, extracted_text) "
        "VALUES (1, 'A.pdf', 'p', 'pdf', 'alpha')"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
async def mock_env(test_db, monkeypatch):
    monkeypatch.setenv("JOBTRACKER_DB_PATH", test_db)
    await ensure_row()


@pytest.fixture
def fake_config():
    with patch("src.memory.legacy_migration.load_model_config") as m:
        m.return_value = {
            "embedding": {"provider": "sentence_transformer", "model": "all-MiniLM-L6-v2"}
        }
        yield m


def _make_mock_client(*, has_legacy=False, payload=None):
    """Return an AsyncMock that mimics the async ChromaDB client."""
    client = AsyncMock()

    if has_legacy:
        legacy_col = MagicMock()
        legacy_col.name = "resume_chunks"
        client.list_collections.return_value = [legacy_col]
    else:
        client.list_collections.return_value = []

    legacy_collection = AsyncMock()
    if payload is None:
        payload = {"ids": [], "embeddings": None, "documents": None, "metadatas": None}
    legacy_collection.get.return_value = payload
    client.get_collection.return_value = legacy_collection
    client.delete_collection.return_value = None

    return client


async def test_migration_skips_when_active_signature_set(fake_config):
    await set_active_signature("already_set")
    await migrate_legacy_collection()
    assert await get_active_signature() == "already_set"


async def test_migration_skips_when_no_legacy_collection(fake_config):
    mock_client = _make_mock_client(has_legacy=False)
    with patch("src.memory.legacy_migration._client", return_value=mock_client):
        await migrate_legacy_collection()
    assert await get_active_signature() is None


async def test_migration_copies_and_sets_signature(fake_config):
    payload = {
        "ids": ["resume-1-chunk-0"],
        "embeddings": [[0.1, 0.2, 0.3]],
        "documents": ["A.pdf -- general -- alpha text content here"],
        "metadatas": [
            {
                "resume_id": 1,
                "resume_name": "A.pdf",
                "section_type": "general",
                "raw_text": "alpha text content here",
            }
        ],
    }
    mock_client = _make_mock_client(has_legacy=True, payload=payload)
    new_col = AsyncMock()
    new_col.name = "resume_chunks__sentence_transformer__all_minilm_l6_v2"

    with (
        patch("src.memory.legacy_migration._client", return_value=mock_client),
        patch(
            "src.memory.legacy_migration.collection_for_signature",
            return_value=new_col,
        ),
    ):
        await migrate_legacy_collection()

    assert await get_active_signature() == "sentence_transformer__all_minilm_l6_v2"
    new_col.add.assert_awaited_once()
    mock_client.delete_collection.assert_awaited_once_with(name="resume_chunks")


async def test_migration_marks_resumes_with_chunks_as_ok(fake_config, test_db):
    payload = {
        "ids": ["resume-1-chunk-0"],
        "embeddings": [[0.1, 0.2]],
        "documents": ["alpha"],
        "metadatas": [
            {
                "resume_id": 1,
                "resume_name": "A.pdf",
                "section_type": "general",
                "raw_text": "alpha",
            }
        ],
    }
    mock_client = _make_mock_client(has_legacy=True, payload=payload)
    new_col = AsyncMock()
    new_col.name = "resume_chunks__sentence_transformer__all_minilm_l6_v2"

    with (
        patch("src.memory.legacy_migration._client", return_value=mock_client),
        patch(
            "src.memory.legacy_migration.collection_for_signature",
            return_value=new_col,
        ),
    ):
        await migrate_legacy_collection()

    conn = sqlite3.connect(test_db)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT last_index_signature, last_index_status FROM resumes WHERE id=1"
    ).fetchone()
    conn.close()
    assert row["last_index_signature"] == "sentence_transformer__all_minilm_l6_v2"
    assert row["last_index_status"] == "ok"


async def test_migration_idempotent_second_call(fake_config):
    payload = {
        "ids": ["resume-1-chunk-0"],
        "embeddings": [[0.1]],
        "documents": ["text"],
        "metadatas": [{"resume_id": 1}],
    }
    mock_client = _make_mock_client(has_legacy=True, payload=payload)
    new_col = AsyncMock()
    new_col.name = "resume_chunks__sentence_transformer__all_minilm_l6_v2"

    with (
        patch("src.memory.legacy_migration._client", return_value=mock_client),
        patch(
            "src.memory.legacy_migration.collection_for_signature",
            return_value=new_col,
        ),
    ):
        await migrate_legacy_collection()
    first = await get_active_signature()

    # Second call should be a no-op because active_signature is now set
    await migrate_legacy_collection()
    assert await get_active_signature() == first

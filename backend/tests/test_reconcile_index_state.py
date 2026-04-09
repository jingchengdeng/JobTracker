"""Tests for reconcile_resume_index_state -- startup heal that keeps SQL
per-resume state in sync with actual Chroma contents."""
import sqlite3
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.memory.embedding_state import ensure_row, set_active_signature
from src.memory.rag import reconcile_resume_index_state


ACTIVE_SIG = "sentence_transformer__all_minilm_l6_v2"
ACTIVE_COLLECTION_NAME = f"resume_chunks__{ACTIVE_SIG}"


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
async def wire_env(test_db, monkeypatch):
    monkeypatch.setenv("JOBTRACKER_DB_PATH", test_db)
    await ensure_row()
    yield


def _insert_resume(db_path, rid, sig, status):
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO resumes (id, name, file_path, file_type, extracted_text, "
        "last_index_signature, last_index_status) VALUES (?, 'r.pdf', 'p', 'pdf', 't', ?, ?)",
        (rid, sig, status),
    )
    conn.commit()
    conn.close()


def _row(db_path, rid):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    r = conn.execute(
        "SELECT last_index_signature, last_index_status FROM resumes WHERE id = ?",
        (rid,),
    ).fetchone()
    conn.close()
    return dict(r)


def _mock_client(collection_names=None, collection_metadatas=None):
    """Build an AsyncMock Chroma client with configurable collections.

    Args:
        collection_names: names of collections that list_collections returns.
        collection_metadatas: dict mapping collection name to the metadatas
            list that col.get() returns.
    """
    if collection_names is None:
        collection_names = []
    if collection_metadatas is None:
        collection_metadatas = {}

    mock_collections = []
    for name in collection_names:
        c = MagicMock()
        c.name = name
        mock_collections.append(c)

    client = AsyncMock()
    client.list_collections.return_value = mock_collections

    def _get_collection(name):
        col = MagicMock()
        col.name = name
        metas = collection_metadatas.get(name, [])
        col.get.return_value = {"ids": [f"id-{i}" for i in range(len(metas))], "metadatas": metas}
        return col

    client.get_collection = AsyncMock(side_effect=_get_collection)
    return client


async def test_orphan_signature_gets_reset_to_null(test_db):
    # No collections exist at all -- any signature is orphaned
    await set_active_signature(ACTIVE_SIG)
    _insert_resume(test_db, 1, "some_phantom_sig", "ok")

    client = _mock_client(collection_names=[])
    with patch("src.memory.collection_resolver._client", new_callable=AsyncMock, return_value=client):
        await reconcile_resume_index_state()

    row = _row(test_db, 1)
    assert row["last_index_signature"] is None
    assert row["last_index_status"] is None


async def test_null_signature_healed_when_chunks_exist_in_active(test_db):
    await set_active_signature(ACTIVE_SIG)
    _insert_resume(test_db, 5, None, None)

    metadatas = [{"resume_id": 5, "resume_name": "r.pdf", "section_type": "x", "raw_text": "t"}]
    client = _mock_client(
        collection_names=[ACTIVE_COLLECTION_NAME],
        collection_metadatas={ACTIVE_COLLECTION_NAME: metadatas},
    )
    with patch("src.memory.collection_resolver._client", new_callable=AsyncMock, return_value=client):
        await reconcile_resume_index_state()

    row = _row(test_db, 5)
    assert row["last_index_signature"] == ACTIVE_SIG
    assert row["last_index_status"] == "ok"


async def test_null_signature_stays_null_when_no_chunks(test_db):
    await set_active_signature(ACTIVE_SIG)
    _insert_resume(test_db, 2, None, None)

    # only resume 1 has chunks, not resume 2
    metadatas = [{"resume_id": 1, "resume_name": "r.pdf", "section_type": "x", "raw_text": "t"}]
    client = _mock_client(
        collection_names=[ACTIVE_COLLECTION_NAME],
        collection_metadatas={ACTIVE_COLLECTION_NAME: metadatas},
    )
    with patch("src.memory.collection_resolver._client", new_callable=AsyncMock, return_value=client):
        await reconcile_resume_index_state()

    row = _row(test_db, 2)
    assert row["last_index_signature"] is None


async def test_correct_signature_is_left_alone(test_db):
    await set_active_signature(ACTIVE_SIG)
    _insert_resume(test_db, 3, ACTIVE_SIG, "ok")

    metadatas = [{"resume_id": 3, "resume_name": "r.pdf", "section_type": "x", "raw_text": "t"}]
    client = _mock_client(
        collection_names=[ACTIVE_COLLECTION_NAME],
        collection_metadatas={ACTIVE_COLLECTION_NAME: metadatas},
    )
    with patch("src.memory.collection_resolver._client", new_callable=AsyncMock, return_value=client):
        await reconcile_resume_index_state()

    row = _row(test_db, 3)
    assert row["last_index_signature"] == ACTIVE_SIG
    assert row["last_index_status"] == "ok"


async def test_noop_when_no_active_signature(test_db):
    _insert_resume(test_db, 1, "any_sig", "ok")

    # No collections exist, active_signature is NULL; reconcile should
    # still clear orphan signatures that point at missing collections.
    client = _mock_client(collection_names=[])
    with patch("src.memory.collection_resolver._client", new_callable=AsyncMock, return_value=client):
        await reconcile_resume_index_state()

    row = _row(test_db, 1)
    assert row["last_index_signature"] is None

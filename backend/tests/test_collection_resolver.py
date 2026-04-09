import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.collection_resolver import (
    active_collection,
    collection_for_signature,
)
from src.memory.embedding_state import set_active_signature, ensure_row


@pytest.fixture
def test_db(tmp_path):
    """Create a temp SQLite DB with the embedding_state table."""
    import sqlite3

    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE embedding_state ("
        "id INTEGER PRIMARY KEY, active_signature TEXT, updated_at TEXT)"
    )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
async def mock_db_and_chromadb(test_db, monkeypatch):
    monkeypatch.setenv("JOBTRACKER_DB_PATH", test_db)
    fake_config = {
        "embedding": {"provider": "sentence_transformer", "model": "all-MiniLM-L6-v2"}
    }
    with patch(
        "src.memory.collection_resolver.load_model_config",
        return_value=fake_config,
    ):
        await ensure_row()
        yield


def _make_mock_chromadb(collection_name="resume_chunks__sentence_transformer__all_minilm_l6_v2"):
    """Build a mock chromadb module with AsyncHttpClient returning a fake client."""
    mock_collection = MagicMock()
    mock_collection.name = collection_name

    mock_client = AsyncMock()
    mock_client.get_or_create_collection = AsyncMock(return_value=mock_collection)

    mock_chromadb = MagicMock()
    mock_chromadb.AsyncHttpClient = AsyncMock(return_value=mock_client)
    return mock_chromadb, mock_collection


@pytest.mark.asyncio
async def test_active_collection_returns_none_when_no_active_signature():
    mock_chromadb, _ = _make_mock_chromadb()
    with patch("src.memory.collection_resolver.chromadb", mock_chromadb):
        result = await active_collection()
    assert result is None


@pytest.mark.asyncio
async def test_collection_for_signature_creates_collection():
    mock_chromadb, mock_collection = _make_mock_chromadb()
    with patch("src.memory.collection_resolver.chromadb", mock_chromadb):
        col = await collection_for_signature(
            "sentence_transformer__all_minilm_l6_v2",
            provider="sentence_transformer",
            model="all-MiniLM-L6-v2",
        )
    assert col is not None
    assert col.name == "resume_chunks__sentence_transformer__all_minilm_l6_v2"


@pytest.mark.asyncio
async def test_active_collection_returns_collection_for_active_signature():
    await set_active_signature("sentence_transformer__all_minilm_l6_v2")
    mock_chromadb, mock_collection = _make_mock_chromadb()
    with patch("src.memory.collection_resolver.chromadb", mock_chromadb):
        col = await active_collection()
    assert col is not None
    assert col.name == "resume_chunks__sentence_transformer__all_minilm_l6_v2"


@pytest.mark.asyncio
async def test_collection_for_signature_is_idempotent():
    mock_chromadb, mock_collection = _make_mock_chromadb()
    with patch("src.memory.collection_resolver.chromadb", mock_chromadb):
        col1 = await collection_for_signature(
            "sentence_transformer__all_minilm_l6_v2",
            provider="sentence_transformer",
            model="all-MiniLM-L6-v2",
        )
        col2 = await collection_for_signature(
            "sentence_transformer__all_minilm_l6_v2",
            provider="sentence_transformer",
            model="all-MiniLM-L6-v2",
        )
    assert col1.name == col2.name

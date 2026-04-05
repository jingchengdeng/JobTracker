import os
from pathlib import Path

import chromadb

from src.auth.credentials import load_model_config
from src.memory.embedding_state import get_active_signature
from src.memory.signatures import collection_name_for
from src.services.embeddings import embedding_function_for_signature

VECTORDB_DIR = os.environ.get(
    "VECTORDB_PATH",
    str(Path(__file__).parent.parent.parent.parent / "data" / "vectordb"),
)


def _client():
    # Re-read env each call so tests that monkeypatch VECTORDB_PATH work.
    path = os.environ.get("VECTORDB_PATH", VECTORDB_DIR)
    return chromadb.PersistentClient(path=path)


def active_collection():
    """Return the Chroma collection serving queries, or None if none active."""
    signature = get_active_signature()
    if signature is None:
        return None
    config = load_model_config()
    embedding = config["embedding"]
    return collection_for_signature(
        signature,
        provider=embedding["provider"],
        model=embedding["model"],
    )


def collection_for_signature(signature: str, *, provider: str, model: str):
    """Get-or-create the Chroma collection for a specific signature."""
    ef = embedding_function_for_signature(signature, provider=provider, model=model)
    return _client().get_or_create_collection(
        name=collection_name_for(signature),
        embedding_function=ef,
    )

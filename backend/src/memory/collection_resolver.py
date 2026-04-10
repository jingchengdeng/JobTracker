import asyncio
import os

import chromadb

from src.auth.credentials import load_model_config
from src.memory.embedding_state import get_active_signature
from src.memory.signatures import collection_name_for
from src.services.embeddings import embedding_function_for_signature

CHROMADB_HOST = os.environ.get("CHROMADB_HOST", "localhost")
CHROMADB_PORT = int(os.environ.get("CHROMADB_PORT", "8200"))

_chroma_client: chromadb.AsyncClientAPI | None = None
_chroma_lock = asyncio.Lock()


async def _client() -> chromadb.AsyncClientAPI:
    global _chroma_client
    async with _chroma_lock:
        if _chroma_client is None:
            _chroma_client = await chromadb.AsyncHttpClient(host=CHROMADB_HOST, port=CHROMADB_PORT)
    return _chroma_client


async def active_collection():
    """Return the Chroma collection serving queries, or None if none active."""
    signature = await get_active_signature()
    if signature is None:
        return None
    config = await load_model_config()
    embedding = config["embedding"]
    return await collection_for_signature(
        signature,
        provider=embedding["provider"],
        model=embedding["model"],
    )


async def collection_for_signature(signature: str, *, provider: str, model: str):
    """Get-or-create the Chroma collection for a specific signature."""
    ef = await embedding_function_for_signature(signature, provider=provider, model=model)
    client = await _client()
    return await client.get_or_create_collection(
        name=collection_name_for(signature),
        embedding_function=ef,
    )

import logging

from src.auth.credentials import load_model_config
from src.db import get_connection
from src.memory.collection_resolver import _client, collection_for_signature
from src.memory.embedding_state import get_active_signature, set_active_signature
from src.memory.signatures import signature_for

logger = logging.getLogger("jobtracker")

LEGACY_COLLECTION_NAME = "resume_chunks"


async def migrate_legacy_collection() -> None:
    """One-time migration from unsuffixed 'resume_chunks' collection to the
    signature-suffixed scheme. No-op if already migrated or nothing to do."""
    if await get_active_signature() is not None:
        return

    client = await _client()
    collections = await client.list_collections()
    legacy_names = [c.name for c in collections]
    if LEGACY_COLLECTION_NAME not in legacy_names:
        logger.info("No legacy resume_chunks collection; skipping migration")
        return

    config = load_model_config()
    embedding = config["embedding"]
    target_sig = signature_for(embedding["provider"], embedding["model"])
    logger.info("Migrating legacy collection to signature %s", target_sig)

    try:
        new_col = await collection_for_signature(
            target_sig, provider=embedding["provider"], model=embedding["model"]
        )
    except ValueError as exc:
        logger.warning("Cannot create target collection: %s", exc)
        return

    legacy = await client.get_collection(name=LEGACY_COLLECTION_NAME)
    payload = await legacy.get(include=["embeddings", "documents", "metadatas"])
    if payload["ids"]:
        embeddings = payload["embeddings"]
        if embeddings is not None:
            embeddings = [list(e) for e in embeddings]
        await new_col.add(
            ids=payload["ids"],
            embeddings=embeddings,
            documents=payload["documents"],
            metadatas=payload["metadatas"],
        )
        logger.info("Copied %d chunks to %s", len(payload["ids"]), new_col.name)

    resume_ids_with_chunks = {
        m["resume_id"] for m in (payload["metadatas"] or []) if m and "resume_id" in m
    }
    if resume_ids_with_chunks:
        async with get_connection() as conn:
            placeholders = ",".join("?" * len(resume_ids_with_chunks))
            await conn.execute(
                f"UPDATE resumes SET last_index_signature = ?, last_index_status = 'ok' "
                f"WHERE id IN ({placeholders})",
                (target_sig, *tuple(resume_ids_with_chunks)),
            )
            await conn.commit()

    await client.delete_collection(name=LEGACY_COLLECTION_NAME)
    await set_active_signature(target_sig)
    logger.info("Legacy migration complete; active_signature=%s", target_sig)

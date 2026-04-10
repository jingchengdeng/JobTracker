import asyncio
import logging
import re

from src.db import get_connection
from src.memory.collection_resolver import active_collection
from src.memory.embedding_state import get_active_signature
from src.memory.signatures import collection_name_for

logger = logging.getLogger("jobtracker.rag")

COLLECTION_NAME = "resume_chunks"  # legacy (pre-signature) collection name


async def index_resume(resume_id: int, resume_name: str, extracted_text: str):
    """Index a resume into the active collection and persist its state.

    No-op if no active signature yet (first-run before any reindex). The
    caller is expected to trigger a reindex after initial upload in that case.
    """
    col = await active_collection()
    if col is None:
        return
    active_sig = await get_active_signature()
    try:
        await index_resume_into(col, resume_id, resume_name, extracted_text)
    except Exception as exc:
        await mark_resume_failed(resume_id, str(exc))
        raise
    if active_sig is not None:
        await mark_resume_ok(resume_id, active_sig)


async def mark_resume_ok(resume_id: int, signature: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE resumes SET last_index_signature = ?, last_index_status = 'ok', "
            "last_index_error = NULL WHERE id = ?",
            (signature, resume_id),
        )
        await conn.commit()


async def mark_resume_failed(resume_id: int, error: str) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE resumes SET last_index_status = 'failed', last_index_error = ? "
            "WHERE id = ?",
            (error, resume_id),
        )
        await conn.commit()


async def index_resume_into(collection, resume_id: int, resume_name: str, extracted_text: str):
    """Index a resume into a specific Chroma collection."""
    try:
        existing = await collection.get(where={"resume_id": resume_id})
        if existing["ids"]:
            await collection.delete(ids=existing["ids"])
    except Exception:
        pass

    chunks = _chunk_resume(extracted_text)
    if not chunks:
        return

    ids = []
    documents = []
    metadatas = []
    for i, chunk in enumerate(chunks):
        chunk_id = f"resume-{resume_id}-chunk-{i}"
        enriched = f"{resume_name} -- {chunk['section']} -- {chunk['text']}"
        ids.append(chunk_id)
        documents.append(enriched)
        metadatas.append({
            "resume_id": resume_id,
            "resume_name": resume_name,
            "section_type": chunk["section"],
            "raw_text": chunk["text"],
        })

    await collection.add(ids=ids, documents=documents, metadatas=metadatas)


async def delete_resume_chunks(resume_id: int) -> int:
    """Delete all chunks for a resume. Returns the number removed."""
    col = await active_collection()
    if col is None:
        return 0
    existing = await col.get(where={"resume_id": resume_id})
    ids = existing["ids"] if existing else []
    if ids:
        await col.delete(ids=ids)
    return len(ids)


async def query_resume_corpus(query: str, n_results: int = 10, filters: dict | None = None):
    """Query the active collection for relevant experience chunks."""
    col = await active_collection()
    if col is None:
        return []

    where = filters if filters else None
    results = await col.query(query_texts=[query], n_results=n_results, where=where)

    chunks = []
    if results and results["documents"]:
        for i, doc in enumerate(results["documents"][0]):
            meta = results["metadatas"][0][i] if results["metadatas"] else {}
            chunks.append({
                "text": meta.get("raw_text", doc),
                "resume_name": meta.get("resume_name", ""),
                "section_type": meta.get("section_type", ""),
                "distance": results["distances"][0][i] if results["distances"] else None,
            })
    return chunks


def _chunk_resume(text: str) -> list[dict]:
    """Split resume text into chunks by role/entry."""
    lines = text.split("\n")
    chunks = []
    current_section = "general"
    current_chunk_lines = []

    section_keywords = {
        "experience": "experience",
        "work": "experience",
        "employment": "experience",
        "education": "education",
        "project": "project",
        "skill": "skills",
        "summary": "summary",
        "objective": "summary",
        "certification": "education",
    }

    date_pattern = re.compile(
        r"(20\d{2}|19\d{2})\s*[-\u2013]\s*(present|current|20\d{2}|19\d{2})", re.IGNORECASE
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        lower = stripped.lower()
        new_section = None
        for keyword, section in section_keywords.items():
            if keyword in lower and len(stripped) < 40:
                new_section = section
                break

        if new_section:
            if current_chunk_lines:
                chunks.append({
                    "section": current_section,
                    "text": "\n".join(current_chunk_lines).strip(),
                })
                current_chunk_lines = []
            current_section = new_section
            continue

        if date_pattern.search(stripped) and current_section == "experience":
            if current_chunk_lines:
                chunks.append({
                    "section": current_section,
                    "text": "\n".join(current_chunk_lines).strip(),
                })
                current_chunk_lines = []

        current_chunk_lines.append(stripped)

    if current_chunk_lines:
        chunks.append({
            "section": current_section,
            "text": "\n".join(current_chunk_lines).strip(),
        })

    return [c for c in chunks if len(c["text"]) > 20]


async def reconcile_resume_index_state() -> None:
    """Heal drift between SQL per-resume index state and real Chroma contents.

    Run at startup. Two passes:
      1. Any resume whose recorded signature points at a collection that no
         longer exists gets its signature/status cleared (NULL).
      2. Any resume with a NULL signature whose chunks DO exist in the active
         collection is marked ok with the active signature.
    """
    from src.memory.collection_resolver import _client
    from src.memory.embedding_state import get_active_signature as _get_active_sig

    try:
        client = await _client()
        collections = await client.list_collections()
        existing = {c.name for c in collections}
    except Exception as exc:
        logger.warning("reconcile: could not list Chroma collections: %s", exc)
        existing = set()

    async with get_connection() as conn:
        cursor = await conn.execute("SELECT id, last_index_signature FROM resumes")
        rows = await cursor.fetchall()

        # Phase 1: clear orphan signatures
        cleared = 0
        for r in rows:
            sig = r["last_index_signature"]
            if sig is None:
                continue
            if collection_name_for(sig) not in existing:
                await conn.execute(
                    "UPDATE resumes SET last_index_signature = NULL, "
                    "last_index_status = NULL, last_index_error = NULL WHERE id = ?",
                    (r["id"],),
                )
                cleared += 1
        if cleared:
            await conn.commit()
            logger.info("reconcile: cleared %d orphan resume signature(s)", cleared)

    # Phase 2: heal NULL signatures against active collection
    active_sig = await _get_active_sig()
    if active_sig is None:
        return
    active_name = collection_name_for(active_sig)
    if active_name not in existing:
        return

    try:
        col = await client.get_collection(name=active_name)
        result = await col.get(include=["metadatas"])
    except Exception as exc:
        logger.warning("reconcile: could not read active collection: %s", exc)
        return

    resume_ids_in_chroma: set[int] = set()
    for md in result.get("metadatas") or []:
        if md and md.get("resume_id") is not None:
            resume_ids_in_chroma.add(md["resume_id"])
    if not resume_ids_in_chroma:
        return

    async with get_connection() as conn:
        placeholders = ",".join("?" * len(resume_ids_in_chroma))
        cursor = await conn.execute(
            f"UPDATE resumes SET last_index_signature = ?, "
            f"last_index_status = 'ok', last_index_error = NULL "
            f"WHERE last_index_signature IS NULL AND id IN ({placeholders})",
            (active_sig, *resume_ids_in_chroma),
        )
        if cursor.rowcount:
            await conn.commit()
            logger.info("reconcile: healed %d NULL resume signature(s)", cursor.rowcount)

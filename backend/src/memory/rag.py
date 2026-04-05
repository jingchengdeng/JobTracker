import re

from src.db import get_connection
from src.memory.collection_resolver import active_collection, collection_for_signature
from src.memory.embedding_state import get_active_signature

COLLECTION_NAME = "resume_chunks"  # legacy (pre-signature) collection name


def index_resume(resume_id: int, resume_name: str, extracted_text: str):
    """Index a resume into the active collection and persist its state.

    No-op if no active signature yet (first-run before any reindex). The
    caller is expected to trigger a reindex after initial upload in that case.
    """
    col = active_collection()
    if col is None:
        return
    active_sig = get_active_signature()
    try:
        index_resume_into(col, resume_id, resume_name, extracted_text)
    except Exception as exc:
        mark_resume_failed(resume_id, str(exc))
        raise
    if active_sig is not None:
        mark_resume_ok(resume_id, active_sig)


def mark_resume_ok(resume_id: int, signature: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE resumes SET last_index_signature = ?, last_index_status = 'ok', "
            "last_index_error = NULL WHERE id = ?",
            (signature, resume_id),
        )
        conn.commit()
    finally:
        conn.close()


def mark_resume_failed(resume_id: int, error: str) -> None:
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE resumes SET last_index_status = 'failed', last_index_error = ? "
            "WHERE id = ?",
            (error, resume_id),
        )
        conn.commit()
    finally:
        conn.close()


def index_resume_into(collection, resume_id: int, resume_name: str, extracted_text: str):
    """Index a resume into a specific Chroma collection.

    Removes any existing chunks for this resume_id first, then adds fresh chunks.
    """
    try:
        existing = collection.get(where={"resume_id": resume_id})
        if existing["ids"]:
            collection.delete(ids=existing["ids"])
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

    collection.add(ids=ids, documents=documents, metadatas=metadatas)


def delete_resume_chunks(resume_id: int) -> int:
    """Delete all chunks for a resume. Returns the number removed."""
    col = active_collection()
    if col is None:
        return 0
    existing = col.get(where={"resume_id": resume_id})
    ids = existing["ids"] if existing else []
    if ids:
        col.delete(ids=ids)
    return len(ids)


def query_resume_corpus(query: str, n_results: int = 10, filters: dict | None = None):
    """Query the active collection for relevant experience chunks."""
    col = active_collection()
    if col is None:
        return []

    where = filters if filters else None
    results = col.query(query_texts=[query], n_results=n_results, where=where)

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

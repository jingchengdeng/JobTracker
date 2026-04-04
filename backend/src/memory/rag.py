import os
import re
from pathlib import Path

import chromadb

from src.services.embeddings import get_embedding_function

VECTORDB_DIR = os.environ.get(
    "VECTORDB_PATH",
    str(Path(__file__).parent.parent.parent.parent / "data" / "vectordb"),
)

COLLECTION_NAME = "resume_chunks"


def _get_collection():
    client = chromadb.PersistentClient(path=VECTORDB_DIR)
    ef = get_embedding_function()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
    )


def index_resume(resume_id: int, resume_name: str, extracted_text: str):
    """Chunk a resume by role/entry and index each chunk in ChromaDB."""
    collection = _get_collection()

    # Remove old chunks for this resume
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


def query_resume_corpus(query: str, n_results: int = 10, filters: dict | None = None):
    """Query the resume corpus for relevant experience chunks."""
    collection = _get_collection()

    where = filters if filters else None

    results = collection.query(
        query_texts=[query],
        n_results=n_results,
        where=where,
    )

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
    """Split resume text into chunks by role/entry.

    Heuristic: split on lines that look like role headers (contain date patterns,
    company names, or section headers). Falls back to paragraph-level splitting.
    """
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

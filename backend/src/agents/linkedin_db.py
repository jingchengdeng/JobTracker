import sqlite3

from src.db import get_connection


def ensure_linkedin_tables(db_path: str | None = None) -> None:
    """CREATE TABLE IF NOT EXISTS for linkedin_searches and linkedin_contacts. Idempotent."""
    if db_path:
        conn = sqlite3.connect(db_path)
    else:
        from src.db import get_sync_connection
        conn = get_sync_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS linkedin_searches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'running',
                company_domain TEXT,
                company_data_json TEXT,
                company_summary TEXT,
                started_at TEXT NOT NULL DEFAULT (datetime('now')),
                completed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS linkedin_contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                search_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                title TEXT NOT NULL,
                location TEXT,
                linkedin_url TEXT NOT NULL,
                source_query TEXT NOT NULL,
                relevance_score INTEGER NOT NULL,
                low_confidence INTEGER NOT NULL DEFAULT 0,
                connection_note TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


async def create_search(job_id: int) -> int:
    """Insert a new linkedin_searches row with status='running'. Returns the new id."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO linkedin_searches (job_id, status) VALUES (?, 'running')",
            (job_id,),
        )
        search_id = cursor.lastrowid
        await conn.commit()
        return search_id


async def load_search(search_id: int) -> dict:
    """Load a search by id. Raises ValueError if not found."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM linkedin_searches WHERE id = ?", (search_id,)
        )
        row = await cursor.fetchone()
    if not row:
        raise ValueError(f"Search {search_id} not found")
    return dict(row)


async def update_search_status(search_id: int, status: str) -> None:
    """Update the status of a search. Sets completed_at for 'completed' or 'failed'."""
    async with get_connection() as conn:
        if status in ("completed", "failed"):
            await conn.execute(
                "UPDATE linkedin_searches SET status = ?, completed_at = datetime('now') WHERE id = ?",
                (status, search_id),
            )
        else:
            await conn.execute(
                "UPDATE linkedin_searches SET status = ? WHERE id = ?",
                (status, search_id),
            )
        await conn.commit()


async def save_company_data(search_id: int, domain: str, data_json: str, summary: str) -> None:
    """Persist company domain, raw data JSON, and summary on the search row."""
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE linkedin_searches "
            "SET company_domain = ?, company_data_json = ?, company_summary = ? "
            "WHERE id = ?",
            (domain, data_json, summary, search_id),
        )
        await conn.commit()


async def save_contacts(search_id: int, contacts: list[dict]) -> None:
    """Bulk-insert contacts for a search. Each dict must have all required fields."""
    async with get_connection() as conn:
        await conn.executemany(
            "INSERT INTO linkedin_contacts "
            "(search_id, name, title, location, linkedin_url, source_query, "
            "relevance_score, low_confidence, connection_note) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    search_id,
                    c["name"],
                    c["title"],
                    c.get("location"),
                    c["linkedin_url"],
                    c["source_query"],
                    c["relevance_score"],
                    c.get("low_confidence", 0),
                    c["connection_note"],
                )
                for c in contacts
            ],
        )
        await conn.commit()


async def load_contacts(search_id: int) -> list[dict]:
    """Load all contacts for a search, sorted by relevance_score descending."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM linkedin_contacts WHERE search_id = ? ORDER BY relevance_score DESC",
            (search_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def delete_search(search_id: int) -> None:
    """Delete a search and all its contacts."""
    async with get_connection() as conn:
        await conn.execute("DELETE FROM linkedin_contacts WHERE search_id = ?", (search_id,))
        await conn.execute("DELETE FROM linkedin_searches WHERE id = ?", (search_id,))
        await conn.commit()


async def load_latest_search_for_job(job_id: int) -> dict | None:
    """Return the most recent search for a job, or None if none exist."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM linkedin_searches WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return dict(row)

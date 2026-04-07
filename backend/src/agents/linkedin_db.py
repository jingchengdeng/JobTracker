import sqlite3

from src.db import get_connection


def ensure_linkedin_tables(db_path: str) -> None:
    """CREATE TABLE IF NOT EXISTS for linkedin_searches and linkedin_contacts. Idempotent."""
    conn = sqlite3.connect(db_path)
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


def create_search(job_id: int) -> int:
    """Insert a new linkedin_searches row with status='running'. Returns the new id."""
    conn = get_connection()
    try:
        cursor = conn.execute(
            "INSERT INTO linkedin_searches (job_id, status) VALUES (?, 'running')",
            (job_id,),
        )
        search_id = cursor.lastrowid
        conn.commit()
        return search_id
    finally:
        conn.close()


def load_search(search_id: int) -> dict:
    """Load a search by id. Raises ValueError if not found."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM linkedin_searches WHERE id = ?", (search_id,)
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise ValueError(f"Search {search_id} not found")
    return dict(row)


def update_search_status(search_id: int, status: str) -> None:
    """Update the status of a search. Sets completed_at for 'completed' or 'failed'."""
    conn = get_connection()
    try:
        if status in ("completed", "failed"):
            conn.execute(
                "UPDATE linkedin_searches SET status = ?, completed_at = datetime('now') WHERE id = ?",
                (status, search_id),
            )
        else:
            conn.execute(
                "UPDATE linkedin_searches SET status = ? WHERE id = ?",
                (status, search_id),
            )
        conn.commit()
    finally:
        conn.close()


def save_company_data(search_id: int, domain: str, data_json: str, summary: str) -> None:
    """Persist company domain, raw data JSON, and summary on the search row."""
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE linkedin_searches "
            "SET company_domain = ?, company_data_json = ?, company_summary = ? "
            "WHERE id = ?",
            (domain, data_json, summary, search_id),
        )
        conn.commit()
    finally:
        conn.close()


def save_contacts(search_id: int, contacts: list[dict]) -> None:
    """Bulk-insert contacts for a search. Each dict must have all required fields."""
    conn = get_connection()
    try:
        conn.executemany(
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
        conn.commit()
    finally:
        conn.close()


def load_contacts(search_id: int) -> list[dict]:
    """Load all contacts for a search, sorted by relevance_score descending."""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM linkedin_contacts WHERE search_id = ? ORDER BY relevance_score DESC",
            (search_id,),
        ).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


def delete_search(search_id: int) -> None:
    """Delete a search and all its contacts."""
    conn = get_connection()
    try:
        conn.execute("DELETE FROM linkedin_contacts WHERE search_id = ?", (search_id,))
        conn.execute("DELETE FROM linkedin_searches WHERE id = ?", (search_id,))
        conn.commit()
    finally:
        conn.close()


def load_latest_search_for_job(job_id: int) -> dict | None:
    """Return the most recent search for a job, or None if none exist."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM linkedin_searches WHERE job_id = ? ORDER BY id DESC LIMIT 1",
            (job_id,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return dict(row)

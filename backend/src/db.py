import sqlite3
import os
from pathlib import Path


def get_db_path() -> str:
    """Return path to the shared SQLite database."""
    return os.environ.get(
        "JOBTRACKER_DB_PATH",
        str(Path(__file__).parent.parent.parent / "jobtracker.db"),
    )


def get_connection() -> sqlite3.Connection:
    """Open a connection to the shared SQLite database with WAL mode."""
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

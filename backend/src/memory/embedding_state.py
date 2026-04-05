from src.db import get_connection


def ensure_row() -> None:
    """Ensure the single embedding_state row (id=1) exists."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO embedding_state (id, active_signature) VALUES (1, NULL)"
        )
        conn.commit()
    finally:
        conn.close()


def get_active_signature() -> str | None:
    """Return the currently active embedding signature, or None."""
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT active_signature FROM embedding_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return None
        return row["active_signature"]
    finally:
        conn.close()


def set_active_signature(signature: str | None) -> None:
    """Write the active signature (creating the row if missing)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO embedding_state (id, active_signature, updated_at) "
            "VALUES (1, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET "
            "active_signature = excluded.active_signature, "
            "updated_at = datetime('now')",
            (signature,),
        )
        conn.commit()
    finally:
        conn.close()

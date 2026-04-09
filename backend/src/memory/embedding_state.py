from src.db import get_connection


async def ensure_row() -> None:
    """Ensure the single embedding_state row (id=1) exists."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT OR IGNORE INTO embedding_state (id, active_signature) VALUES (1, NULL)"
        )
        await conn.commit()


async def get_active_signature() -> str | None:
    """Return the currently active embedding signature, or None."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT active_signature FROM embedding_state WHERE id = 1"
        )
        row = await cursor.fetchone()
    if row is None:
        return None
    return row["active_signature"]


async def set_active_signature(signature: str | None) -> None:
    """Write the active signature (creating the row if missing)."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO embedding_state (id, active_signature, updated_at) "
            "VALUES (1, ?, datetime('now')) "
            "ON CONFLICT(id) DO UPDATE SET "
            "active_signature = excluded.active_signature, "
            "updated_at = datetime('now')",
            (signature,),
        )
        await conn.commit()

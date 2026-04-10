from src.db import get_connection


async def load_all_preferences() -> list[str]:
    """Load all user preferences as a list of strings for the system prompt."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT content FROM user_preferences ORDER BY created_at ASC"
        )
        rows = await cursor.fetchall()
    return [row["content"] for row in rows]

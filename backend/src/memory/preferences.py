from src.db import get_connection


def load_all_preferences() -> list[str]:
    """Load all user preferences as a list of strings for the system prompt."""
    conn = get_connection()
    rows = conn.execute("SELECT content FROM user_preferences ORDER BY created_at").fetchall()
    conn.close()
    return [row["content"] for row in rows]

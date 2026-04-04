from src.db import get_connection


MAX_RAW_ROUNDS = 3


def get_recent_messages(run_id: int) -> list[dict]:
    """Get the last MAX_RAW_ROUNDS rounds of messages for a run."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT role, content, round_number FROM ai_messages "
        "WHERE run_id = ? ORDER BY round_number DESC, id DESC",
        (run_id,),
    ).fetchall()
    conn.close()

    if not rows:
        return []

    round_numbers = sorted(set(r["round_number"] for r in rows), reverse=True)[
        :MAX_RAW_ROUNDS
    ]

    messages = []
    for row in reversed(rows):
        if row["round_number"] in round_numbers:
            messages.append({"role": row["role"], "content": row["content"]})

    return messages


def get_conversation_summary(run_id: int) -> str | None:
    """Get the running summary for older rounds."""
    conn = get_connection()
    row = conn.execute(
        "SELECT conversation_summary FROM ai_runs WHERE id = ?", (run_id,)
    ).fetchone()
    conn.close()
    return row["conversation_summary"] if row else None


def save_message(run_id: int, role: str, content: str, round_number: int):
    """Save a message to the ai_messages table."""
    conn = get_connection()
    conn.execute(
        "INSERT INTO ai_messages (run_id, role, content, round_number) VALUES (?, ?, ?, ?)",
        (run_id, role, content, round_number),
    )
    conn.commit()
    conn.close()


def get_current_round(run_id: int) -> int:
    """Get the next round number for a run."""
    conn = get_connection()
    row = conn.execute(
        "SELECT MAX(round_number) as max_round FROM ai_messages WHERE run_id = ?",
        (run_id,),
    ).fetchone()
    conn.close()
    current = row["max_round"] if row and row["max_round"] is not None else 0
    return current + 1


def summarize_old_rounds(run_id: int, llm):
    """Summarize rounds beyond MAX_RAW_ROUNDS and update the running summary."""
    conn = get_connection()

    rows = conn.execute(
        "SELECT DISTINCT round_number FROM ai_messages WHERE run_id = ? ORDER BY round_number",
        (run_id,),
    ).fetchall()
    all_rounds = [r["round_number"] for r in rows]

    if len(all_rounds) <= MAX_RAW_ROUNDS:
        conn.close()
        return

    rounds_to_summarize = all_rounds[: -MAX_RAW_ROUNDS]

    placeholders = ",".join("?" * len(rounds_to_summarize))
    messages = conn.execute(
        f"SELECT role, content, round_number FROM ai_messages "
        f"WHERE run_id = ? AND round_number IN ({placeholders}) "
        f"ORDER BY round_number, id",
        [run_id] + rounds_to_summarize,
    ).fetchall()

    if not messages:
        conn.close()
        return

    existing_summary = get_conversation_summary(run_id)
    text_to_summarize = ""
    if existing_summary:
        text_to_summarize += f"Previous summary:\n{existing_summary}\n\n"

    text_to_summarize += "New rounds to incorporate:\n"
    for msg in messages:
        text_to_summarize += f"[Round {msg['round_number']}] {msg['role']}: {msg['content'][:500]}\n"

    summary_prompt = (
        "Summarize this conversation history concisely. Focus on:\n"
        "- Key decisions the user made\n"
        "- Preferences expressed\n"
        "- Changes requested and why\n"
        "Keep it under 300 words.\n\n"
        f"{text_to_summarize}"
    )

    response = llm.invoke(summary_prompt)
    new_summary = response.content if hasattr(response, "content") else str(response)

    conn.execute(
        "UPDATE ai_runs SET conversation_summary = ? WHERE id = ?",
        (new_summary, run_id),
    )
    conn.execute(
        f"DELETE FROM ai_messages WHERE run_id = ? AND round_number IN ({placeholders})",
        [run_id] + rounds_to_summarize,
    )
    conn.commit()
    conn.close()

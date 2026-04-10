from src.db import get_connection


MAX_RAW_ROUNDS = 3


async def get_recent_messages(run_id: int) -> list[dict]:
    """Get the last MAX_RAW_ROUNDS rounds of messages for a run."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT role, content, round_number FROM ai_messages "
            "WHERE run_id = ? ORDER BY round_number DESC, id DESC",
            (run_id,),
        )
        rows = await cursor.fetchall()

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


async def get_conversation_summary(run_id: int) -> str | None:
    """Get the running summary for older rounds."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT conversation_summary FROM ai_runs WHERE id = ?", (run_id,)
        )
        row = await cursor.fetchone()
    return row["conversation_summary"] if row else None


async def save_message(run_id: int, role: str, content: str, round_number: int):
    """Save a message to the ai_messages table."""
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO ai_messages (run_id, role, content, round_number) VALUES (?, ?, ?, ?)",
            (run_id, role, content, round_number),
        )
        await conn.commit()


async def start_new_round(run_id: int, role: str, content: str) -> int:
    """Atomically compute next round number and insert the message. Returns the round number."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO ai_messages (run_id, role, content, round_number) "
            "VALUES (?, ?, ?, COALESCE((SELECT MAX(round_number) FROM ai_messages WHERE run_id = ?), 0) + 1) "
            "RETURNING round_number",
            (run_id, role, content, run_id),
        )
        row = await cursor.fetchone()
        await conn.commit()
    return row["round_number"]


async def get_current_round(run_id: int) -> int:
    """Get the current max round number for a run (0 if no messages)."""
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT MAX(round_number) as max_round FROM ai_messages WHERE run_id = ?",
            (run_id,),
        )
        row = await cursor.fetchone()
    return row["max_round"] if row and row["max_round"] is not None else 0


async def summarize_old_rounds(run_id: int, llm):
    """Summarize rounds beyond MAX_RAW_ROUNDS and update the running summary."""
    # Step 1: READ -- get all round numbers (connection closes after block)
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT DISTINCT round_number FROM ai_messages WHERE run_id = ? ORDER BY round_number",
            (run_id,),
        )
        rows = await cursor.fetchall()
    all_rounds = [r["round_number"] for r in rows]

    if len(all_rounds) <= MAX_RAW_ROUNDS:
        return

    rounds_to_summarize = all_rounds[: -MAX_RAW_ROUNDS]

    # Step 2: READ -- get messages for those rounds (connection closes after block)
    placeholders = ",".join("?" * len(rounds_to_summarize))
    async with get_connection() as conn:
        cursor = await conn.execute(
            f"SELECT role, content, round_number FROM ai_messages "
            f"WHERE run_id = ? AND round_number IN ({placeholders}) "
            f"ORDER BY round_number, id",
            [run_id] + rounds_to_summarize,
        )
        messages = await cursor.fetchall()

    if not messages:
        return

    existing_summary = await get_conversation_summary(run_id)
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

    # Step 3: LLM call -- NO connection held
    response = await llm.ainvoke(summary_prompt)
    new_summary = response.content if hasattr(response, "content") else str(response)

    # Step 4: WRITE -- new connection for updates
    async with get_connection() as conn:
        await conn.execute(
            "UPDATE ai_runs SET conversation_summary = ? WHERE id = ?",
            (new_summary, run_id),
        )
        await conn.execute(
            f"DELETE FROM ai_messages WHERE run_id = ? AND round_number IN ({placeholders})",
            [run_id] + rounds_to_summarize,
        )
        await conn.commit()

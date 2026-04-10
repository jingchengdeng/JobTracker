import json

from src.db import get_connection


async def create_session(
    job_id: int,
    resume_id: int | None,
    interview_type: str,
    difficulty: str,
    duration_minutes: int,
    voice: str,
    focus_area: str | None = None,
) -> int:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO interview_sessions "
            "(job_id, resume_id, interview_type, difficulty, duration_minutes, focus_area, voice) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (job_id, resume_id, interview_type, difficulty, duration_minutes, focus_area, voice),
        )
        session_id = cursor.lastrowid
        await conn.commit()
    return session_id


async def load_session(session_id: int) -> dict:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM interview_sessions WHERE id = ?", (session_id,)
        )
        row = await cursor.fetchone()
    if not row:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return dict(row)


async def update_session_status(session_id: int, status: str) -> None:
    async with get_connection() as conn:
        if status == "active":
            await conn.execute(
                "UPDATE interview_sessions SET status = ?, started_at = datetime('now') WHERE id = ?",
                (status, session_id),
            )
        elif status in ("completed", "interrupted"):
            await conn.execute(
                "UPDATE interview_sessions SET status = ?, ended_at = datetime('now') WHERE id = ?",
                (status, session_id),
            )
        else:
            await conn.execute(
                "UPDATE interview_sessions SET status = ? WHERE id = ?",
                (status, session_id),
            )
        await conn.commit()


async def save_plan(session_id: int, plan: dict) -> None:
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO interview_plans (session_id, plan_json, scoring_dimensions_json) VALUES (?, ?, ?)",
            (session_id, json.dumps(plan), "[]"),
        )
        await conn.commit()


async def load_plan(session_id: int) -> dict:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT plan_json FROM interview_plans WHERE session_id = ?",
            (session_id,),
        )
        row = await cursor.fetchone()
    if not row:
        raise ValueError(f"No plan for session {session_id}")
    return json.loads(row["plan_json"])


async def save_turn(
    session_id: int,
    role: str,
    text: str,
    audio_duration_ms: int | None = None,
    plan_topic_ref: str | None = None,
) -> int:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "INSERT INTO interview_turns (session_id, turn_number, role, text, audio_duration_ms, plan_topic_ref) "
            "VALUES (?, (SELECT COALESCE(MAX(turn_number), 0) + 1 FROM interview_turns WHERE session_id = ?), ?, ?, ?, ?)",
            (session_id, session_id, role, text, audio_duration_ms, plan_topic_ref),
        )
        turn_id = cursor.lastrowid
        await conn.commit()
    return turn_id


async def load_turns(session_id: int) -> list[dict]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM interview_turns WHERE session_id = ? ORDER BY turn_number",
            (session_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def save_results(session_id: int, results: dict) -> None:
    overall_score = sum(d["score"] for d in results["dimension_scores"])
    async with get_connection() as conn:
        await conn.execute(
            "INSERT INTO interview_results "
            "(session_id, overall_score, dimension_scores_json, strengths_json, "
            "improvements_json, model_answers_json, summary) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                overall_score,
                json.dumps(results["dimension_scores"]),
                json.dumps(results["strengths"]),
                json.dumps(results["improvements"]),
                json.dumps(results["model_answers"]),
                results["summary"],
            ),
        )
        await conn.commit()


async def load_results(session_id: int) -> dict | None:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM interview_results WHERE session_id = ?", (session_id,)
        )
        row = await cursor.fetchone()
    if not row:
        return None
    return dict(row)


async def list_sessions_for_job(job_id: int) -> list[dict]:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT s.id, s.interview_type, s.difficulty, s.status, s.created_at, "
            "r.overall_score "
            "FROM interview_sessions s "
            "LEFT JOIN interview_results r ON r.session_id = s.id "
            "WHERE s.job_id = ? ORDER BY s.created_at DESC",
            (job_id,),
        )
        rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def try_transition_to_scoring(session_id: int) -> bool:
    async with get_connection() as conn:
        cursor = await conn.execute(
            "UPDATE interview_sessions SET status = 'scoring' "
            "WHERE id = ? AND status IN ('planning', 'active', 'paused')",
            (session_id,),
        )
        await conn.commit()
        return cursor.rowcount == 1


async def delete_session(session_id: int) -> None:
    async with get_connection() as conn:
        await conn.execute("DELETE FROM interview_results WHERE session_id = ?", (session_id,))
        await conn.execute("DELETE FROM interview_turns WHERE session_id = ?", (session_id,))
        await conn.execute("DELETE FROM interview_plans WHERE session_id = ?", (session_id,))
        await conn.execute("DELETE FROM interview_sessions WHERE id = ?", (session_id,))
        await conn.commit()

import json

from src.db import get_connection


def create_session(
    job_id: int,
    resume_id: int | None,
    interview_type: str,
    difficulty: str,
    duration_minutes: int,
    voice: str,
    focus_area: str | None = None,
) -> int:
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO interview_sessions "
        "(job_id, resume_id, interview_type, difficulty, duration_minutes, focus_area, voice) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (job_id, resume_id, interview_type, difficulty, duration_minutes, focus_area, voice),
    )
    session_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return session_id


def load_session(session_id: int) -> dict:
    conn = get_connection()
    row = conn.execute("SELECT * FROM interview_sessions WHERE id = ?", (session_id,)).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"Session {session_id} not found")
    return dict(row)


def update_session_status(session_id: int, status: str) -> None:
    conn = get_connection()
    if status == "active":
        conn.execute(
            "UPDATE interview_sessions SET status = ?, started_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    elif status in ("completed", "interrupted"):
        conn.execute(
            "UPDATE interview_sessions SET status = ?, ended_at = datetime('now') WHERE id = ?",
            (status, session_id),
        )
    else:
        conn.execute(
            "UPDATE interview_sessions SET status = ? WHERE id = ?",
            (status, session_id),
        )
    conn.commit()
    conn.close()


def save_plan(session_id: int, plan: dict) -> None:
    conn = get_connection()
    conn.execute(
        "INSERT INTO interview_plans (session_id, plan_json, scoring_dimensions_json) VALUES (?, ?, ?)",
        (session_id, json.dumps(plan), "[]"),
    )
    conn.commit()
    conn.close()


def load_plan(session_id: int) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT plan_json FROM interview_plans WHERE session_id = ?",
        (session_id,),
    ).fetchone()
    conn.close()
    if not row:
        raise ValueError(f"No plan for session {session_id}")
    return json.loads(row["plan_json"])


def save_turn(
    session_id: int,
    role: str,
    text: str,
    audio_duration_ms: int | None = None,
    plan_topic_ref: str | None = None,
) -> int:
    conn = get_connection()
    current_max = conn.execute(
        "SELECT COALESCE(MAX(turn_number), 0) FROM interview_turns WHERE session_id = ?",
        (session_id,),
    ).fetchone()[0]
    turn_number = current_max + 1
    cursor = conn.execute(
        "INSERT INTO interview_turns (session_id, turn_number, role, text, audio_duration_ms, plan_topic_ref) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, turn_number, role, text, audio_duration_ms, plan_topic_ref),
    )
    turn_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return turn_id


def load_turns(session_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM interview_turns WHERE session_id = ? ORDER BY turn_number",
        (session_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_results(session_id: int, results: dict) -> None:
    overall_score = sum(d["score"] for d in results["dimension_scores"])
    conn = get_connection()
    conn.execute(
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
    conn.commit()
    conn.close()


def load_results(session_id: int) -> dict | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM interview_results WHERE session_id = ?", (session_id,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    return dict(row)


def list_sessions_for_job(job_id: int) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT s.id, s.interview_type, s.difficulty, s.status, s.created_at, "
        "r.overall_score "
        "FROM interview_sessions s "
        "LEFT JOIN interview_results r ON r.session_id = s.id "
        "WHERE s.job_id = ? ORDER BY s.created_at DESC",
        (job_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_session(session_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM interview_results WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM interview_turns WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM interview_plans WHERE session_id = ?", (session_id,))
    conn.execute("DELETE FROM interview_sessions WHERE id = ?", (session_id,))
    conn.commit()
    conn.close()

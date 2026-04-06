import json
import sqlite3
import pytest


def _create_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT, description TEXT);
        CREATE TABLE resumes (id INTEGER PRIMARY KEY, name TEXT, extracted_text TEXT);
        CREATE TABLE interview_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            resume_id INTEGER,
            status TEXT NOT NULL DEFAULT 'planning',
            interview_type TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            duration_minutes INTEGER NOT NULL,
            focus_area TEXT,
            voice TEXT NOT NULL DEFAULT 'nova',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            started_at TEXT,
            ended_at TEXT
        );
        CREATE TABLE interview_plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            plan_json TEXT NOT NULL,
            scoring_dimensions_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE interview_turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            turn_number INTEGER NOT NULL,
            role TEXT NOT NULL,
            text TEXT NOT NULL,
            audio_duration_ms INTEGER,
            plan_topic_ref TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE interview_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL UNIQUE,
            overall_score INTEGER NOT NULL,
            dimension_scores_json TEXT NOT NULL,
            strengths_json TEXT NOT NULL,
            improvements_json TEXT NOT NULL,
            model_answers_json TEXT NOT NULL,
            summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO jobs (id, title, company, description) VALUES (1, 'SWE', 'Acme', 'Build things');
        INSERT INTO resumes (id, name, extracted_text) VALUES (1, 'Resume', 'I am a developer');
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    _create_tables(db_path)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


class TestCreateSession:
    def test_creates_session_with_planning_status(self, test_db):
        from src.agents.interview_db import create_session

        session_id = create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        assert session_id > 0

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM interview_sessions WHERE id = ?", (session_id,)).fetchone()
        conn.close()
        assert row["status"] == "planning"
        assert row["interview_type"] == "technical"

    def test_nullable_resume_id(self, test_db):
        from src.agents.interview_db import create_session

        session_id = create_session(
            job_id=1, resume_id=None, interview_type="behavioral",
            difficulty="easy", duration_minutes=15, voice="alloy",
        )
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT resume_id FROM interview_sessions WHERE id = ?", (session_id,)).fetchone()
        conn.close()
        assert row["resume_id"] is None


class TestSavePlan:
    def test_saves_and_loads_plan(self, test_db):
        from src.agents.interview_db import create_session, save_plan, load_plan

        session_id = create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        plan = {"topics": [], "opening_prompt": "Hi"}
        save_plan(session_id, plan)

        loaded_plan = load_plan(session_id)
        assert loaded_plan["opening_prompt"] == "Hi"


class TestSaveTurn:
    def test_saves_turn_with_auto_number(self, test_db):
        from src.agents.interview_db import create_session, save_turn, load_turns

        session_id = create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        save_turn(session_id, "interviewer", "Tell me about yourself.", plan_topic_ref="intro")
        save_turn(session_id, "candidate", "I am a developer.")
        turns = load_turns(session_id)
        assert len(turns) == 2
        assert turns[0]["turn_number"] == 1
        assert turns[0]["role"] == "interviewer"
        assert turns[1]["turn_number"] == 2
        assert turns[1]["role"] == "candidate"


class TestSessionStatus:
    def test_update_status(self, test_db):
        from src.agents.interview_db import create_session, update_session_status, load_session

        session_id = create_session(
            job_id=1, resume_id=1, interview_type="technical",
            difficulty="medium", duration_minutes=30, voice="nova",
        )
        update_session_status(session_id, "active")
        session = load_session(session_id)
        assert session["status"] == "active"

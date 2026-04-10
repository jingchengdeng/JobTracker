import sqlite3
import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _create_tables(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            company TEXT,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS resumes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            extracted_text TEXT,
            is_default INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS ai_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER,
            resume_id INTEGER,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS ai_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            step_name TEXT,
            status TEXT
        );
        CREATE TABLE IF NOT EXISTS linkedin_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            company_domain TEXT,
            company_data_json TEXT,
            company_summary TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS linkedin_contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            search_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            title TEXT NOT NULL,
            location TEXT,
            linkedin_url TEXT NOT NULL,
            source_query TEXT NOT NULL,
            relevance_score INTEGER NOT NULL,
            low_confidence INTEGER NOT NULL DEFAULT 0,
            connection_note TEXT NOT NULL
        );
    """)
    conn.commit()
    conn.close()


@pytest.fixture
def test_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    _create_tables(db_path)
    monkeypatch.setenv("JOBTRACKER_DB_PATH", db_path)
    return db_path


@pytest.fixture
async def migrated_db_with_resumes(migrated_db):
    """Extends migrated_db (which has pipeline_events) with a resumes table."""
    import aiosqlite
    async with aiosqlite.connect(migrated_db) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                extracted_text TEXT,
                is_default INTEGER NOT NULL DEFAULT 0
            )
        """)
        await conn.commit()
    return migrated_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(**overrides) -> dict:
    base = {
        "workflow_run_id": "test-run-id",
        "raw_text": "Some job text",
        "url": "https://linkedin.com/jobs/view/123",
        "extracted": {
            "title": "Software Engineer",
            "company": "Acme Corp",
            "description": "Build cool stuff.",
            "location": "Remote",
            "salary_min": None,
            "salary_max": None,
            "salary_currency": None,
            "job_type": "full_time",
            "work_mode": "remote",
        },
        "validation_errors": [],
        "retry_count": 0,
        "job_id": 42,
        "error": None,
        "default_resume_id": None,
        "default_resume_text": None,
        "default_resume_name": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Tests for _should_fan_out
# ---------------------------------------------------------------------------

class TestShouldFanOut:
    async def test_returns_end_when_job_id_is_none(self):
        from src.agents.master_workflow import _should_fan_out

        state = _make_state(job_id=None)
        assert await _should_fan_out(state) == "end"

    async def test_returns_end_when_error_present(self):
        from src.agents.master_workflow import _should_fan_out

        state = _make_state(job_id=42, error="Something went wrong")
        assert await _should_fan_out(state) == "end"

    async def test_returns_end_when_both_job_id_none_and_error(self):
        from src.agents.master_workflow import _should_fan_out

        state = _make_state(job_id=None, error="Failed to insert")
        assert await _should_fan_out(state) == "end"

    async def test_returns_resolve_default_resume_when_job_id_exists(self):
        from src.agents.master_workflow import _should_fan_out

        state = _make_state(job_id=99, error=None)
        assert await _should_fan_out(state) == "resolve_default_resume"

    async def test_returns_resolve_default_resume_with_zero_is_still_no_job(self):
        from src.agents.master_workflow import _should_fan_out

        # job_id=0 is falsy, should be treated as no job
        state = _make_state(job_id=0, error=None)
        assert await _should_fan_out(state) == "end"


# ---------------------------------------------------------------------------
# Tests for fan_out
# ---------------------------------------------------------------------------

class TestFanOut:
    async def test_returns_only_linkedin_when_no_default_resume(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=None,
            default_resume_text=None,
            default_resume_name=None,
        )
        sends = await fan_out(state)

        assert len(sends) == 1
        assert isinstance(sends[0], Send)
        assert sends[0].node == "linkedin_branch"
        assert sends[0].arg["job_id"] == 42

    async def test_returns_both_when_default_resume_exists(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=7,
            default_resume_text="My resume text here.",
            default_resume_name="My Resume",
        )
        sends = await fan_out(state)

        assert len(sends) == 2
        nodes = {s.node for s in sends}
        assert nodes == {"linkedin_branch", "resume_branch"}

    async def test_resume_branch_send_has_correct_payload(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=7,
            default_resume_text="My resume text.",
            default_resume_name="Dev Resume",
        )
        sends = await fan_out(state)

        resume_send = next(s for s in sends if s.node == "resume_branch")
        assert resume_send.arg["job_id"] == 42
        assert resume_send.arg["resume_id"] == 7
        assert resume_send.arg["resume_text"] == "My resume text."
        assert resume_send.arg["resume_name"] == "Dev Resume"

    async def test_returns_only_linkedin_when_resume_text_is_none(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=7,
            default_resume_text=None,  # no extracted text
            default_resume_name="My Resume",
        )
        sends = await fan_out(state)

        assert len(sends) == 1
        assert sends[0].node == "linkedin_branch"

    async def test_returns_only_linkedin_when_resume_id_is_none(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=None,
            default_resume_text="Some text",  # text present but no id
            default_resume_name=None,
        )
        sends = await fan_out(state)

        assert len(sends) == 1
        assert sends[0].node == "linkedin_branch"

    async def test_linkedin_branch_send_carries_job_id(self):
        from langgraph.types import Send
        from src.agents.master_workflow import fan_out

        state = _make_state(job_id=55, default_resume_id=None, default_resume_text=None, default_resume_name=None)
        sends = await fan_out(state)

        linkedin_send = sends[0]
        assert linkedin_send.arg["job_id"] == 55

    async def test_description_passed_to_resume_branch(self):
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=7,
            default_resume_text="Resume text",
            default_resume_name="Resume",
            extracted={
                "title": "Engineer",
                "company": "Acme",
                "description": "Build things.",
                "location": None,
            },
        )
        sends = await fan_out(state)
        resume_send = next(s for s in sends if s.node == "resume_branch")
        assert resume_send.arg["description"] == "Build things."

    async def test_description_is_none_when_extracted_is_none(self):
        from src.agents.master_workflow import fan_out

        state = _make_state(
            job_id=42,
            default_resume_id=7,
            default_resume_text="Resume text",
            default_resume_name="Resume",
            extracted=None,
        )
        sends = await fan_out(state)
        resume_send = next(s for s in sends if s.node == "resume_branch")
        assert resume_send.arg["description"] is None


# ---------------------------------------------------------------------------
# Tests for resolve_default_resume
# ---------------------------------------------------------------------------

class TestResolveDefaultResume:
    async def test_finds_default_resume(self, migrated_db_with_resumes):
        import aiosqlite
        async with aiosqlite.connect(migrated_db_with_resumes) as conn:
            await conn.execute(
                "INSERT INTO resumes (name, extracted_text, is_default) VALUES (?, ?, ?)",
                ("My Resume", "Full resume text here.", 1),
            )
            await conn.commit()

        from src.agents.master_workflow import resolve_default_resume

        # job_id=None avoids FK violation; job is not yet resolved at this node
        state = _make_state(job_id=None)
        result = await resolve_default_resume(state)

        assert result["default_resume_id"] is not None
        assert result["default_resume_text"] == "Full resume text here."
        assert result["default_resume_name"] == "My Resume"

    async def test_returns_none_fields_when_no_default_resume(self, migrated_db_with_resumes):
        from src.agents.master_workflow import resolve_default_resume

        state = _make_state(job_id=None)
        result = await resolve_default_resume(state)

        assert result["default_resume_id"] is None
        assert result["default_resume_text"] is None
        assert result["default_resume_name"] is None

    async def test_returns_none_when_default_resume_has_no_text(self, migrated_db_with_resumes):
        import aiosqlite
        async with aiosqlite.connect(migrated_db_with_resumes) as conn:
            await conn.execute(
                "INSERT INTO resumes (name, extracted_text, is_default) VALUES (?, ?, ?)",
                ("My Resume", None, 1),
            )
            await conn.commit()

        from src.agents.master_workflow import resolve_default_resume

        state = _make_state(job_id=None)
        result = await resolve_default_resume(state)

        assert result["default_resume_id"] is None
        assert result["default_resume_text"] is None
        assert result["default_resume_name"] is None

    async def test_ignores_non_default_resumes(self, migrated_db_with_resumes):
        import aiosqlite
        async with aiosqlite.connect(migrated_db_with_resumes) as conn:
            await conn.execute(
                "INSERT INTO resumes (name, extracted_text, is_default) VALUES (?, ?, ?)",
                ("Not Default", "Some text.", 0),
            )
            await conn.commit()

        from src.agents.master_workflow import resolve_default_resume

        state = _make_state(job_id=None)
        result = await resolve_default_resume(state)

        assert result["default_resume_id"] is None


# ---------------------------------------------------------------------------
# Tests for build_master_graph (import/compile smoke test)
# ---------------------------------------------------------------------------

class TestBuildMasterGraph:
    def test_graph_compiles_without_error(self):
        from src.agents.master_workflow import build_master_graph

        graph = build_master_graph()
        compiled = graph.compile()
        assert compiled is not None

    def test_module_level_compiled_graph_exists(self):
        from src.agents.master_workflow import _compiled_master_graph

        assert _compiled_master_graph is not None


# ---------------------------------------------------------------------------
# Tests for run_master_workflow
# ---------------------------------------------------------------------------

class TestRunMasterWorkflow:
    async def test_returns_error_on_extraction_failure(self, monkeypatch):
        """When extraction LLM fails, run_master_workflow returns error dict."""
        from unittest.mock import patch, AsyncMock

        # Make the LLM raise immediately
        with patch("src.agents.extraction_pipeline.get_linkedin_model") as mock_model:
            mock_model.side_effect = RuntimeError("No API key")

            from src.agents.master_workflow import run_master_workflow

            result = await run_master_workflow("raw text", "https://example.com")

        assert result["job_id"] is None
        assert result["error"] is not None


# ---------------------------------------------------------------------------
# Integration test: master-level instrumentation writes pipeline_events rows
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resolve_default_resume_writes_pipeline_events(migrated_db_with_resumes):
    """Calling resolve_default_resume writes a 'master/resolve_default_resume' row."""
    import aiosqlite
    from src.agents.master_workflow import resolve_default_resume

    state = _make_state(workflow_run_id="master-integration-1", job_id=None)
    await resolve_default_resume(state)

    async with aiosqlite.connect(migrated_db_with_resumes) as conn:
        conn.row_factory = aiosqlite.Row
        cursor = await conn.execute(
            "SELECT graph, node_name FROM pipeline_events "
            "WHERE workflow_run_id='master-integration-1'"
        )
        rows = await cursor.fetchall()

    assert len(rows) >= 1
    assert any(r["graph"] == "master" and r["node_name"] == "resolve_default_resume" for r in rows)

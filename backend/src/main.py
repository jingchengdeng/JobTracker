import os
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before any other import reads os.environ.
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_connection
from src.api.exception_handlers import register_exception_handlers

logger = logging.getLogger("jobtracker")


def _ensure_round_number_column(db_path: str) -> None:
    """Add round_number column to ai_steps if missing. Idempotent."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_steps)").fetchall()}
        if "round_number" not in cols:
            conn.execute(
                "ALTER TABLE ai_steps ADD COLUMN round_number INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Check LangSmith config
    if os.environ.get("LANGSMITH_API_KEY"):
        logger.info("LangSmith tracing enabled")
    else:
        logger.info("LangSmith tracing disabled (set LANGSMITH_API_KEY to enable)")

    # Startup: mark any interrupted runs as failed
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE ai_runs SET status = 'failed', error = 'Interrupted -- click Retry to re-run.' "
            "WHERE status = 'running'"
        )
        conn.commit()
    except Exception as exc:
        logger.warning("Stale-run recovery skipped: %s", exc)
    finally:
        conn.close()

    # Startup: mark interrupted interview sessions
    try:
        conn = get_connection()
        conn.execute(
            "UPDATE interview_sessions SET status = 'interrupted', ended_at = datetime('now') "
            "WHERE status IN ('active', 'paused')"
        )
        conn.commit()
        conn.close()
    except Exception as exc:
        logger.warning("Interview session recovery skipped: %s", exc)

    try:
        from src.memory.embedding_state import ensure_row
        from src.memory.legacy_migration import migrate_legacy_collection
        ensure_row()
        migrate_legacy_collection()
    except Exception as exc:
        logger.warning("Legacy embedding migration skipped: %s", exc)

    try:
        from src.memory.rag import reconcile_resume_index_state
        reconcile_resume_index_state()
    except Exception as exc:
        logger.warning("Resume index reconciliation skipped: %s", exc)

    try:
        from src.db import get_db_path
        _ensure_round_number_column(get_db_path())
    except Exception as exc:
        logger.warning("round_number migration skipped: %s", exc)

    yield


app = FastAPI(title="JobTracker AI Backend", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.routes import router
from src.api.embedding_routes import router as embedding_router
from src.api.interview_routes import router as interview_router

app.include_router(router)
app.include_router(embedding_router)
app.include_router(interview_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

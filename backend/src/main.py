import os
import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env before any other import reads os.environ.
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_connection, get_sync_connection
from src.api.exception_handlers import register_exception_handlers

logger = logging.getLogger("jobtracker")

# Global set for tracking background tasks for graceful shutdown
_background_tasks: set[asyncio.Task] = set()


def _ensure_round_number_column() -> None:
    """Add round_number column to ai_steps if missing. Idempotent."""
    conn = get_sync_connection()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_steps)").fetchall()}
        if "round_number" not in cols:
            conn.execute(
                "ALTER TABLE ai_steps ADD COLUMN round_number INTEGER NOT NULL DEFAULT 0"
            )
            conn.commit()
    finally:
        conn.close()


def _ensure_linkedin_tables() -> None:
    """Create linkedin_searches and linkedin_contacts tables if missing."""
    from src.agents.linkedin_db import ensure_linkedin_tables
    ensure_linkedin_tables()


def _ensure_interview_plans_table() -> None:
    """Create interview_plans table if missing. Backend-only, not in Drizzle schema."""
    conn = get_sync_connection()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS interview_plans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL UNIQUE,
                plan_json TEXT NOT NULL,
                scoring_dimensions_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        conn.commit()
    finally:
        conn.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-event-loop startup (sync, idempotent schema migrations)
    try:
        _ensure_round_number_column()
        _ensure_interview_plans_table()
        _ensure_linkedin_tables()
    except Exception as exc:
        logger.warning("Schema migration skipped: %s", exc)

    # LangSmith config
    if os.environ.get("LANGSMITH_API_KEY"):
        logger.info("LangSmith tracing enabled")
    else:
        logger.info("LangSmith tracing disabled (set LANGSMITH_API_KEY to enable)")

    # Async startup: mark interrupted runs as failed
    try:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE ai_runs SET status = 'failed', error = 'Interrupted -- click Retry to re-run.' "
                "WHERE status = 'running'"
            )
            await conn.commit()
    except Exception as exc:
        logger.warning("Stale-run recovery skipped: %s", exc)

    try:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE interview_sessions SET status = 'interrupted', ended_at = datetime('now') "
                "WHERE status IN ('planning', 'active', 'paused', 'scoring')"
            )
            await conn.commit()
    except Exception as exc:
        logger.warning("Interview session recovery skipped: %s", exc)

    try:
        async with get_connection() as conn:
            await conn.execute(
                "UPDATE linkedin_searches SET status = 'failed', completed_at = datetime('now') "
                "WHERE status IN ('pending', 'running')"
            )
            await conn.commit()
    except Exception as exc:
        logger.warning("LinkedIn search recovery skipped: %s", exc)

    # Async startup: embedding state + legacy migration
    try:
        from src.memory.embedding_state import ensure_row
        from src.memory.legacy_migration import migrate_legacy_collection
        await ensure_row()
        await migrate_legacy_collection()
    except Exception as exc:
        logger.warning("Legacy embedding migration skipped: %s", exc)

    try:
        from src.memory.rag import reconcile_resume_index_state
        await reconcile_resume_index_state()
    except Exception as exc:
        logger.warning("Resume index reconciliation skipped: %s", exc)

    # ChromaDB health check with retry
    import chromadb
    for attempt in range(3):
        try:
            chroma_host = os.environ.get("CHROMADB_HOST", "localhost")
            chroma_port = int(os.environ.get("CHROMADB_PORT", "8200"))
            client = await chromadb.AsyncHttpClient(host=chroma_host, port=chroma_port)
            await client.heartbeat()
            logger.info("ChromaDB server connected at %s:%s", chroma_host, chroma_port)
            break
        except Exception as exc:
            if attempt < 2:
                logger.warning("ChromaDB not ready (attempt %d/3): %s", attempt + 1, exc)
                await asyncio.sleep(2)
            else:
                logger.warning("ChromaDB unreachable after 3 attempts -- RAG features will be unavailable")

    # Background task: expire stale interview sessions
    async def _expire_stale_sessions():
        while True:
            await asyncio.sleep(300)
            try:
                async with get_connection() as conn:
                    await conn.execute(
                        "UPDATE interview_sessions SET status = 'interrupted', ended_at = datetime('now') "
                        "WHERE status IN ('planning', 'active', 'paused') "
                        "AND created_at < datetime('now', '-2 hours')"
                    )
                    await conn.commit()
            except Exception as exc:
                logger.warning("Session expiry check failed: %s", exc)

    expiry_task = asyncio.create_task(_expire_stale_sessions())
    _background_tasks.add(expiry_task)
    expiry_task.add_done_callback(_background_tasks.discard)

    yield

    # Graceful shutdown: collect background tasks from all route modules
    all_tasks = set(_background_tasks)
    for module_path in [
        "src.api.routes",
        "src.api.linkedin_routes",
        "src.api.extension_routes",
        "src.api.interview_routes",
    ]:
        try:
            import importlib
            mod = importlib.import_module(module_path)
            module_tasks = getattr(mod, "_background_tasks", set())
            all_tasks |= module_tasks
        except (ImportError, AttributeError):
            pass

    all_tasks.discard(asyncio.current_task())

    if all_tasks:
        logger.info("Waiting for %d background tasks to complete (30s timeout)...", len(all_tasks))
        done, pending = await asyncio.wait(all_tasks, timeout=30)
        if pending:
            logger.warning("Cancelling %d remaining background tasks", len(pending))
            for task in pending:
                task.cancel()
            await asyncio.wait(pending, timeout=5)


app = FastAPI(title="JobTracker AI Backend", lifespan=lifespan)
register_exception_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_methods=["*"],
    allow_headers=["*"],
)

from src.api.routes import router
from src.api.embedding_routes import router as embedding_router
from src.api.interview_routes import router as interview_router
from src.api.linkedin_routes import router as linkedin_router
from src.api.extension_routes import router as extension_router

app.include_router(router)
app.include_router(embedding_router)
app.include_router(interview_router)
app.include_router(linkedin_router)
app.include_router(extension_router)


from fastapi import WebSocket
from src.api.interview_ws import interview_ws_handler


@app.websocket("/ws/interview/{session_id}")
async def interview_websocket(websocket: WebSocket, session_id: int):
    await interview_ws_handler(websocket, session_id)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.db import get_connection
from src.api.exception_handlers import register_exception_handlers

logger = logging.getLogger("jobtracker")


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

    try:
        from src.memory.embedding_state import ensure_row
        from src.memory.legacy_migration import migrate_legacy_collection
        ensure_row()
        migrate_legacy_collection()
    except Exception as exc:
        logger.warning("Legacy embedding migration skipped: %s", exc)

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

app.include_router(router)
app.include_router(embedding_router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}

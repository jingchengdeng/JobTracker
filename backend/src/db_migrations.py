"""Startup migrations for the JobTracker backend.

Called from the async FastAPI lifespan context manager in `main.py`.
Every DB call is awaited — no sync connection is used anywhere. Idempotent
via existence checks on the source tables.
"""
import logging

from src.db import get_connection

logger = logging.getLogger(__name__)


PIPELINE_EVENTS_DDL = """
CREATE TABLE IF NOT EXISTS pipeline_events (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_run_id   TEXT    NOT NULL,
    job_id            INTEGER,
    graph             TEXT    NOT NULL,
    node_name         TEXT    NOT NULL,
    status            TEXT    NOT NULL,
    attempt           INTEGER NOT NULL DEFAULT 1,
    started_at        TEXT,
    completed_at      TEXT,
    duration_ms       INTEGER,
    error             TEXT,
    traceback         TEXT,
    run_id            INTEGER,
    step_type         TEXT,
    result            TEXT,
    version           INTEGER NOT NULL DEFAULT 1,
    round_number      INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES ai_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_pipeline_events_job
    ON pipeline_events(job_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_workflow
    ON pipeline_events(workflow_run_id);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_run_step
    ON pipeline_events(run_id, step_type, version);
CREATE INDEX IF NOT EXISTS idx_pipeline_events_latest
    ON pipeline_events(job_id, graph, node_name, started_at DESC);
"""


async def migrate_ai_steps_to_pipeline_events() -> None:
    """Backfill ai_steps into pipeline_events and drop the old table.

    Idempotent: existence check on ai_steps short-circuits re-runs. If any
    step inside the transaction fails, the whole migration rolls back and
    ai_steps is preserved, so the server starts with the old table still
    in place and the debug tab features disabled.
    """
    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ai_steps'"
        )
        row = await cursor.fetchone()
        await cursor.close()
        if not row:
            return

        await conn.executescript(PIPELINE_EVENTS_DDL)

        cursor = await conn.execute("PRAGMA table_info(ai_steps)")
        cols = {r[1] for r in await cursor.fetchall()}
        await cursor.close()
        if "round_number" not in cols:
            await conn.execute(
                "ALTER TABLE ai_steps ADD COLUMN round_number INTEGER NOT NULL DEFAULT 0"
            )

        await conn.execute("PRAGMA foreign_keys = OFF")
        try:
            await conn.execute("BEGIN")

            cursor = await conn.execute(
                """
                SELECT COUNT(*)
                  FROM ai_steps s
                  JOIN ai_runs r ON r.id = s.run_id
             LEFT JOIN jobs j    ON j.id = r.job_id
                 WHERE j.id IS NULL
                """
            )
            (orphan_count,) = await cursor.fetchone()
            await cursor.close()
            if orphan_count:
                logger.warning(
                    "pipeline_events backfill: %d ai_steps rows orphaned "
                    "from deleted jobs will be skipped",
                    orphan_count,
                )

            await conn.execute(
                """
                INSERT INTO pipeline_events (
                    workflow_run_id, job_id, graph, node_name,
                    status, attempt, completed_at, duration_ms,
                    result, run_id, step_type, version, round_number
                )
                SELECT
                    'legacy-' || r.id,
                    r.job_id,
                    'resume',
                    s.step_type,
                    s.status,
                    1,
                    s.completed_at,
                    NULL,
                    s.result,
                    s.run_id,
                    s.step_type,
                    s.version,
                    s.round_number
                  FROM ai_steps s
                  JOIN ai_runs r ON r.id = s.run_id
                  JOIN jobs j    ON j.id = r.job_id
                """
            )

            await conn.execute("DROP TABLE ai_steps")
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise
        finally:
            await conn.execute("PRAGMA foreign_keys = ON")

        await conn.commit()

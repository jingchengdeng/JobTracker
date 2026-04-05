import sqlite3
import pytest

from src.main import _ensure_round_number_column


@pytest.fixture
def legacy_db(tmp_path):
    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE ai_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            step_type TEXT,
            status TEXT,
            result TEXT,
            version INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            completed_at TEXT
        );
        INSERT INTO ai_steps (run_id, step_type, status, result)
            VALUES (1, 'jd_analysis', 'completed', '{}'),
                   (1, 'rewrite', 'completed', '{}');
        """
    )
    conn.commit()
    conn.close()
    return db_path


def test_migration_adds_column_with_default_zero(legacy_db):
    _ensure_round_number_column(legacy_db)
    conn = sqlite3.connect(legacy_db)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(ai_steps)").fetchall()}
    assert "round_number" in cols
    rows = conn.execute("SELECT round_number FROM ai_steps").fetchall()
    conn.close()
    assert all(r[0] == 0 for r in rows)


def test_migration_is_idempotent(legacy_db):
    _ensure_round_number_column(legacy_db)
    _ensure_round_number_column(legacy_db)  # should not raise
    conn = sqlite3.connect(legacy_db)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(ai_steps)").fetchall()]
    conn.close()
    assert cols.count("round_number") == 1


def test_migration_noop_when_column_exists(tmp_path):
    db_path = str(tmp_path / "new.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE ai_steps (id INTEGER PRIMARY KEY, round_number INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO ai_steps (round_number) VALUES (3)")
    conn.commit()
    conn.close()
    _ensure_round_number_column(db_path)
    conn = sqlite3.connect(db_path)
    row = conn.execute("SELECT round_number FROM ai_steps WHERE id = 1").fetchone()
    conn.close()
    assert row[0] == 3

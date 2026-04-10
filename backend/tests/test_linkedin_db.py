import sqlite3
import pytest


def _create_tables(db_path):
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE jobs (id INTEGER PRIMARY KEY, title TEXT, company TEXT, description TEXT);
        INSERT INTO jobs (id, title, company, description) VALUES (1, 'SWE', 'Acme', 'Build things');
        CREATE TABLE linkedin_searches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'running',
            company_domain TEXT,
            company_data_json TEXT,
            company_summary TEXT,
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            completed_at TEXT
        );
        CREATE TABLE linkedin_contacts (
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


class TestCreateSearch:
    async def test_returns_positive_id(self, test_db):
        from src.agents.linkedin_db import create_search

        search_id = await create_search(job_id=1)
        assert search_id > 0

    async def test_initial_status_is_running(self, test_db):
        from src.agents.linkedin_db import create_search

        search_id = await create_search(job_id=1)
        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM linkedin_searches WHERE id = ?", (search_id,)).fetchone()
        conn.close()
        assert row["status"] == "running"
        assert row["job_id"] == 1

    async def test_multiple_searches_for_same_job(self, test_db):
        from src.agents.linkedin_db import create_search

        id1 = await create_search(job_id=1)
        id2 = await create_search(job_id=1)
        assert id1 != id2


class TestLoadSearch:
    async def test_loads_existing_search(self, test_db):
        from src.agents.linkedin_db import create_search, load_search

        search_id = await create_search(job_id=1)
        search = await load_search(search_id)
        assert search["id"] == search_id
        assert search["job_id"] == 1
        assert search["status"] == "running"

    async def test_raises_for_missing_search(self, test_db):
        from src.agents.linkedin_db import load_search

        with pytest.raises(ValueError, match="99999"):
            await load_search(99999)


class TestUpdateSearchStatus:
    async def test_update_to_completed_sets_completed_at(self, test_db):
        from src.agents.linkedin_db import create_search, update_search_status, load_search

        search_id = await create_search(job_id=1)
        await update_search_status(search_id, "completed")
        search = await load_search(search_id)
        assert search["status"] == "completed"
        assert search["completed_at"] is not None

    async def test_update_to_failed_sets_completed_at(self, test_db):
        from src.agents.linkedin_db import create_search, update_search_status, load_search

        search_id = await create_search(job_id=1)
        await update_search_status(search_id, "failed")
        search = await load_search(search_id)
        assert search["status"] == "failed"
        assert search["completed_at"] is not None

    async def test_update_to_other_status_no_completed_at(self, test_db):
        from src.agents.linkedin_db import create_search, update_search_status, load_search

        search_id = await create_search(job_id=1)
        await update_search_status(search_id, "pending")
        search = await load_search(search_id)
        assert search["status"] == "pending"
        assert search["completed_at"] is None


class TestSaveCompanyData:
    async def test_updates_company_fields(self, test_db):
        from src.agents.linkedin_db import create_search, save_company_data, load_search

        search_id = await create_search(job_id=1)
        await save_company_data(
            search_id=search_id,
            domain="acme.com",
            data_json='{"employees": 500}',
            summary="Acme is a mid-sized company.",
        )
        search = await load_search(search_id)
        assert search["company_domain"] == "acme.com"
        assert search["company_data_json"] == '{"employees": 500}'
        assert search["company_summary"] == "Acme is a mid-sized company."


class TestSaveAndLoadContacts:
    def _make_contact(self, name="Alice", title="Engineer", score=80):
        return {
            "name": name,
            "title": title,
            "location": "San Francisco, CA",
            "linkedin_url": f"https://linkedin.com/in/{name.lower()}",
            "source_query": "site:linkedin.com Acme engineer",
            "relevance_score": score,
            "low_confidence": 0,
            "connection_note": "Works on relevant team.",
        }

    async def test_save_and_load_contacts(self, test_db):
        from src.agents.linkedin_db import create_search, save_contacts, load_contacts

        search_id = await create_search(job_id=1)
        contacts = [
            self._make_contact("Alice", score=70),
            self._make_contact("Bob", score=90),
        ]
        await save_contacts(search_id, contacts)

        loaded = await load_contacts(search_id)
        assert len(loaded) == 2

    async def test_load_contacts_sorted_by_score_desc(self, test_db):
        from src.agents.linkedin_db import create_search, save_contacts, load_contacts

        search_id = await create_search(job_id=1)
        contacts = [
            self._make_contact("Alice", score=70),
            self._make_contact("Bob", score=90),
            self._make_contact("Carol", score=50),
        ]
        await save_contacts(search_id, contacts)

        loaded = await load_contacts(search_id)
        scores = [c["relevance_score"] for c in loaded]
        assert scores == sorted(scores, reverse=True)
        assert scores[0] == 90

    async def test_load_contacts_returns_empty_list(self, test_db):
        from src.agents.linkedin_db import create_search, load_contacts

        search_id = await create_search(job_id=1)
        assert await load_contacts(search_id) == []

    async def test_save_contacts_bulk(self, test_db):
        from src.agents.linkedin_db import create_search, save_contacts, load_contacts

        search_id = await create_search(job_id=1)
        contacts = [self._make_contact(f"Person{i}", score=i * 10) for i in range(1, 6)]
        await save_contacts(search_id, contacts)

        loaded = await load_contacts(search_id)
        assert len(loaded) == 5

    async def test_low_confidence_persisted(self, test_db):
        from src.agents.linkedin_db import create_search, save_contacts, load_contacts

        search_id = await create_search(job_id=1)
        contact = self._make_contact("Dave", score=60)
        contact["low_confidence"] = 1
        await save_contacts(search_id, [contact])

        loaded = await load_contacts(search_id)
        assert loaded[0]["low_confidence"] == 1


class TestDeleteSearch:
    async def test_deletes_search_and_contacts(self, test_db):
        from src.agents.linkedin_db import create_search, save_contacts, delete_search

        search_id = await create_search(job_id=1)
        await save_contacts(search_id, [
            {
                "name": "Alice",
                "title": "SWE",
                "location": "NYC",
                "linkedin_url": "https://linkedin.com/in/alice",
                "source_query": "acme engineer",
                "relevance_score": 80,
                "low_confidence": 0,
                "connection_note": "Relevant.",
            }
        ])
        await delete_search(search_id)

        conn = sqlite3.connect(test_db)
        conn.row_factory = sqlite3.Row
        assert conn.execute(
            "SELECT COUNT(*) FROM linkedin_searches WHERE id = ?", (search_id,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM linkedin_contacts WHERE search_id = ?", (search_id,)
        ).fetchone()[0] == 0
        conn.close()

    async def test_noop_on_nonexistent(self, test_db):
        from src.agents.linkedin_db import delete_search

        await delete_search(99999)  # Should not raise


class TestLoadLatestSearchForJob:
    async def test_returns_most_recent(self, test_db):
        from src.agents.linkedin_db import create_search, load_latest_search_for_job

        id1 = await create_search(job_id=1)
        id2 = await create_search(job_id=1)
        latest = await load_latest_search_for_job(job_id=1)
        assert latest is not None
        assert latest["id"] == id2

    async def test_returns_none_when_no_searches(self, test_db):
        from src.agents.linkedin_db import load_latest_search_for_job

        result = await load_latest_search_for_job(job_id=999)
        assert result is None

    async def test_isolates_by_job_id(self, test_db):
        """Should not return a search for a different job."""
        conn = sqlite3.connect(test_db)
        conn.execute("INSERT INTO jobs (id, title, company, description) VALUES (2, 'PM', 'OtherCo', 'Manage')")
        conn.commit()
        conn.close()

        from src.agents.linkedin_db import create_search, load_latest_search_for_job

        await create_search(job_id=2)
        result = await load_latest_search_for_job(job_id=1)
        assert result is None


class TestEnsureLinkedinTables:
    def test_creates_tables_idempotent(self, tmp_path):
        import sqlite3 as _sqlite3
        db_path = str(tmp_path / "fresh.db")
        from src.agents.linkedin_db import ensure_linkedin_tables

        # Call twice — should not raise
        ensure_linkedin_tables(db_path)
        ensure_linkedin_tables(db_path)

        conn = _sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        conn.close()
        assert "linkedin_searches" in tables
        assert "linkedin_contacts" in tables

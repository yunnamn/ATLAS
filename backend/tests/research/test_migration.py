import json
import os
import sqlite3
import subprocess
from pathlib import Path

from atlas.config import Settings
from atlas.research.manager import ResearchManager
from atlas.research.models import ResearchReport, ResearchRun
from tests.research.helpers import make_run


def test_task2_upgrade_preserves_all_task1_records(tmp_path, record) -> None:
    path = tmp_path / "prior-version.db"
    environment = {**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{path}"}
    command = [str(Path(".venv/bin/alembic").resolve()), "upgrade"]
    subprocess.run([*command, "0001"], env=environment, check=True, capture_output=True)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO opportunities VALUES (1, ?, ?, ?, ?, ?, 1, ?, ?)",
            (
                record["external_id"],
                record["title"],
                record["country"],
                record["category"],
                json.dumps(record),
                "2026-10-23",
                "2026-10-23",
            ),
        )
        db.execute(
            "INSERT INTO applications VALUES (1, 1, 'preparing', 'preserve notes', "
            "'[\"IELTS\"]', '2026-10-23')"
        )
        before = db.execute("SELECT * FROM opportunities").fetchall()
        apps = db.execute("SELECT * FROM applications").fetchall()
    subprocess.run([*command, "head"], env=environment, check=True, capture_output=True)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM opportunities").fetchall() == before
        assert db.execute("SELECT * FROM applications").fetchall() == apps
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0003"
        assert db.execute("SELECT count(*) FROM research_runs").fetchone()[0] == 0


def test_interrupted_runs_are_preserved_as_failed_without_replaying_model_costs(sessions) -> None:
    run_id = make_run(sessions)
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        run.status = "running"
        s.commit()
    manager = ResearchManager(sessions.kw["bind"], Settings())
    manager.start()
    with sessions() as s:
        run = s.get(ResearchRun, run_id)
        assert run.status == "failed" and run.stop_reason == "interrupted"
        assert s.get(ResearchReport, run_id).content["outcome"] == "partial"
        assert run.stats.get("provider_requests", 0) == 0
    manager.close()


def test_task3_additive_migration_keeps_existing_runs_and_original_bytes(tmp_path) -> None:
    path = tmp_path / "task2.db"
    environment = {**os.environ, "ATLAS_DATABASE_URL": f"sqlite:///{path}"}
    alembic = str(Path(".venv/bin/alembic").resolve())
    subprocess.run([alembic, "upgrade", "0002"], env=environment, check=True, capture_output=True)
    with sqlite3.connect(path) as db:
        db.execute(
            "INSERT INTO research_runs (id, objective, mode, status, request, state, stats, "
            "cancel_requested, created_at, updated_at) "
            "VALUES ('prior', 'Preserve this research', 'demo', 'completed', '{}', '{}', '{}', "
            "0, '2026-10-23', '2026-10-23')"
        )
        db.execute(
            "INSERT INTO research_documents (id, url, title, media_type, sha256, text, "
            "raw_content, "
            "locations, links, synthetic, fetched_at, last_checked_at) "
            "VALUES ('doc', 'https://example.edu', 'Prior source', 'text/html', "
            "?, 'Original text', "
            "?, '[]', '[]', 0, '2026-10-23', '2026-10-23')",
            ("a" * 64, b"<html>Original bytes</html>"),
        )
        db.execute(
            "INSERT INTO research_claims (id, run_id, document_id, field, value, scope, "
            "proposed_quote, "
            "proposed_scope_quote, state, verification_note) "
            "VALUES ('claim', 'prior', 'doc', 'program', 'Original', '{}', 'Original text', "
            "'Original text', 'unverified', 'Prior assessment')"
        )
        before = {
            t: db.execute(f"SELECT * FROM {t}").fetchall()
            for t in (
                "research_runs",
                "research_documents",
                "research_claims",
            )
        }
    subprocess.run([alembic, "upgrade", "head"], env=environment, check=True, capture_output=True)
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT * FROM research_runs").fetchall() == before["research_runs"]
        assert (
            db.execute("SELECT * FROM research_documents").fetchall()
            == before["research_documents"]
        )
        claims = db.execute("SELECT * FROM research_claims").fetchall()
        assert [row[:-1] for row in claims] == before["research_claims"]
        assert json.loads(claims[0][-1]) == {}  # Legacy evidence is not falsely re-verified.
        assert db.execute("SELECT count(*) FROM research_proposals").fetchone()[0] == 0

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
        assert db.execute("SELECT version_num FROM alembic_version").fetchone()[0] == "0002"
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

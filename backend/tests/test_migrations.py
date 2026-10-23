import os
import subprocess
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import Session

from atlas.db import Opportunity
from atlas.schemas import ImportBatch
from atlas.services.storage import import_records


def test_fresh_migration_persistence_and_upgrade_repeatability(
    tmp_path: Path, batch: ImportBatch
) -> None:
    database_url = f"sqlite:///{tmp_path / 'test.db'}"
    environment = {**os.environ, "ATLAS_DATABASE_URL": database_url}
    command = [str(Path(".venv/bin/alembic").resolve()), "upgrade", "head"]
    subprocess.run(command, env=environment, check=True, capture_output=True)
    engine = create_engine(database_url)
    assert set(inspect(engine).get_table_names()) >= {
        "opportunities",
        "changes",
        "applications",
        "profiles",
        "alembic_version",
    }
    with Session(engine) as session:
        assert len(import_records(session, batch.opportunities)["created"]) == 6
    engine.dispose()
    subprocess.run(command, env=environment, check=True, capture_output=True)
    reopened = create_engine(database_url)
    with Session(reopened) as session:
        assert len(list(session.scalars(select(Opportunity)))) == 6
        assert len(import_records(session, batch.opportunities)["skipped"]) == 6
    reopened.dispose()
    subprocess.run(
        [command[0], "downgrade", "base"], env=environment, check=True, capture_output=True
    )
    subprocess.run(command, env=environment, check=True, capture_output=True)

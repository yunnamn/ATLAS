from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from atlas.db import Base, get_session
from atlas.main import app
from atlas.schemas import ImportBatch


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'api.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(engine)

    def override() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override
    app.state.database_engine = engine
    with TestClient(app) as test_client:
        yield test_client
    del app.state.database_engine
    app.dependency_overrides.clear()
    engine.dispose()


@pytest.fixture
def record() -> dict:
    import json

    return deepcopy(json.loads(Path("atlas/demo.json").read_text())["opportunities"][0])


@pytest.fixture
def batch() -> ImportBatch:
    return ImportBatch.model_validate_json(Path("atlas/demo.json").read_text())

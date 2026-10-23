"""Run after migrations: python -m atlas.seed."""

import json
from pathlib import Path

from sqlalchemy.orm import Session

from atlas.db import engine
from atlas.schemas import ImportBatch
from atlas.services.storage import import_records

if __name__ == "__main__":
    data = ImportBatch.model_validate_json(Path(__file__).with_name("demo.json").read_text())
    with Session(engine) as session:
        print(json.dumps(import_records(session, data.opportunities)))

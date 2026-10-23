from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from atlas.db import Application, Change, Opportunity, utc_iso, utcnow
from atlas.schemas import OpportunityInput


def serialize(row: Opportunity) -> dict[str, Any]:
    return {
        **row.payload,
        "id": row.id,
        "revision": row.revision,
        "created_at": utc_iso(row.created_at),
        "updated_at": utc_iso(row.updated_at),
    }


def application_dict(row: Application) -> dict[str, Any]:
    return {
        "id": row.id,
        "opportunity_id": row.opportunity_id,
        "status": row.status,
        "notes": row.notes,
        "missing_requirements": row.missing_requirements,
        "updated_at": utc_iso(row.updated_at),
    }


def insert(session: Session, data: OpportunityInput) -> Opportunity:
    row = Opportunity(
        external_id=data.external_id,
        title=data.title,
        country=data.country,
        category=data.category,
        payload=data.model_dump(mode="json"),
    )
    session.add(row)
    session.flush()
    session.add(
        Change(
            opportunity_id=row.id,
            revision=1,
            actor="import",
            reason="Record created",
            before=None,
            after=row.payload,
        )
    )
    return row


def import_records(session: Session, records: list[OpportunityInput]) -> dict[str, Any]:
    """Idempotent insert-only import: never overwrite human corrections."""
    created, skipped = [], []
    for record in records:
        existing = session.scalar(
            select(Opportunity).where(Opportunity.external_id == record.external_id)
        )
        if existing:
            skipped.append(existing.id)
        else:
            created.append(insert(session, record).id)
    session.commit()
    return {"created": created, "skipped": skipped}


def update_fact(
    session: Session, row: Opportunity, payload: dict[str, Any], actor: str, reason: str
) -> None:
    before = row.payload
    row.payload = payload
    row.revision += 1
    row.updated_at = utcnow()
    session.add(
        Change(
            opportunity_id=row.id,
            revision=row.revision,
            actor=actor,
            reason=reason,
            before=before,
            after=payload,
        )
    )
    session.commit()

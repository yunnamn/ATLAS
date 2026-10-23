import json
import subprocess
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from atlas.config import settings
from atlas.db import Application, Change, Opportunity, Profile, engine, get_session, utc_iso, utcnow
from atlas.research.api import router as research_router
from atlas.research.manager import ResearchManager, capabilities
from atlas.schemas import (
    FACT_LABELS,
    ApplicationInput,
    FactKey,
    FactReview,
    ImportBatch,
    OpportunityInput,
    Source,
    UserProfile,
)
from atlas.services.extraction import DeterministicExtractor, document_source
from atlas.services.matching import evaluate
from atlas.services.storage import application_dict, import_records, insert, serialize, update_fact


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    manager = ResearchManager(getattr(application.state, "database_engine", engine), settings)
    manager.start()
    application.state.research_manager = manager
    try:
        yield
    finally:
        manager.close()


app = FastAPI(
    title="ATLAS",
    version="0.2.0",
    description="Local opportunity research workspace",
    lifespan=lifespan,
)
app.include_router(research_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
DB = Annotated[Session, Depends(get_session)]


def get_op(session: Session, opportunity_id: int) -> Opportunity:
    row = session.get(Opportunity, opportunity_id)
    if row is None:
        raise HTTPException(404, "Opportunity not found")
    return row


@app.get("/api/health")
def health(session: DB) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    # Table access ensures migrations actually ran.
    session.execute(select(Opportunity.id).limit(1))
    return {
        "status": "ok",
        "mode": "local-single-user",
        "llm": "configured" if capabilities(settings)["live_ready"] else "disabled",
    }


@app.get("/api/metadata")
def metadata() -> dict[str, Any]:
    return {
        "fact_labels": FACT_LABELS,
        "funding_options": ["tuition_and_stipend", "tuition_only", "partial", "none"],
    }


@app.get("/api/opportunities")
def opportunities(
    session: DB,
    q: str = Query(default="", max_length=200),
    country: str = "",
    funding: str = "",
    category: str = "",
    review: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    statement = select(Opportunity).order_by(Opportunity.id)
    if country:
        statement = statement.where(Opportunity.country == country)
    if category:
        statement = statement.where(Opportunity.category == category)
    rows = list(session.scalars(statement))
    if q:
        needle = q.casefold().strip()
        rows = [
            r
            for r in rows
            if needle
            in " ".join(
                [
                    r.title,
                    r.payload["institution"],
                    r.country,
                    r.payload["summary"],
                    *r.payload["subjects"],
                ]
            ).casefold()
        ]
    if funding:
        rows = [r for r in rows if r.payload["facts"]["funding"]["value"] == funding]
    if review:
        rows = [
            r for r in rows if any(f["state"] != "verified" for f in r.payload["facts"].values())
        ]
    all_rows = list(session.scalars(select(Opportunity)))
    return {
        "items": [serialize(r) for r in rows[offset : offset + limit]],
        "total": len(rows),
        "countries": sorted({r.country for r in all_rows}),
        "total_all": len(all_rows),
    }


@app.get("/api/opportunities/{opportunity_id}")
def opportunity(opportunity_id: int, session: DB) -> dict[str, Any]:
    return serialize(get_op(session, opportunity_id))


@app.post("/api/opportunities", status_code=201)
def create_opportunity(data: OpportunityInput, session: DB) -> dict[str, Any]:
    try:
        row = insert(session, data)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(409, "external_id already exists") from exc
    return serialize(row)


@app.post("/api/imports")
def import_batch(data: ImportBatch, session: DB) -> dict[str, Any]:
    try:
        return import_records(session, data.opportunities)
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(
            409, "An import with this external ID was saved concurrently; retry"
        ) from exc


@app.post("/api/imports/demo")
def import_demo(session: DB) -> dict[str, Any]:
    data = ImportBatch.model_validate_json(Path(__file__).with_name("demo.json").read_text())
    return import_batch(data, session)


@app.get("/api/demo-records")
def demo_records() -> Any:
    return json.loads(Path(__file__).with_name("demo.json").read_text())


@app.put("/api/opportunities/{opportunity_id}/facts/{key}")
def review_fact(opportunity_id: int, key: FactKey, data: FactReview, session: DB) -> dict[str, Any]:
    row = get_op(session, opportunity_id)
    if row.revision != data.expected_revision:
        raise HTTPException(409, "Record changed. Reload before reviewing.")
    payload = {**row.payload, "facts": {**row.payload["facts"], key: data.fact.model_dump()}}
    try:
        validated = OpportunityInput.model_validate(payload)
    except ValidationError as exc:
        raise HTTPException(422, str(exc)) from exc
    try:
        update_fact(session, row, validated.model_dump(mode="json"), data.actor, data.reason)
    except StaleDataError as exc:
        session.rollback()
        raise HTTPException(409, "Record changed. Reload before reviewing.") from exc
    return serialize(row)


@app.get("/api/opportunities/{opportunity_id}/history")
def history(opportunity_id: int, session: DB) -> list[dict[str, Any]]:
    get_op(session, opportunity_id)
    return [
        {
            "id": h.id,
            "revision": h.revision,
            "actor": h.actor,
            "reason": h.reason,
            "before": h.before,
            "after": h.after,
            "created_at": utc_iso(h.created_at),
        }
        for h in session.scalars(
            select(Change)
            .where(Change.opportunity_id == opportunity_id)
            .order_by(Change.revision.desc())
        )
    ]


def current_profile(session: Session) -> UserProfile:
    row = session.get(Profile, 1)
    return UserProfile.model_validate(row.payload) if row else UserProfile()


@app.get("/api/profile")
def get_profile(session: DB) -> UserProfile:
    return current_profile(session)


@app.put("/api/profile")
def save_profile(data: UserProfile, session: DB) -> UserProfile:
    row = session.get(Profile, 1)
    if row:
        row.payload = data.model_dump(mode="json")
    else:
        session.add(Profile(id=1, payload=data.model_dump(mode="json")))
    session.commit()
    return data


@app.get("/api/opportunities/{opportunity_id}/match")
def match(opportunity_id: int, session: DB) -> dict[str, Any]:
    row = get_op(session, opportunity_id)
    return evaluate(OpportunityInput.model_validate(row.payload), current_profile(session))


@app.get("/api/applications")
def applications(session: DB) -> list[dict[str, Any]]:
    return [
        {**application_dict(a), "opportunity": serialize(o)}
        for a, o in session.execute(
            select(Application, Opportunity)
            .join(Opportunity, Application.opportunity_id == Opportunity.id)
            .order_by(Application.updated_at.desc())
        )
    ]


@app.put("/api/applications/{opportunity_id}")
def save_application(opportunity_id: int, data: ApplicationInput, session: DB) -> dict[str, Any]:
    get_op(session, opportunity_id)
    row = session.scalar(select(Application).where(Application.opportunity_id == opportunity_id))
    if row:
        row.status, row.notes = data.status, data.notes
        row.missing_requirements, row.updated_at = data.missing_requirements, utcnow()
    else:
        row = Application(opportunity_id=opportunity_id, **data.model_dump())
        session.add(row)
    session.commit()
    return application_dict(row)


@app.delete("/api/applications/{opportunity_id}", status_code=204)
def remove_application(opportunity_id: int, session: DB) -> None:
    row = session.scalar(select(Application).where(Application.opportunity_id == opportunity_id))
    if row:
        session.delete(row)
        session.commit()


class TextDocument(BaseModel):
    text: str = Field(min_length=1, max_length=100_000)
    label: str = Field(min_length=1, max_length=200)


@app.post("/api/extract/text")
def extract_text(data: TextDocument) -> dict[str, Any]:
    source = document_source(data.text.encode(), data.label, "manual")
    facts = DeterministicExtractor().extract(data.text, "document")
    # Validate individual numeric/date candidates through the same import schema.
    valid = {}
    for key, fact in facts.items():
        try:
            OpportunityInput(
                external_id="candidate",
                title="Candidate",
                institution="Unknown",
                country="Unknown",
                summary="Unreviewed extraction candidate",
                sources=[Source.model_validate(source)],
                facts={FactKey(key): fact},
            )
            valid[key] = fact.model_dump()
        except ValidationError:
            pass
    return {
        "source": source,
        "facts": valid,
        "characters": len(data.text),
        "warning": "Candidates only. Review original evidence before importing. "
        "Only exact labeled fields are recognized; other information stays unknown.",
    }


@app.post("/api/extract/pdf")
def extract_pdf(file: Annotated[UploadFile, File()]) -> dict[str, Any]:
    content = file.file.read(8 * 1024 * 1024 + 1)
    if len(content) > 8 * 1024 * 1024:
        raise HTTPException(413, "Maximum PDF size is 8 MiB")
    if not content.startswith(b"%PDF-"):
        raise HTTPException(422, "Upload a PDF document")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "atlas.services.pdf_worker"],
            input=content,
            capture_output=True,
            timeout=12,
            check=True,
        )
        parsed = json.loads(result.stdout)
    except (subprocess.SubprocessError, ValueError) as exc:
        raise HTTPException(
            422,
            "Could not safely read this PDF. Use an unencrypted, text-based "
            "PDF of at most 30 pages, or paste its text.",
        ) from exc
    if not parsed["text"].strip():
        raise HTTPException(422, "No text found. Scanned PDFs require OCR, which is not included.")
    label = (file.filename or "Uploaded PDF").strip()[:200] or "Uploaded PDF"
    extracted = extract_text(TextDocument(text=parsed["text"], label=label))
    extracted["source"] = document_source(content, label)
    extracted["pages"] = parsed["pages"]
    return extracted

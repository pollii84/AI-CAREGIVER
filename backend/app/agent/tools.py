"""Care Agent tool set — Architecture doc §4.

Every tool is scoped to the requesting patient's own data at the
implementation layer (not by trusting model input) — Architecture doc §4:
"No tool returns another patient's data — enforced at the tool-implementation
layer, not just by prompting." Each function below takes `patient_id` from
the authenticated session, never from the model's tool-call input.

NOTE: DB calls here use the sync SQLAlchemy session inside async tool
dispatch (pipeline.py is async for Mongo/Anthropic I/O). Acceptable for this
scaffold; production should move to an async SQLAlchemy engine or run these
via `run_in_executor` so a slow query can't block the event loop.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Checkin, CorpusSource, Medication, Patient

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_patient_record",
        "description": (
            "Get the requesting patient's own profile and active medications. "
            "Always scoped to the current patient — never accepts a patient ID."
        ),
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "strict": True,
    },
    {
        "name": "search_corpus",
        "description": (
            "Search the curated medical corpus (clinical guidelines, PubMed abstracts) "
            "scoped to the patient's disease profile. Call this before making any factual "
            "or research claim — never answer from unaided knowledge."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Search query"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "search_trials",
        "description": "Search ClinicalTrials.gov for trials matching the patient's disease and stage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "condition": {"type": "string", "description": "Disease/condition, e.g. 'Parkinson Disease'"},
            },
            "required": ["condition"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "name": "get_checkin_history",
        "description": "Get the requesting patient's own check-in history (structured and mood-row) for a date range.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_back": {"type": "integer", "description": "How many days of history to retrieve", "default": 7},
            },
            "required": ["days_back"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]


def get_patient_record(db: Session, patient_id: UUID, _input: dict) -> dict:
    patient = db.get(Patient, patient_id)
    if patient is None:
        return {"error": "patient not found"}
    meds = db.scalars(
        select(Medication).where(Medication.patient_id == patient_id, Medication.active.is_(True))
    ).all()
    return {
        "preferred_comm_mode": patient.preferred_comm_mode,
        "disease_profile_id": str(patient.disease_profile_id),
        "medications": [{"name": m.name, "dosage": m.dosage, "schedule_rrule": m.schedule_rrule} for m in meds],
    }


def search_corpus(db: Session, patient_id: UUID, tool_input: dict) -> dict:
    """Stub full-text search over `corpus_sources` metadata. Real semantic
    retrieval depends on Architecture doc §8's vector DB decision (pgvector
    vs. Pinecone) — this ILIKE search is a placeholder that returns the same
    citation shape the agent contract expects, so the pipeline/schema don't
    need to change once real retrieval lands.
    """
    query = tool_input.get("query", "")
    patient = db.get(Patient, patient_id)
    sources = db.scalars(
        select(CorpusSource)
        .where(CorpusSource.disease_profile_id == patient.disease_profile_id)
        .where(CorpusSource.title.ilike(f"%{query}%"))
        .limit(5)
    ).all()
    return {
        "results": [
            {
                "source_id": str(s.id),
                "title": s.title,
                "clinician_reviewed": s.clinician_reviewed,
                "url": s.url,
            }
            for s in sources
        ]
    }


def search_trials(_db: Session, _patient_id: UUID, tool_input: dict) -> dict:
    """ClinicalTrials.gov API v2 — Architecture doc Integration Points."""
    condition = tool_input.get("condition", "")
    try:
        resp = httpx.get(
            "https://clinicaltrials.gov/api/v2/studies",
            params={"query.cond": condition, "pageSize": 5},
            timeout=10.0,
        )
        resp.raise_for_status()
        studies = resp.json().get("studies", [])
    except httpx.HTTPError:
        return {"results": [], "error": "clinicaltrials.gov lookup failed"}

    return {
        "results": [
            {
                "source_id": s.get("protocolSection", {}).get("identificationModule", {}).get("nctId", ""),
                "title": s.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", ""),
                "status": s.get("protocolSection", {}).get("statusModule", {}).get("overallStatus", ""),
            }
            for s in studies
        ]
    }


def get_checkin_history(db: Session, patient_id: UUID, tool_input: dict) -> dict:
    days_back = tool_input.get("days_back", 7)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    checkins = db.scalars(
        select(Checkin)
        .where(Checkin.patient_id == patient_id, Checkin.recorded_at >= cutoff)
        .order_by(Checkin.recorded_at.desc())
    ).all()
    return {
        "checkins": [
            {
                "type": c.checkin_type,
                "answers": c.answers,
                "computed_score": float(c.computed_score) if c.computed_score is not None else None,
                "recorded_at": c.recorded_at.isoformat(),
            }
            for c in checkins
        ]
    }


TOOL_IMPLEMENTATIONS = {
    "get_patient_record": get_patient_record,
    "search_corpus": search_corpus,
    "search_trials": search_trials,
    "get_checkin_history": get_checkin_history,
}

from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ScopedIdentity, require_patient_scope, require_patient_write_scope
from app.db.base import get_db
from app.db.models import Medication

router = APIRouter(prefix="/patients/{patient_id}/medications", tags=["medications"])


class MedicationCreate(BaseModel):
    name: str
    dosage: str
    schedule_rrule: str  # e.g. "FREQ=DAILY;BYHOUR=8,16" — Database doc §2.3


class MedicationOut(BaseModel):
    id: UUID
    name: str
    dosage: str
    schedule_rrule: str
    active: bool

    class Config:
        from_attributes = True


@router.post("", response_model=MedicationOut, status_code=201)
def add_medication(
    patient_id: UUID,
    payload: MedicationCreate,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_write_scope),
):
    med = Medication(patient_id=patient_id, **payload.model_dump())
    db.add(med)
    db.commit()
    db.refresh(med)
    return med


@router.get("", response_model=list[MedicationOut])
def list_medications(
    patient_id: UUID,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_scope),
):
    return db.scalars(
        select(Medication).where(Medication.patient_id == patient_id, Medication.active.is_(True))
    ).all()

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ScopedIdentity, require_patient_scope, require_patient_write_scope
from app.db.base import get_db
from app.db.models import Checkin

router = APIRouter(prefix="/patients/{patient_id}/checkins", tags=["checkins"])


class CheckinCreate(BaseModel):
    checkin_type: str  # 'structured' | 'mood_row' — Product/UX doc §3.1a / §5
    answers: dict
    computed_score: Optional[float] = None
    input_mode: str  # 'text' | 'voice'


class CheckinOut(BaseModel):
    id: UUID
    checkin_type: str
    answers: dict
    computed_score: Optional[float]
    input_mode: str
    recorded_at: datetime

    class Config:
        from_attributes = True


@router.post("", response_model=CheckinOut, status_code=201)
def submit_checkin(
    patient_id: UUID,
    payload: CheckinCreate,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_write_scope),
):
    # TODO: UPDRS/CDR/EDSS score computation from `answers` per
    # disease_profiles.rating_scale_config — stubbed as pass-through for now;
    # `computed_score` is caller-supplied until that scoring logic is written.
    checkin = Checkin(patient_id=patient_id, **payload.model_dump())
    db.add(checkin)
    db.commit()
    db.refresh(checkin)
    return checkin


@router.get("", response_model=list[CheckinOut])
def list_checkins(
    patient_id: UUID,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_scope),
):
    return db.scalars(
        select(Checkin).where(Checkin.patient_id == patient_id).order_by(Checkin.recorded_at.desc()).limit(100)
    ).all()

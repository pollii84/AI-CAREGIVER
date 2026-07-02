from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.db.models import DiseaseProfile, Patient

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientCreate(BaseModel):
    disease_code: str = "parkinsons"
    preferred_comm_mode: str = "both"


class PatientOut(BaseModel):
    id: UUID
    disease_profile_id: UUID
    preferred_comm_mode: str

    class Config:
        from_attributes = True


@router.post("", response_model=PatientOut, status_code=201)
def create_patient(payload: PatientCreate, db: Session = Depends(get_db)):
    """Onboarding, PRD Functional Requirements §Patient Experience.

    NOTE: identity/auth (name, DOB, login) is out of scope here — lives in
    the OAuth2/JWT layer per Architecture doc §3 and Database doc §2.1's
    explicit "not duplicated here" note. This endpoint only creates the
    app-side patient row.
    """
    profile = db.query(DiseaseProfile).filter_by(disease_code=payload.disease_code, active=True).first()
    if profile is None:
        raise HTTPException(404, f"No active disease profile for '{payload.disease_code}'")

    patient = Patient(disease_profile_id=profile.id, preferred_comm_mode=payload.preferred_comm_mode)
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(patient_id: UUID, db: Session = Depends(get_db)):
    # TODO(auth): once the OAuth2/JWT layer exists, enforce Database doc §8 —
    # a patient session may only read patient_id == self; a caregiver session
    # only patient_ids with an active patient_caregiver_links row.
    patient = db.get(Patient, patient_id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(404, "Patient not found")
    return patient

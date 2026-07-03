from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import ScopedIdentity, require_patient_scope
from app.db.base import get_db
from app.db.models import Patient

router = APIRouter(prefix="/patients", tags=["patients"])


class PatientOut(BaseModel):
    id: UUID
    disease_profile_id: UUID
    preferred_comm_mode: str

    class Config:
        from_attributes = True


# NOTE: the old unauthenticated `POST /patients` onboarding route is gone —
# AUTH_LAYER.md §6.1 folds its logic (disease-profile lookup, row creation)
# into `POST /api/v1/auth/register/patient`'s transaction (app/api/v1/auth.py),
# which also creates the credentials row in the same commit. There is no
# internal-only remnant kept here; register/patient is the only entry point
# now, per §9 step 6 ("should not remain reachable unauthenticated at its
# current path").


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: UUID,
    db: Session = Depends(get_db),
    _scope: ScopedIdentity = Depends(require_patient_scope),
):
    patient = db.get(Patient, patient_id)
    if patient is None or patient.deleted_at is not None:
        raise HTTPException(404, "Patient not found")
    return patient

"""Auth dependencies — AUTH_LAYER.md §3.3, §4.1, §5.1, §9 step 4.

Fits alongside the existing `Depends(get_db)` style in app/db/base.py.
Verification only (public-key side); token issuance lives in app/auth/.

Dependency chain, cheapest to most restrictive:

    get_current_identity      -- valid bearer token -> who is calling, full stop.
    require_patient_scope     -- + "may this caller read this path's patient_id"
                                  (patient-self OR active caregiver link).
    require_patient_write_scope -- + "and it must be the patient, not a caregiver"
                                  (Database doc §8: caregiver sessions never write
                                  clinical data).
    require_patient_self      -- patient-actor-only, no caregiver-link exception
                                  at all. Used by the Care Agent routes (§5.1) —
                                  a caregiver link is never sufficient here,
                                  regardless of role, because conversation
                                  transcripts are patient-private (Database doc §8).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.keys import get_public_key
from app.auth.tokens import ALGORITHM
from app.db.base import get_db
from app.db.models import PatientCaregiverLink

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Identity:
    actor_id: UUID  # == patients.id or caregivers.id, per actor_type
    actor_type: str  # "patient" | "caregiver"
    session_id: UUID  # JWT "sid" claim


@dataclass(frozen=True)
class ScopedIdentity:
    patient_id: UUID
    actor_type: str  # "patient" | "caregiver"
    actor_id: UUID
    link_role: Optional[str]  # "family" | "clinician" | None (None when actor_type == "patient")


def get_current_identity(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Identity:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        payload = jwt.decode(
            credentials.credentials,
            get_public_key(),
            algorithms=[ALGORITHM],
        )
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")

    if payload.get("token_type") != "access":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not an access token")

    try:
        return Identity(
            actor_id=UUID(payload["sub"]),
            actor_type=payload["actor_type"],
            session_id=UUID(payload["sid"]),
        )
    except (KeyError, ValueError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed token claims")


def require_patient_scope(
    patient_id: UUID,
    identity: Identity = Depends(get_current_identity),
    db: Session = Depends(get_db),
) -> ScopedIdentity:
    """AUTH_LAYER.md §4.1 — the generic "caller may access this patient_id"
    check: patient-self, or an active `patient_caregiver_links` row. This is
    a live DB lookup on every caregiver request (§1 decision summary) —
    deliberately not a patient-ID list embedded in the JWT, so a revoked link
    takes effect on the caregiver's next request, not at their next login.
    """
    if identity.actor_type == "patient":
        if identity.actor_id != patient_id:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this patient")
        return ScopedIdentity(patient_id=patient_id, actor_type="patient", actor_id=identity.actor_id, link_role=None)

    if identity.actor_type == "caregiver":
        link = db.scalar(
            select(PatientCaregiverLink).where(
                PatientCaregiverLink.caregiver_id == identity.actor_id,
                PatientCaregiverLink.patient_id == patient_id,
                PatientCaregiverLink.status == "active",
            )
        )
        if link is None:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No active link to this patient")
        return ScopedIdentity(
            patient_id=patient_id, actor_type="caregiver", actor_id=identity.actor_id, link_role=link.role
        )

    raise HTTPException(status.HTTP_403_FORBIDDEN, "Unknown actor type")


def require_patient_write_scope(
    scope: ScopedIdentity = Depends(require_patient_scope),
) -> ScopedIdentity:
    """AUTH_LAYER.md §4.1 last paragraph: `require_patient_scope` alone
    doesn't distinguish read vs. write — caregiver sessions never write
    clinical data (Database doc §8), so write routes (POST checkins,
    POST medications, ...) depend on this instead of the bare scope check.
    """
    if scope.actor_type != "patient":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Caregiver sessions cannot write clinical data")
    return scope


def require_patient_self(
    patient_id: UUID,
    identity: Identity = Depends(get_current_identity),
) -> UUID:
    """AUTH_LAYER.md §5.1 — Care Agent routes. Stricter than
    `require_patient_scope`: an active caregiver link is never sufficient
    here, however active, because Care Agent conversations are patient-private
    (Database doc §8) with no sharing feature in MVP.
    """
    if identity.actor_type != "patient" or identity.actor_id != patient_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Care Agent access is patient-only")
    return identity.actor_id  # == patient_id; verified value, see AUTH_LAYER.md §5.2

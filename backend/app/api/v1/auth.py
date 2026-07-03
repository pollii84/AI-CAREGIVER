"""Auth endpoints — AUTH_LAYER.md §6, §9 step 5.

Registration, login, refresh-token rotation, logout for both patient and
caregiver actors. Caregiver-invite endpoints live in
app/api/v1/caregiver_invites.py — this file is login/session lifecycle only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.auth.audit import write_audit_log
from app.auth.invites import accept_invite, lookup_pending_invite
from app.auth.passwords import hash_password, verify_password
from app.auth.session import issue_token_pair
from app.auth.tokens import hash_token
from app.db.base import get_db
from app.db.models import (
    Caregiver,
    CaregiverCredential,
    DiseaseProfile,
    Patient,
    PatientCredential,
    RefreshToken,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class PatientRegisterIn(BaseModel):
    email: str
    password: str
    disease_code: str = "parkinsons"
    preferred_comm_mode: str = "both"


class CaregiverRegisterIn(BaseModel):
    email: str
    password: str
    invite_token: Optional[str] = None  # AUTH_LAYER.md §6.2 branch 4a


class LoginIn(BaseModel):
    email: str
    password: str
    actor_type: Optional[str] = None  # "patient" | "caregiver" hint; tries both if omitted


class RefreshIn(BaseModel):
    refresh_token: str


class LogoutIn(BaseModel):
    refresh_token: str


class TokenPairOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    patient_id: Optional[UUID] = None
    caregiver_id: Optional[UUID] = None


@router.post("/register/patient", response_model=TokenPairOut, status_code=201)
def register_patient(payload: PatientRegisterIn, db: Session = Depends(get_db)):
    """AUTH_LAYER.md §6.1. Replaces the old standalone `POST /patients` as
    the onboarding entry point — see app/api/v1/patients.py for the note on
    why that route no longer exists unauthenticated.
    """
    email = payload.email.strip().lower()
    if db.scalar(select(PatientCredential).where(PatientCredential.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    profile = db.query(DiseaseProfile).filter_by(disease_code=payload.disease_code, active=True).first()
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No active disease profile for '{payload.disease_code}'")

    patient = Patient(disease_profile_id=profile.id, preferred_comm_mode=payload.preferred_comm_mode)
    db.add(patient)
    db.flush()  # populate patient.id (client-side default) for the credentials FK

    db.add(
        PatientCredential(
            patient_id=patient.id,
            email=email,
            password_hash=hash_password(payload.password),
            provider="local",
        )
    )
    write_audit_log(db, "patient", patient.id, "account_created", "patient", patient.id)

    tokens, _ = issue_token_pair(db, actor_id=patient.id, actor_type="patient")
    db.commit()
    return {**tokens, "patient_id": patient.id}


@router.post("/register/caregiver", response_model=TokenPairOut, status_code=201)
def register_caregiver(payload: CaregiverRegisterIn, db: Session = Depends(get_db)):
    """AUTH_LAYER.md §6.2 branch 4a. When `invite_token` is present, this one
    call performs the full step-5 accept transaction inline (credentials
    insert *and* link creation together) — there is no separate client call
    to /accept in this branch.
    """
    email = payload.email.strip().lower()
    if db.scalar(select(CaregiverCredential).where(CaregiverCredential.email == email)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    invite = None
    if payload.invite_token:
        invite = lookup_pending_invite(db, payload.invite_token)
        if invite is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired invite token")
        if invite.email.strip().lower() != email:
            # §6.2 step 5a: reject before creating any row, so a token can't
            # be redeemed under a different email than it was sent to.
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Registration email does not match the invited email")

    caregiver = Caregiver()
    db.add(caregiver)
    db.flush()

    db.add(
        CaregiverCredential(
            caregiver_id=caregiver.id,
            email=email,
            password_hash=hash_password(payload.password),
            provider="local",
        )
    )
    write_audit_log(db, "caregiver", caregiver.id, "account_created", "caregiver", caregiver.id)

    if invite is not None:
        link = accept_invite(db, invite, caregiver.id)
        write_audit_log(
            db,
            "caregiver",
            caregiver.id,
            "caregiver_link_accepted",
            "patient_caregiver_link",
            link.id,
            metadata={"invite_id": str(invite.id), "patient_id": str(invite.patient_id)},
        )

    tokens, _ = issue_token_pair(db, actor_id=caregiver.id, actor_type="caregiver")
    db.commit()
    return {**tokens, "caregiver_id": caregiver.id}


@router.post("/login", response_model=TokenPairOut)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    """AUTH_LAYER.md §6.1. Tries both credential tables unless `actor_type`
    narrows it — the two tables are queried independently since an email can
    (in principle) exist in both.
    """
    email = payload.email.strip().lower()
    candidates: list[tuple] = []
    if payload.actor_type in (None, "patient"):
        candidates.append(("patient", db.scalar(select(PatientCredential).where(PatientCredential.email == email))))
    if payload.actor_type in (None, "caregiver"):
        candidates.append(
            ("caregiver", db.scalar(select(CaregiverCredential).where(CaregiverCredential.email == email)))
        )

    for actor_type, cred in candidates:
        if cred is None or not cred.password_hash:
            continue
        if verify_password(payload.password, cred.password_hash):
            actor_id = cred.patient_id if actor_type == "patient" else cred.caregiver_id
            write_audit_log(db, actor_type, actor_id, "login_succeeded", actor_type, actor_id)
            tokens, _ = issue_token_pair(db, actor_id, actor_type)
            db.commit()
            result = dict(tokens)
            result[f"{actor_type}_id"] = actor_id
            return result

    # No successful match — log a failure against every credential row we did
    # find (bad password), or against no actor at all (no such account).
    found_any = False
    for actor_type, cred in candidates:
        if cred is not None:
            found_any = True
            actor_id = cred.patient_id if actor_type == "patient" else cred.caregiver_id
            write_audit_log(
                db, actor_type, actor_id, "login_failed", actor_type, actor_id, metadata={"reason": "bad_password"}
            )
    if not found_any:
        write_audit_log(db, "system", None, "login_failed", "auth", metadata={"email": email, "reason": "no_such_account"})
    db.commit()
    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")


@router.post("/refresh", response_model=TokenPairOut)
def refresh(payload: RefreshIn, db: Session = Depends(get_db)):
    """AUTH_LAYER.md §3.2: rotate on every use, detect reuse of an
    already-rotated token as theft and revoke the whole session chain.
    """
    token_hash = hash_token(payload.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    if row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token revoked")

    if row.replaced_by_id is not None:
        # This exact token was already consumed by a prior rotation — the
        # legitimate client has already moved past it, so this is a signal
        # of token theft. Revoke the whole session chain, not just this row.
        now = datetime.now(timezone.utc)
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.session_id == row.session_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        write_audit_log(
            db,
            row.actor_type,
            row.actor_id,
            "refresh_token_reuse_detected",
            "refresh_token",
            row.id,
            metadata={"session_id": str(row.session_id)},
        )
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token reuse detected — session revoked")

    if row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token expired")

    tokens, new_row = issue_token_pair(db, actor_id=row.actor_id, actor_type=row.actor_type, session_id=row.session_id)
    row.replaced_by_id = new_row.id
    write_audit_log(db, row.actor_type, row.actor_id, "token_refreshed", "refresh_token", new_row.id)
    db.commit()
    result = dict(tokens)
    result[f"{row.actor_type}_id"] = row.actor_id
    return result


@router.post("/logout", status_code=204)
def logout(payload: LogoutIn, db: Session = Depends(get_db)):
    """AUTH_LAYER.md §3.2: revokes the current session's refresh-token row.
    Access tokens already issued remain valid until their own short expiry —
    the standard access/refresh tradeoff.
    """
    token_hash = hash_token(payload.refresh_token)
    row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if row is not None and row.revoked_at is None:
        row.revoked_at = datetime.now(timezone.utc)
        write_audit_log(db, row.actor_type, row.actor_id, "logout", "refresh_token", row.id)
        db.commit()
    return None

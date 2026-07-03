"""Caregiver invite endpoints — AUTH_LAYER.md §6.2, §9 step 9.

Two accept paths converge on the same `accept_invite` transaction
(app/auth/invites.py): branch 4a is `POST /auth/register/caregiver` with an
`invite_token` (no separate call here); branch 4b is
`POST /caregiver-invites/{token}/accept` below, for a caregiver who already
has an account.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.audit import write_audit_log
from app.auth.invites import accept_invite, create_invite, lookup_pending_invite
from app.core.security import Identity, get_current_identity, require_patient_write_scope
from app.db.base import get_db
from app.db.models import CaregiverCredential, PatientCaregiverLink

router = APIRouter(tags=["caregiver-invites"])


class InviteCreateIn(BaseModel):
    email: str
    role: str = "family"  # "clinician" not exposed in MVP UI, but the mechanism doesn't care


class InviteCreateOut(BaseModel):
    invite_id: UUID
    email: str
    role: str
    expires_at: datetime
    # No email/SMS dispatch exists yet (README "Known gaps" — Notification
    # Service isn't scaffolded), so the raw token is returned directly for
    # local dev / manual testing. Once Twilio/email delivery lands, this
    # field should be dropped from the response and the token sent
    # out-of-band only.
    invite_token: str


class InvitePreviewOut(BaseModel):
    patient_id: UUID
    email: str
    role: str
    expires_at: datetime


class LinkOut(BaseModel):
    patient_id: UUID
    caregiver_id: UUID
    role: str
    status: str


@router.post(
    "/patients/{patient_id}/caregiver-invites",
    response_model=InviteCreateOut,
    status_code=201,
)
def create_caregiver_invite(
    patient_id: UUID,
    payload: InviteCreateIn,
    db: Session = Depends(get_db),
    _scope=Depends(require_patient_write_scope),
):
    """Patient-only (§4.1 write-route rule) — the patient initiates every
    invite (§6.2: MVP has no admin/clinician back-office to originate one
    otherwise).
    """
    if payload.role not in ("family", "clinician"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "role must be 'family' or 'clinician'")

    invite, raw_token = create_invite(db, patient_id=patient_id, email=payload.email.strip().lower(), role=payload.role)
    write_audit_log(
        db,
        "patient",
        patient_id,
        "caregiver_invited",
        "caregiver_invite",
        invite.id,
        metadata={"email": invite.email, "role": invite.role},
    )
    db.commit()
    return InviteCreateOut(
        invite_id=invite.id,
        email=invite.email,
        role=invite.role,
        expires_at=invite.expires_at,
        invite_token=raw_token,
    )


@router.get("/caregiver-invites/{token}", response_model=InvitePreviewOut)
def preview_caregiver_invite(token: str, db: Session = Depends(get_db)):
    """No auth required — the token itself is the credential for this one
    lookup (§6.2 step 3). NOTE: patients/caregivers have no name field
    anywhere in the current schema (Database doc §2.1 keeps contact/identity
    data out of the clinical tables, and the credentials tables added here
    only carry email) — there is no human-readable "invited by <name>" to
    return. Flagged in README known gaps; Product/UX doc needs to specify
    what the accept screen should actually show.
    """
    invite = lookup_pending_invite(db, token)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found, expired, or already used")
    return InvitePreviewOut(
        patient_id=invite.patient_id, email=invite.email, role=invite.role, expires_at=invite.expires_at
    )


@router.post("/caregiver-invites/{token}/accept", response_model=LinkOut)
def accept_caregiver_invite(
    token: str,
    db: Session = Depends(get_db),
    identity: Identity = Depends(get_current_identity),
):
    """§6.2 branch 4b — caregiver already has an account: login first, then
    this call. Step 5's email-match check uses the authenticated session's
    own credential email rather than a client-supplied one.
    """
    if identity.actor_type != "caregiver":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only a caregiver account can accept a caregiver invite")

    invite = lookup_pending_invite(db, token)
    if invite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invite not found, expired, or already used")

    credential = db.get(CaregiverCredential, identity.actor_id)
    if credential is None or credential.email.strip().lower() != invite.email.strip().lower():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invite email does not match the logged-in account")

    link = accept_invite(db, invite, identity.actor_id)
    write_audit_log(
        db,
        "caregiver",
        identity.actor_id,
        "caregiver_link_accepted",
        "patient_caregiver_link",
        invite.patient_id,
        metadata={"invite_id": str(invite.id)},
    )
    db.commit()
    return LinkOut(patient_id=link.patient_id, caregiver_id=link.caregiver_id, role=link.role, status=link.status)


@router.delete("/patients/{patient_id}/caregivers/{caregiver_id}", status_code=204)
def revoke_caregiver_link(
    patient_id: UUID,
    caregiver_id: UUID,
    db: Session = Depends(get_db),
    _scope=Depends(require_patient_write_scope),
):
    """Patient-only (§4.1). Because `require_patient_scope`/`require_patient_write_scope`
    are live DB lookups, this takes effect on the caregiver's *next* request —
    no separate token-invalidation step needed (§6.2's stated payoff of the
    live-lookup design).
    """
    link = db.scalar(
        select(PatientCaregiverLink).where(
            PatientCaregiverLink.patient_id == patient_id,
            PatientCaregiverLink.caregiver_id == caregiver_id,
            PatientCaregiverLink.status == "active",
        )
    )
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No active caregiver link found")

    link.status = "revoked"
    link.revoked_at = datetime.now(timezone.utc)
    write_audit_log(db, "patient", patient_id, "caregiver_link_revoked", "patient_caregiver_link", link.id)
    db.commit()
    return None

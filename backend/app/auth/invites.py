"""Caregiver invite helpers — AUTH_LAYER.md §6.2. Shared between the two
accept paths (4a: register/caregiver with an invite_token inline; 4b:
existing caregiver hits /caregiver-invites/{token}/accept) so the accept
transaction itself is written once.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.tokens import generate_opaque_token, hash_token
from app.db.models import CaregiverInvite, PatientCaregiverLink

INVITE_TTL_DAYS = 7


def create_invite(db: Session, patient_id: UUID, email: str, role: str) -> tuple[CaregiverInvite, str]:
    raw_token = generate_opaque_token()
    invite = CaregiverInvite(
        patient_id=patient_id,
        email=email,
        role=role,
        token_hash=hash_token(raw_token),
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=INVITE_TTL_DAYS),
    )
    db.add(invite)
    db.flush()
    return invite, raw_token


def lookup_pending_invite(db: Session, raw_token: str) -> Optional[CaregiverInvite]:
    invite = db.scalar(select(CaregiverInvite).where(CaregiverInvite.token_hash == hash_token(raw_token)))
    if invite is None:
        return None
    if invite.status != "pending":
        return None
    if invite.expires_at < datetime.now(timezone.utc):
        return None
    return invite


def accept_invite(db: Session, invite: CaregiverInvite, caregiver_id: UUID) -> PatientCaregiverLink:
    """Step 5 of AUTH_LAYER.md §6.2 minus the credentials-insert, which the
    two call sites handle differently (4a creates one inline, 4b already has
    one). Caller is responsible for the email-match check (§6.2 step 5a) and
    for committing.
    """
    link = PatientCaregiverLink(
        patient_id=invite.patient_id,
        caregiver_id=caregiver_id,
        role=invite.role,
        status="active",
    )
    db.add(link)
    invite.status = "accepted"
    invite.accepted_at = datetime.now(timezone.utc)
    db.flush()
    return link

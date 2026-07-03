"""Shared audit_log writer — AUTH_LAYER.md §8.4. No schema change needed
(`audit_log.action` is unconstrained TEXT); this just centralizes the insert
so every auth endpoint writes consistently instead of hand-rolling the model
construction each time.
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AuditLog


def write_audit_log(
    db: Session,
    actor_type: str,
    actor_id: Optional[UUID],
    action: str,
    resource_type: str,
    resource_id: Optional[UUID] = None,
    metadata: Optional[dict] = None,
) -> None:
    db.add(
        AuditLog(
            actor_type=actor_type,
            actor_id=actor_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            event_metadata=metadata,
        )
    )

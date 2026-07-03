"""Issues an (access_token, refresh_token) pair and persists the refresh
token's hash — the one piece of state every login/register/refresh path
needs, factored out so it's written once (AUTH_LAYER.md §3).
"""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.tokens import (
    create_access_token,
    generate_opaque_token,
    hash_token,
    new_session_id,
    refresh_token_expiry,
)
from app.db.models import RefreshToken


def issue_token_pair(
    db: Session, actor_id: UUID, actor_type: str, session_id: Optional[UUID] = None
) -> "tuple[dict, RefreshToken]":
    """`session_id` is passed explicitly on rotation (refresh keeps the same
    chain id); omitted on fresh login/register, where a new session begins.

    Returns (tokens_dict, refresh_token_row) — the row is needed by the
    /auth/refresh handler to set the *previous* row's `replaced_by_id` for
    rotation chaining (AUTH_LAYER.md §3.2); other callers (register, login)
    only use the dict half.
    """
    sid = session_id or new_session_id()
    access_token = create_access_token(actor_id=actor_id, actor_type=actor_type, session_id=sid)

    raw_refresh = generate_opaque_token()
    row = RefreshToken(
        session_id=sid,
        actor_type=actor_type,
        actor_id=actor_id,
        token_hash=hash_token(raw_refresh),
        expires_at=refresh_token_expiry(),
    )
    db.add(row)
    db.flush()

    tokens = {
        "access_token": access_token,
        "refresh_token": raw_refresh,
        "token_type": "bearer",
    }
    return tokens, row

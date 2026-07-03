"""Token issuance — AUTH_LAYER.md §3.

Access tokens: RS256 JWT, 15 min default TTL, signed with the private key
(app/auth/keys.py). Verification (the public-key side) lives in
app/core/security.py per AUTH_LAYER.md §9 step 4/§3.3 — this module only
issues.

Refresh tokens: opaque, high-entropy random values, NOT JWTs — a lookup key
only. The raw value is returned to the caller exactly once (at issuance) and
never stored; only its SHA-256 hash goes in `refresh_tokens.token_hash`. The
same hash-at-rest pattern is reused for caregiver-invite tokens (§8.3) —
`hash_token` is shared between both call sites.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import jwt

from app.auth.keys import get_private_key
from app.core.config import settings

ALGORITHM = "RS256"


def create_access_token(actor_id: UUID, actor_type: str, session_id: UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(actor_id),
        "actor_type": actor_type,
        "token_type": "access",
        "sid": str(session_id),
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_ttl_minutes),
    }
    return jwt.encode(payload, get_private_key(), algorithm=ALGORITHM)


def new_session_id() -> UUID:
    return uuid4()


def generate_opaque_token() -> str:
    """32 bytes of entropy, base64url-encoded — used for both refresh tokens
    (§3.2) and caregiver-invite tokens (§6.2), which share the same
    hash-at-rest storage pattern.
    """
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_ttl_days)

"""Password hashing — AUTH_LAYER.md §2.2: Argon2id via argon2-cffi, not
bcrypt (no 72-byte truncation footgun, tunable memory cost, current OWASP
recommendation).
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()  # library defaults are Argon2id with OWASP-reasonable params


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False

"""RS256 keypair loading for the auth layer — AUTH_LAYER.md §3.1, §9 step 2.

Resolution order (first one that produces both a private and public key wins):

1. Inline PEM via `settings.jwt_private_key_pem` / `jwt_public_key_pem` —
   the production/CI path: a real secrets manager injects these env vars.
2. File paths via `settings.jwt_private_key_path` / `jwt_public_key_path`.
3. Local-dev fallback: look for `jwt_private.pem` / `jwt_public.pem` under
   `settings.jwt_key_dir` (default `.keys/`, relative to the process's cwd —
   i.e. `backend/` when running `uvicorn app.main:app` per the README). If
   missing, generate a fresh 2048-bit RSA keypair, write it there so restarts
   don't invalidate every outstanding session, and log a loud warning that
   this path is dev-only.

`.keys/` must never be committed — see backend/.gitignore.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from app.core.config import settings

logger = logging.getLogger(__name__)


def _generate_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


def _load_from_files(private_path: str, public_path: str) -> tuple[str, str]:
    with open(private_path, "r") as f:
        private_pem = f.read()
    with open(public_path, "r") as f:
        public_pem = f.read()
    return private_pem, public_pem


def _load_or_generate_dev_keys() -> tuple[str, str]:
    key_dir = settings.jwt_key_dir
    private_path = os.path.join(key_dir, "jwt_private.pem")
    public_path = os.path.join(key_dir, "jwt_public.pem")

    if os.path.exists(private_path) and os.path.exists(public_path):
        return _load_from_files(private_path, public_path)

    logger.warning(
        "No JWT keypair configured (jwt_private_key_pem/jwt_public_key_pem or "
        "jwt_private_key_path/jwt_public_key_path unset) and none found at "
        "%s — generating a new dev-only RSA keypair and caching it there. "
        "Every server restart before this file exists issues a new keypair, "
        "invalidating all previously-issued tokens. Do not rely on this path "
        "past local dev.",
        key_dir,
    )
    os.makedirs(key_dir, exist_ok=True)
    private_pem, public_pem = _generate_keypair()
    with open(private_path, "w") as f:
        f.write(private_pem)
    os.chmod(private_path, 0o600)
    with open(public_path, "w") as f:
        f.write(public_pem)
    return private_pem, public_pem


@lru_cache(maxsize=1)
def get_keypair() -> tuple[str, str]:
    """Returns (private_key_pem, public_key_pem). Cached for process lifetime."""
    if settings.jwt_private_key_pem and settings.jwt_public_key_pem:
        return settings.jwt_private_key_pem, settings.jwt_public_key_pem

    if settings.jwt_private_key_path and settings.jwt_public_key_path:
        return _load_from_files(settings.jwt_private_key_path, settings.jwt_public_key_path)

    return _load_or_generate_dev_keys()


def get_private_key() -> str:
    return get_keypair()[0]


def get_public_key() -> str:
    return get_keypair()[1]

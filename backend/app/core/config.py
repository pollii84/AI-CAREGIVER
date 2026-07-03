from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    mongo_url: str
    mongo_db: str = "ai_caregiver"
    anthropic_api_key: Optional[str] = None
    care_agent_model: str = "claude-sonnet-5"

    # Auth layer — 02-Software-Architecture/AUTH_LAYER.md §3.1, §9 step 2.
    # RS256 needs a keypair. Two ways to supply it, checked in this order by
    # app/auth/keys.py:
    #   1. Inline PEM via these settings (prod / CI — real secret manager
    #      injects the env var, newlines as literal "\n").
    #   2. File paths below (local dev default — see .env.example).
    # If neither resolves, app/auth/keys.py generates a keypair on first run
    # and caches it under jwt_key_dir so restarts don't invalidate sessions
    # every reload; this is dev-only and logs a loud warning.
    jwt_private_key_pem: Optional[str] = None
    jwt_public_key_pem: Optional[str] = None
    jwt_private_key_path: Optional[str] = None
    jwt_public_key_path: Optional[str] = None
    jwt_key_dir: str = ".keys"

    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    class Config:
        env_file = ".env"


settings = Settings()

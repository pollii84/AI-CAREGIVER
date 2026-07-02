from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    mongo_url: str
    mongo_db: str = "ai_caregiver"
    anthropic_api_key: Optional[str] = None
    care_agent_model: str = "claude-sonnet-5"

    class Config:
        env_file = ".env"


settings = Settings()

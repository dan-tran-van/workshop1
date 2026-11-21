from typing import List, Union
import secrets
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Restaurant Review Insights API"
    DATABASE_URL: str = "sqlite:///./data.db"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    GOOGLE_PLACES_API_KEY: str = ""
    AUTH_SECRET_KEY: str = secrets.token_urlsafe(32)
    AUTH_BOOTSTRAP_KEY: str = ""
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173"]
    BAD_REVIEW_NOTIFICATIONS_ENABLED: bool = True
    BAD_REVIEW_RATING_THRESHOLD: float = 2.0

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[List[str], str]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    @field_validator("AUTH_SECRET_KEY", mode="before")
    @classmethod
    def generate_auth_secret_if_unset(cls, value: str) -> str:
        if not isinstance(value, str) or not value.strip():
            return secrets.token_urlsafe(32)
        if len(value) < 32:
            raise ValueError("AUTH_SECRET_KEY must contain at least 32 characters")
        return value

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

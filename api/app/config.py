from typing import List, Union
import secrets
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Restaurant Review Insights API"
    DATABASE_URL: str = "sqlite:///./data.db"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    HUGGINGFACE_API_TOKEN: str = ""
    HUGGINGFACE_TTS_MODEL: str = "hexgrad/Kokoro-82M"
    HUGGINGFACE_TTS_PROVIDER: str = "auto"
    HUGGINGFACE_TTS_TIMEOUT: float = 30.0
    GOOGLE_PLACES_API_KEY: str = ""
    AUTH_SECRET_KEY: str = secrets.token_urlsafe(32)
    AUTH_BOOTSTRAP_KEY: str = ""
    CORS_ORIGINS: Union[List[str], str] = ["http://localhost:3000", "http://localhost:5173"]
    BAD_REVIEW_NOTIFICATIONS_ENABLED: bool = True
    BAD_REVIEW_RATING_THRESHOLD: float = 2.0
    # Market comparison (US-01 competitive set, US-02 criteria gap).
    COMPETITOR_MIN_SUGGESTIONS: int = 5
    COMPETITOR_MAX_SUGGESTIONS: int = 10
    # Demo default is 3 because the mock datasets hold at most 5 reviews per HCMC restaurant.
    # Production should use 20 (the value named in US-02).
    MIN_REVIEWS_PER_CRITERION: int = 3
    GAP_TIE_MARGIN: float = 0.3
    GAP_WEAK_COMPETITOR_AVG: float = 3.5

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

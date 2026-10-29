from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent.parent
KNOWLEDGE_BASE_DIR: Path = REPO_ROOT / "knowledge_base" / "benchmarks"


class Settings(BaseSettings):
    APP_NAME: str = "NexusAgent"
    VERSION: str = "0.1.0-alpha"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    KNOWLEDGE_BASE_DIR: Path = KNOWLEDGE_BASE_DIR
    GEMINI_MODELS: list[str] = ["gemini-2.5-flash", "gemini-2.5-flash-lite"]
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    PORT: int = 8000
    CORS_ORIGINS: str | list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://nexusagent.avinaba.com",
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: object) -> list[str]:
        if isinstance(v, str):
            v_str = v.strip()
            if v_str.startswith("[") and v_str.endswith("]"):
                import json

                try:
                    return json.loads(v_str)
                except json.JSONDecodeError, TypeError, ValueError:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    NEON_DATABASE_URL: str = ""

    JWT_SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GUEST_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    # Refreshing cannot extend a login beyond this age; the user must sign in again.
    MAX_SESSION_AGE_DAYS: int = 7
    JWT_ISSUER: str = "nexusagent-api"
    JWT_AUDIENCE: str = "nexusagent-web"
    GUEST_QUOTA_DEFAULT: int = 5
    USER_QUOTA_DEFAULT: int = 25
    MAX_DOCUMENTS_PER_USER: int = 20
    CHAT_HISTORY_MESSAGES: int = 6
    MAX_CHUNKS_PER_DOCUMENT: int = 400
    GUEST_SIGNUPS_PER_IP_PER_HOUR: int = 5
    GUEST_IP_QUOTA_PER_HOUR: int = 15
    GOOGLE_AUTH_PER_IP_PER_HOUR: int = 20
    REFRESH_PER_IP_PER_HOUR: int = 60
    # Rate-limit keying: enable only when behind a trusted reverse proxy that
    # overwrites X-Forwarded-For. Default keys quota on the socket IP so clients
    # cannot rotate quota by header spoofing.
    TRUST_PROXY_HEADERS: bool = False

    GEMINI_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""

    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT in ("development", "test")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.is_dev:
            if not self.JWT_SECRET_KEY:
                self.JWT_SECRET_KEY = "nexusagent-local-dev-only-secret-not-for-production"
            return self
        if len(self.JWT_SECRET_KEY) < 32:
            raise ValueError("JWT_SECRET_KEY must be set (>= 32 chars) outside development/test.")
        if not self.GOOGLE_CLIENT_ID:
            raise ValueError("GOOGLE_CLIENT_ID must be set outside development/test.")
        if self.DEBUG:
            raise ValueError("DEBUG cannot be enabled outside development/test.")
        return self

    model_config = SettingsConfigDict(
        env_file=(
            str(BACKEND_DIR / ".env.local"),
            ".env.local",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

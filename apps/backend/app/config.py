from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    APP_NAME: str = "NexusAgent"
    VERSION: str = "0.1.0-alpha"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    HOST: str = "0.0.0.0"
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
                except Exception:
                    pass
            return [origin.strip() for origin in v_str.split(",") if origin.strip()]
        return v  # type: ignore[return-value]

    NEON_DATABASE_URL: str = ""
    DATABASE_URL: str = ""

    JWT_SECRET_KEY: str = "nexusagent-dev-insecure-secret-key-change-in-production-12345"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GUEST_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    GUEST_QUOTA_DEFAULT: int = 5
    HITL_APPROVAL_TIMEOUT_SECONDS: float = 30.0
    # Rate-limit keying: enable only when behind a trusted reverse proxy that
    # overwrites X-Forwarded-For. Default keys quota on the socket IP so clients
    # cannot rotate quota by header spoofing.
    TRUST_PROXY_HEADERS: bool = False

    # Accepted BYOK key prefixes (provider-recognizable formats only).
    BYOK_PREFIXES: list[str] = ["sk-", "AIza"]

    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        insecure_default = "nexusagent-dev-insecure-secret-key-change-in-production-12345"
        if self.ENVIRONMENT in ("production", "prod", "staging"):
            if not self.JWT_SECRET_KEY or self.JWT_SECRET_KEY == insecure_default:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a secure, unique secret in production/staging environments."
                )
            if len(self.JWT_SECRET_KEY) < 32:
                raise ValueError("JWT_SECRET_KEY must be at least 32 characters in production.")
            if self.DEBUG:
                raise ValueError("DEBUG mode cannot be enabled in production/staging environments.")
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

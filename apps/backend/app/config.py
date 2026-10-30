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
    # Free-tier text models, best first (ai.google.dev/gemini-api/docs/pricing, 2026-10-28). Each has
    # its own free quota; ModelRouter moves to the next one when a model returns 429.
    GEMINI_MODELS: list[str] = [
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash-lite",
    ]
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    PORT: int = 8000
    CORS_ORIGINS: str | list[str] = ["https://nexusagent.avinaba.com"]

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
    # Refreshing cannot extend a login beyond this age; the user must sign in again.
    MAX_SESSION_AGE_DAYS: int = 7
    JWT_ISSUER: str = "nexusagent-api"
    JWT_AUDIENCE: str = "nexusagent-web"
    GUEST_QUOTA_DEFAULT: int = 5
    USER_QUOTA_DEFAULT: int = 25
    MAX_DOCUMENTS_PER_USER: int = 20
    CHAT_HISTORY_MESSAGES: int = 6
    MAX_CHUNKS_PER_DOCUMENT: int = 400
    # Request-body caps enforced before parsing/auth: 1 MB file + multipart overhead, and a small cap elsewhere.
    MAX_UPLOAD_REQUEST_BYTES: int = 1024 * 1024 + 16 * 1024
    MAX_JSON_REQUEST_BYTES: int = 64 * 1024
    GUEST_SIGNUPS_PER_IP_PER_HOUR: int = 5
    GUEST_IP_QUOTA_PER_HOUR: int = 15
    GOOGLE_AUTH_PER_IP_PER_HOUR: int = 20
    REFRESH_PER_IP_PER_HOUR: int = 60
    # Number of trusted reverse proxies in front of the API (Render alone = 1; Cloudflare in front
    # of Render = 2). 0 keys per-IP limits on the socket address, which behind a proxy is the
    # proxy's address, so every user shares one limit. Never set it higher than the real hop count.
    TRUSTED_PROXY_HOPS: int = 0

    GEMINI_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""

    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT in ("development", "test")

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.is_dev:
            local_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
            self.CORS_ORIGINS = [
                *(o for o in local_origins if o not in self.CORS_ORIGINS),
                *self.CORS_ORIGINS,
            ]
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

from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent.parent
KNOWLEDGE_BASE_DIR: Path = REPO_ROOT / "knowledge_base" / "benchmarks"
# Render = 1 hop, Cloudflare in front of Render = 2. More than that trusts client-supplied forwarding.
MAX_TRUSTED_PROXY_HOPS = 2


class Settings(BaseSettings):
    APP_NAME: str = "NexusAgent"
    VERSION: str = "0.1.0-alpha"
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    # Free-tier text models, best first (ai.google.dev/gemini-api/docs/pricing). Each has
    # its own free quota; ModelRouter moves to the next one when a model returns 429.
    # Routing order is not this list's order: see TEXT_MODELS (lite first, then Gemma, then flash).
    GEMINI_MODELS: list[str] = [
        "gemini-3.8-flash",
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-3-flash-preview",
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
        "gemini-flash-lite-latest",
    ]
    # Hosted Gemma 4 instruction models (gemma.ai/deployment/gemini-api). Free on the Gemini
    # Developer API, each with its own quota. They support generateContent, function calling,
    # system instructions, and Google Search. Smaller Gemma sizes are not hosted.
    # Stronger model first; TEXT_MODELS tries them after the flash-lite models and before full flash.
    GEMMA_MODELS: list[str] = [
        "gemma-4-31b-it",
        "gemma-4-26b-a4b-it",
    ]
    EMBEDDING_MODEL: str = "gemini-embedding-001"

    PORT: int = 8000
    PUBLIC_SITE_HOST: str = "nexusagent.avinaba.com"
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
    # Guest chats per rolling day from one client network (an IPv4 address or an IPv6 /64).
    # Everyone behind a shared NAT shares it, so it is a multiple of GUEST_QUOTA_DEFAULT.
    GUEST_QUOTA_PER_NETWORK: int = 20
    # Service-wide ceilings per rolling day. They keep scripted guests from spending the free
    # model quota that every user shares. 0 switches a ceiling off.
    GUEST_CHATS_PER_DAY: int = 500
    CHATS_PER_DAY: int = 1500
    CHAT_HISTORY_MESSAGES: int = 6
    LLM_TIMEOUT_SECONDS: float = 45.0
    # A streamed call that sends nothing for this long is abandoned and the next model is tried.
    # Covers thinking and search grounding, which happen before the first chunk. 0 disables it.
    LLM_FIRST_TOKEN_TIMEOUT_SECONDS: float = 10.0
    # Includes "thinking" tokens on models that think. Too low truncates answers; raise it if answers are cut off.
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    MAX_CHUNKS_PER_DOCUMENT: int = 400
    # Request-body caps enforced before parsing/auth: 5 MB file + multipart overhead, and a small cap elsewhere.
    MAX_UPLOAD_REQUEST_BYTES: int = 5 * 1024 * 1024 + 16 * 1024
    MAX_JSON_REQUEST_BYTES: int = 64 * 1024
    GUEST_SIGNUPS_PER_IP_PER_HOUR: int = 5
    # Public MCP search embeds one query per call. This caps that spend per rolling day.
    # Further MCP searches keep working on the lexical index.
    MCP_EMBEDDINGS_PER_DAY: int = 200
    GOOGLE_AUTH_PER_IP_PER_HOUR: int = 20
    REFRESH_PER_IP_PER_HOUR: int = 60
    # Number of trusted reverse proxies in front of the API (Render alone = 1; Cloudflare in front
    # of Render = 2). 0 keys per-IP limits on the socket address, which behind a proxy is the
    # proxy's address, so every user shares one limit. Never set it higher than the real hop count.
    # The ceiling is the larger of those two deployments: a higher value would trust client-supplied
    # X-Forwarded-For entries.
    TRUSTED_PROXY_HOPS: int = 0

    GEMINI_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""

    @property
    def TEXT_MODELS(self) -> list[str]:
        """Free-tier chat models in routing order: Gemini flash-lite, then Gemma, then full Gemini flash.

        Lite and Gemma models answer quickly and have far larger daily quotas (500 vs 20 requests on
        the free tier), while the full flash models are often slow or overloaded, so they are the
        fallback. Each group keeps its configured order.
        """
        lite = [m for m in self.GEMINI_MODELS if "lite" in m.lower()]
        full = [m for m in self.GEMINI_MODELS if "lite" not in m.lower()]
        return [*lite, *self.GEMMA_MODELS, *full]

    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT in ("development", "test")

    @property
    def SESSION_COOKIE_NAME(self) -> str:
        return "nexus_session" if self.is_dev else "__Host-nexus_session"

    @property
    def DEVICE_COOKIE_NAME(self) -> str:
        return "nexus_device" if self.is_dev else "__Host-nexus_device"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> Settings:
        if self.TRUSTED_PROXY_HOPS < 0 or self.TRUSTED_PROXY_HOPS > MAX_TRUSTED_PROXY_HOPS:
            raise ValueError(
                f"TRUSTED_PROXY_HOPS must be between 0 and {MAX_TRUSTED_PROXY_HOPS} "
                "(Render = 1, Cloudflare in front of Render = 2)."
            )
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
        if self.TRUSTED_PROXY_HOPS < 1:
            raise ValueError(
                "TRUSTED_PROXY_HOPS must be >= 1 outside development/test "
                "(Render = 1). With 0 every client shares the proxy's IP address."
            )
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

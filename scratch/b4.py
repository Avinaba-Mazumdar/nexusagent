from ed import rep

# config.py: ruff rewrites setattr(self, "X", v) back to assignment, so write the field dict.
rep(
    "app/config.py",
    """            # Settings fields are uppercase by convention, not constants, so the dev defaults
            # are filled in with setattr (plain assignment reads as a constant redefinition).
            origins = [
                *(o for o in local_origins if o not in self.CORS_ORIGINS),
                *self.CORS_ORIGINS,
            ]
            self.CORS_ORIGINS = origins
            if not self.JWT_SECRET_KEY:
                self.JWT_SECRET_KEY = "nexusagent-local-dev-only-secret-not-for-production"
""",
    """            # Settings fields are uppercase by convention, not constants. Plain assignment reads
            # as a constant redefinition to the type checker, so the dev defaults go through
            # the model's field dict (validate_assignment is off, so this is equivalent).
            dev_defaults: dict[str, object] = {
                "CORS_ORIGINS": [
                    *(o for o in local_origins if o not in self.CORS_ORIGINS),
                    *self.CORS_ORIGINS,
                ]
            }
            if not self.JWT_SECRET_KEY:
                dev_defaults["JWT_SECRET_KEY"] = "nexusagent-local-dev-only-secret-not-for-production"
            self.__dict__.update(dev_defaults)
""",
)

# main.py: asynccontextmanager wants an AsyncGenerator annotation
rep("app/main.py", "async def lifespan(_app: FastAPI) -> AsyncIterator[None]:", "async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:")
rep("app/main.py", "from collections.abc import AsyncIterator, Awaitable, Callable\n", "from collections.abc import AsyncGenerator, Awaitable, Callable\n")

# embeddings.py
rep(
    "app/rag/embeddings.py",
    """        self.api_key = api_key or settings.GEMINI_API_KEY
        self.dimension = EMBEDDING_DIMENSION
        self.model = settings.EMBEDDING_MODEL""",
    """        self.api_key: str = api_key or settings.GEMINI_API_KEY
        self.dimension: int = EMBEDDING_DIMENSION
        self.model: str = settings.EMBEDDING_MODEL""",
)
rep("app/rag/embeddings.py", "        self, url: str, headers: dict[str, str], payload: dict\n", "        self, url: str, headers: dict[str, str], payload: dict[str, object]\n")
rep(
    "app/rag/embeddings.py",
    """            embeddings = [item["values"] for item in response.json().get("embeddings", [])]""",
    """            try:
                body = _BatchEmbedResponse.model_validate(cast(object, response.json()))
            except (ValueError, ValidationError) as exc:
                logger.error("Gemini embedding API (%s) returned a malformed body", self.model)
                raise EmbeddingUnavailable("Gemini embedding provider unavailable") from exc
            embeddings = [item.values for item in body.embeddings]""",
)
rep(
    "app/rag/embeddings.py",
    "class EmbeddingUnavailable(RuntimeError):",
    '''class _Embedding(BaseModel):
    values: list[float]


class _BatchEmbedResponse(BaseModel):
    """The part of a ``batchEmbedContents`` response this client reads."""

    embeddings: list[_Embedding] = []


class EmbeddingUnavailable(RuntimeError):''',
)
rep("app/rag/embeddings.py", "from collections.abc import Sequence\n\nimport httpx\n", "from collections.abc import Sequence\nfrom typing import cast\n\nimport httpx\nfrom pydantic import BaseModel, ValidationError\n")

# csrf.py: ASGI scope values are untyped
rep("app/core/csrf.py", '            or not scope["path"].startswith("/api/")', '            or not cast(str, scope["path"]).startswith("/api/")')
rep(
    "app/core/csrf.py",
    '        for raw_k, raw_v in scope.get("headers", []):',
    '        for raw_k, raw_v in cast(list[tuple[bytes, bytes]], scope.get("headers", [])):',
)
rep("app/core/csrf.py", "import json\n", "import json\nfrom typing import cast\n")

# audit_log.py
rep(
    "app/core/audit_log.py",
    '''def _row_to_entry(r: Any) -> dict[str, Any]:
    return {
        "id": str(r["id"]),
        "tool_name": r["tool_name"],
        "mcp_server": r["mcp_server"],
        "input_args": r["input_args"],
        "output_summary": r["output_summary"],
        "duration_ms": r["duration_ms"],
        "user_id": str(r["user_id"]) if r["user_id"] else None,
        "conversation_id": str(r["conversation_id"]) if r["conversation_id"] else None,
        "executed_at": r["executed_at"].isoformat() if r["executed_at"] else None,
    }''',
    '''def _row_to_entry(r: Record) -> dict[str, object]:
    row = record_dict(r)
    user_id = row["user_id"]
    conversation_id = row["conversation_id"]
    executed_at = col_opt_datetime(r, "executed_at")
    return {
        "id": str(row["id"]),
        "tool_name": row["tool_name"],
        "mcp_server": row["mcp_server"],
        "input_args": row["input_args"],
        "output_summary": row["output_summary"],
        "duration_ms": row["duration_ms"],
        "user_id": str(user_id) if user_id else None,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "executed_at": executed_at.isoformat() if executed_at else None,
    }''',
)
rep("app/core/audit_log.py", "        self.db = db or neon_db", "        self.db: NeonDatabase = db or neon_db")
rep("app/core/audit_log.py", "        input_args: dict[str, Any],\n        output_summary: dict[str, Any] | None,", "        input_args: dict[str, object],\n        output_summary: dict[str, object] | None,")
rep("app/core/audit_log.py", "    ) -> list[dict[str, Any]]:", "    ) -> list[dict[str, object]]:")
rep(
    "app/core/audit_log.py",
    """                f"SELECT {SELECT_COLUMNS} FROM tool_audit_logs "
                "WHERE user_id""",
    """                f"SELECT {SELECT_COLUMNS} FROM tool_audit_logs "
                + "WHERE user_id""",
)
rep("app/core/audit_log.py", "from typing import Any\nfrom uuid import UUID, uuid4\n\n", "from uuid import UUID, uuid4\n\nfrom asyncpg import Record\n\n")
rep("app/core/audit_log.py", "from app.db.neon import NeonDatabase, neon_db\n", "from app.db.neon import NeonDatabase, neon_db\nfrom app.db.records import col_opt_datetime, record_dict\n")

# mcp/server.py
rep("app/mcp/server.py", "async def search(query: str) -> dict:", "async def search(query: str) -> dict[str, object]:")
rep("app/mcp/server.py", "async def fetch(id: str) -> dict:", "async def fetch(id: str) -> dict[str, object]:")
print("ok")

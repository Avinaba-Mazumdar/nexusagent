"""
MCP Tool & Resource Registry.
Provides tools:
  - hybrid_rag_search: Dense pgvector + BM25 tsvector with RRF ranking
"""

import logging
import time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.config import KNOWLEDGE_BASE_DIR
from app.core.audit_log import default_audit_logger
from app.core.security_guardrails import sanitize_retrieved_chunks, wrap_untrusted_context
from app.mcp.protocol import (
    ResourceDefinition,
    ToolCallContent,
    ToolCallResult,
    ToolDefinition,
    ToolInputSchema,
)
from app.rag.hybrid_search import default_hybrid_search_engine

logger = logging.getLogger("nexusagent.mcp.registry")


class HybridRagSearchArgs(BaseModel):
    """Typed arguments for ``hybrid_rag_search``; also the source of the advertised JSON schema."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(
        min_length=1,
        max_length=1000,
        description="Natural language query to search across architectural RFCs and benchmarks.",
    )
    limit: int = Field(
        default=5, ge=1, le=20, description="Maximum number of chunks to return (1 to 20)."
    )


class InvalidToolArguments(ValueError):
    """Raised when tool arguments do not satisfy the tool's schema."""


ARGUMENT_MODELS: dict[str, type[BaseModel]] = {"hybrid_rag_search": HybridRagSearchArgs}


def _tool_definition(name: str, description: str, model: type[BaseModel]) -> ToolDefinition:
    schema = model.model_json_schema()
    return ToolDefinition(
        name=name,
        description=description,
        inputSchema=ToolInputSchema(
            properties=schema["properties"], required=schema.get("required", [])
        ),
    )


TOOLS: list[ToolDefinition] = [
    _tool_definition(
        "hybrid_rag_search",
        "Performs dense pgvector and sparse BM25 hybrid search across RFC documents and AI model "
        "benchmarks fused via Reciprocal Rank Fusion (RRF).",
        HybridRagSearchArgs,
    ),
]


# Resource Definitions
STATIC_RESOURCES: list[ResourceDefinition] = [
    ResourceDefinition(
        uri="benchmark://benchlm-2026",
        name="BenchLM Overall Model Rankings",
        description="BenchLM overall scores, prices and evidence levels (snapshot retrieved 2026-10-30).",
        mimeType="text/markdown",
    ),
    ResourceDefinition(
        uri="benchmark://cursorbench-coding",
        name="CursorBench Agentic Coding Leaderboard",
        description="CursorBench 4.0 agentic coding scores and cost per task (snapshot retrieved 2026-10-30).",
        mimeType="text/markdown",
    ),
]


class McpRegistry:
    """Manages MCP tool execution and resource listing."""

    @staticmethod
    def get_tools() -> list[dict[str, Any]]:
        return [tool.model_dump() for tool in TOOLS]

    @staticmethod
    def validate_arguments(name: str, arguments: Any) -> BaseModel:
        """Validate arguments against the tool's schema (``name`` must be a known tool)."""
        if not isinstance(arguments, dict):
            raise InvalidToolArguments("'arguments' must be an object.")
        try:
            return ARGUMENT_MODELS[name].model_validate(arguments)
        except ValidationError as exc:
            problems = "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: {err['msg']}"
                for err in exc.errors()
            )
            raise InvalidToolArguments(problems) from exc

    @staticmethod
    def get_resources() -> list[dict[str, Any]]:
        return [res.model_dump() for res in STATIC_RESOURCES]

    @staticmethod
    async def read_resource(uri: str) -> dict[str, Any]:
        """Read resource content by URI."""
        filename_map = {
            "benchmark://benchlm-2026": "benchlm_evals.md",
            "benchmark://cursorbench-coding": "cursor_bench.md",
        }

        # Check knowledge base files
        filename = filename_map.get(uri)
        if filename and KNOWLEDGE_BASE_DIR.is_dir():
            target_file = KNOWLEDGE_BASE_DIR / filename
            if target_file.is_file():
                content = target_file.read_text(encoding="utf-8")
                return {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "text/markdown",
                            "text": content,
                        }
                    ]
                }

        raise ValueError(f"Unknown resource: {uri}")

    @classmethod
    async def call_tool(
        cls, name: str, parsed: BaseModel, user_id: UUID | None = None
    ) -> ToolCallResult:
        """Run an already-validated tool call and write an audit row."""
        start_time = time.perf_counter()
        result = await cls._exec_hybrid_search(parsed)  # type: ignore[arg-type]

        duration_ms = max(int((time.perf_counter() - start_time) * 1000), 0)
        await default_audit_logger.log_tool_audit(
            tool_name=name,
            input_args=parsed.model_dump(),
            output_summary={"isError": result.isError},
            duration_ms=duration_ms,
            user_id=user_id,
            mcp_server="nexusagent-mcp",
        )
        return result

    @classmethod
    async def _exec_hybrid_search(cls, args: HybridRagSearchArgs) -> ToolCallResult:
        query = args.query.strip()
        try:
            results = await default_hybrid_search_engine.search(query=query, limit=args.limit)
        except RuntimeError:
            return ToolCallResult(
                content=[ToolCallContent(text="Knowledge base unavailable.")],
                isError=True,
            )

        safe_results, _ = sanitize_retrieved_chunks(results)
        if not safe_results:
            return ToolCallResult(
                content=[
                    ToolCallContent(
                        text=f"No matching chunks found in knowledge base for query: '{query}'."
                    )
                ],
                isError=False,
            )

        formatted_chunks = []
        for idx, r in enumerate(safe_results, start=1):
            line_info = (
                f" (Lines {r.start_line}-{r.end_line})" if r.start_line and r.end_line else ""
            )
            header_info = f" § {' > '.join(r.header_path)}" if r.header_path else ""
            wrapped = wrap_untrusted_context(
                r.content,
                filename=r.filename,
                start_line=r.start_line,
                end_line=r.end_line,
            )
            formatted_chunks.append(
                f"### Result {idx}: [{r.filename}{line_info}]{header_info}\n"
                f"Relevance Score (RRF): {r.similarity_score:.4f}\n\n"
                f"{wrapped}\n"
            )

        return ToolCallResult(
            content=[ToolCallContent(text="\n---\n".join(formatted_chunks))],
            isError=False,
        )


default_mcp_registry = McpRegistry()

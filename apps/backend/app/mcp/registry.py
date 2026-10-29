"""
MCP Tool & Resource Registry.
Provides tools:
  - hybrid_rag_search: Dense pgvector + BM25 tsvector with RRF ranking
"""

import logging
import time
from typing import Any
from uuid import UUID

from app.config import KNOWLEDGE_BASE_DIR
from app.core.audit_log import default_audit_logger
from app.core.security_guardrails import compute_mcp_tool_hash, scan_mcp_tool_metadata
from app.mcp.protocol import (
    ResourceDefinition,
    ToolCallContent,
    ToolCallResult,
    ToolDefinition,
    ToolInputSchema,
)
from app.rag.hybrid_search import default_hybrid_search_engine

logger = logging.getLogger("nexusagent.mcp.registry")


# Tool Definitions
TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="hybrid_rag_search",
        description="Performs dense pgvector and sparse BM25 hybrid search across RFC documents and AI model benchmarks fused via Reciprocal Rank Fusion (RRF).",
        inputSchema=ToolInputSchema(
            properties={
                "query": {
                    "type": "string",
                    "description": "Natural language query to search across architectural RFCs and benchmarks.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of chunks to return (1 to 20). Default is 5.",
                    "default": 5,
                },
            },
            required=["query"],
        ),
    ),
]

# Pinned cryptographic schema hashes for zero-trust MCP tool integrity (detects rug pull modifications)
PINNED_TOOL_HASHES: dict[str, str] = {tool.name: compute_mcp_tool_hash(tool) for tool in TOOLS}


# Resource Definitions
STATIC_RESOURCES: list[ResourceDefinition] = [
    ResourceDefinition(
        uri="benchmark://benchlm-2026",
        name="BenchLM 2026 AI Model Intelligence & Latency Suite",
        description="Weekly frontier model reasoning, throughput, and TTFT benchmarks.",
        mimeType="text/markdown",
    ),
    ResourceDefinition(
        uri="benchmark://cursorbench-coding",
        name="CursorBench Agentic Coding Leaderboard",
        description="Comparative software engineering benchmarks for Claude, GPT, and Gemini.",
        mimeType="text/markdown",
    ),
]


class McpRegistry:
    """Manages MCP tool execution, resource listing, and protocol dispatch with zero-trust validation."""

    @classmethod
    def validate_tool_integrity(cls, tool: ToolDefinition) -> tuple[bool, str | None]:
        """
        Verify tool against Invariant Labs MCP tool poisoning attacks & rug pull hash drift.
        Returns (is_valid, failure_reason).
        """
        is_poisoned, reason = scan_mcp_tool_metadata(tool)
        if is_poisoned:
            return False, reason

        expected_hash = PINNED_TOOL_HASHES.get(tool.name)
        if expected_hash:
            current_hash = compute_mcp_tool_hash(tool)
            if current_hash != expected_hash:
                return False, (
                    f"Tool integrity violation: Schema hash mismatch for '{tool.name}' "
                    f"(expected {expected_hash[:12]}..., got {current_hash[:12]}...). "
                    "Possible unauthorized runtime tampering (rug pull attack)."
                )
        return True, None

    @classmethod
    def get_tools(cls) -> list[dict[str, Any]]:
        safe_tools = []
        for tool in TOOLS:
            is_valid, reason = cls.validate_tool_integrity(tool)
            if not is_valid:
                logger.error("Skipping untrusted/poisoned MCP tool '%s': %s", tool.name, reason)
                continue
            dumped = tool.model_dump()
            dumped["schemaHash"] = compute_mcp_tool_hash(tool)
            safe_tools.append(dumped)
        return safe_tools

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
        cls, name: str, arguments: dict[str, Any], user_id: UUID | None = None
    ) -> ToolCallResult:
        """Route and execute tool invocation with pre-execution poisoning & integrity gates."""
        start_time = time.perf_counter()
        target_tool = next((t for t in TOOLS if t.name == name), None)
        if not target_tool:
            result = ToolCallResult(
                content=[
                    ToolCallContent(
                        text=f"Unknown tool '{name}'. Available: {', '.join(t.name for t in TOOLS)}"
                    )
                ],
                isError=True,
            )
        else:
            is_valid, reason = cls.validate_tool_integrity(target_tool)
            if not is_valid:
                logger.critical(
                    "Execution blocked for poisoned/tampered MCP tool '%s': %s", name, reason
                )
                result = ToolCallResult(
                    content=[ToolCallContent(text=f"Security Violation: {reason}")],
                    isError=True,
                )
            elif name == "hybrid_rag_search":
                result = await cls._exec_hybrid_search(arguments)
            else:
                result = ToolCallResult(
                    content=[ToolCallContent(text=f"Unknown tool '{name}'.")],
                    isError=True,
                )

        duration_ms = max(int((time.perf_counter() - start_time) * 1000), 0)
        try:
            await default_audit_logger.log_tool_audit(
                tool_name=name,
                input_args=arguments,
                output_summary={"isError": result.isError},
                duration_ms=duration_ms,
                user_id=user_id,
                mcp_server="nexusagent-mcp",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to log MCP tool audit: %s", e)

        return result

    @classmethod
    async def _exec_hybrid_search(cls, arguments: dict[str, Any]) -> ToolCallResult:
        query = str(arguments.get("query", "")).strip()
        if not query:
            return ToolCallResult(
                content=[ToolCallContent(text="Missing required argument 'query'.")],
                isError=True,
            )
        limit = min(max(int(arguments.get("limit", 5)), 1), 20)

        try:
            results = await default_hybrid_search_engine.search(query=query, limit=limit)
        except RuntimeError:
            return ToolCallResult(
                content=[ToolCallContent(text="Knowledge base unavailable.")],
                isError=True,
            )

        if not results:
            return ToolCallResult(
                content=[
                    ToolCallContent(
                        text=f"No matching chunks found in knowledge base for query: '{query}'."
                    )
                ],
                isError=False,
            )

        formatted_chunks = []
        for idx, r in enumerate(results, start=1):
            line_info = (
                f" (Lines {r.start_line}-{r.end_line})" if r.start_line and r.end_line else ""
            )
            header_info = f" § {' > '.join(r.header_path)}" if r.header_path else ""
            formatted_chunks.append(
                f"### Result {idx}: [{r.filename}{line_info}]{header_info}\n"
                f"Relevance Score (RRF): {r.similarity_score:.4f}\n\n"
                f"{r.content.strip()}\n"
            )

        return ToolCallResult(
            content=[ToolCallContent(text="\n---\n".join(formatted_chunks))],
            isError=False,
        )


default_mcp_registry = McpRegistry()

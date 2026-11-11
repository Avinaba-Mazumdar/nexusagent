from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from langchain_core.messages import AnyMessage
from pydantic import BaseModel, ConfigDict, Field

from app.rag.hybrid_search import HybridSearchResult

Intent = Literal["smalltalk", "benchmark", "refuse"]
Grounding = Literal["grounded", "weak", "none"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class UsageRecord(BaseModel):
    step: str  # "router" | "chat" | "agent" | "web_search"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0


class WebSource(BaseModel):
    title: str
    url: str


class Citation(BaseModel):
    """A source the model was shown. ``label`` ([S1], [S2], ...) is what the answer cites."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    label: str
    chunk_id: str
    document_id: str
    filename: str
    page: int | None = None
    header_path: list[str] = Field(default_factory=list)
    preview: str = ""


class PlanStep(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    step_number: int
    description: str
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed"
    tool: str | None = None


class InjectionWarning(BaseModel):
    filename: str
    reason: str


class ToolEvent(BaseModel):
    """One executed tool call, reported to the client and the audit log."""

    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    results: int = 0
    duration_ms: int = 0
    error: str | None = None


class AgentState(BaseModel):
    """
    Strongly-typed state for the LangGraph pipeline:
    router -> refuse | chat | preload -> agent <-> tools.
    """

    model_config = ConfigDict(from_attributes=True)

    # Conversation identity
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: UUID | None = None
    conversation_id: UUID | None = None  # set only when resuming a persisted conversation
    query: str
    document_id: UUID | None = None
    chat_history: list[dict[str, str]] = Field(default_factory=list)

    # Node execution history
    node_history: list[str] = Field(default_factory=list)
    current_node: str | None = None

    # Routing
    intent: Intent | None = None
    plan: list[PlanStep] = Field(default_factory=list)

    # Retrieval
    retrieved_chunks: list[HybridSearchResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    injection_warnings: list[InjectionWarning] = Field(default_factory=list)
    retrieval_duration_ms: int | None = None

    # Grounding check
    grounding: Grounding = "none"
    grounding_feedback: str | None = None

    # Web search (Google Search grounding in chat or agent web_search tool)
    web_search_queries: list[str] = Field(default_factory=list)
    web_sources: list[WebSource] = Field(default_factory=list)
    search_duration_ms: int | None = None

    # Tool-calling loop (benchmark route)
    agent_messages: list[AnyMessage] = Field(default_factory=list)
    pending_tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_rounds: int = 0
    tool_events: list[ToolEvent] = Field(default_factory=list)

    # Citation checking (C4)
    invalid_citations: list[str] = Field(default_factory=list)
    uncited: bool = False

    # Token and model usage observability
    usage: list[UsageRecord] = Field(default_factory=list)

    # Final response
    response: str = ""
    model: str | None = None  # the Gemini model that produced ``response``
    error: str | None = None
    is_complete: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

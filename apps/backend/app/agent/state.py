from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.rag.hybrid_search import HybridSearchResult

Intent = Literal["greeting", "architectural", "out_of_scope"]
Grounding = Literal["grounded", "weak", "none"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class Citation(BaseModel):
    """A source the model was shown. ``label`` ([S1], [S2], ...) is what the answer cites."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    label: str
    chunk_id: str
    document_id: str
    filename: str
    start_line: int | None = None
    end_line: int | None = None
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


class AgentState(BaseModel):
    """
    Strongly-typed state for the LangGraph pipeline:
    planner -> retriever -> grounding check -> synthesizer.
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

    # Planning (intent is classified once, by the caller or the planner)
    intent: Intent | None = None
    plan: list[PlanStep] = Field(default_factory=list)

    # Retrieval
    retrieved_chunks: list[HybridSearchResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)
    injection_warnings: list[InjectionWarning] = Field(default_factory=list)

    # Grounding check
    grounding: Grounding = "none"
    grounding_feedback: str | None = None

    # Security
    canary_token: str | None = None
    canary_leaked: bool = False

    # Final synthesis
    response: str = ""
    error: str | None = None
    mermaid_diagrams: list[str] = Field(default_factory=list)
    is_complete: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

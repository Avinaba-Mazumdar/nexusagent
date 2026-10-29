from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.rag.hybrid_search import HybridSearchResult


def utc_now() -> datetime:
    return datetime.now(UTC)


class Citation(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
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


class AgentState(BaseModel):
    """
    Strongly-typed state container for LangGraph Agent DAG Execution Pipeline.
    Maintains complete trace of planning, retrieval, tool executions,
    reflection critique, loop iterations, and final architectural synthesis.
    """

    model_config = ConfigDict(from_attributes=True)

    # Core conversation identity
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    user_id: UUID | None = None
    query: str
    document_id: UUID | None = None
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    max_history_turns: int = 6

    # DAG Node Execution History
    node_history: list[str] = Field(default_factory=list)
    current_node: str | None = None

    # Planning phase
    plan: list[PlanStep] = Field(default_factory=list)

    # Retrieval phase
    retrieved_chunks: list[HybridSearchResult] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    # Reflection Critic & Quality Loop
    reflection_score: float = 0.0  # 0.0 to 1.0 (>= 0.70 considered grounded)
    reflection_feedback: str | None = None
    is_grounded: bool = False
    needs_replan: bool = False
    iteration_count: int = 0
    max_iterations: int = 10

    # Security Guardrails
    canary_token: str | None = None
    injection_detected: bool = False
    injection_reason: str | None = None

    # Final Synthesis
    response: str = ""
    mermaid_diagrams: list[str] = Field(default_factory=list)
    is_complete: bool = False
    created_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = None

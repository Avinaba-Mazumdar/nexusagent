from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    email: str | None = None
    name: str = "Guest Reviewer"
    avatar_url: str | None = None
    is_guest: bool = True
    client_ip: str | None = None
    device_id: str | None = None
    token_version: int = 0
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class RateLimitBucket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    tokens_remaining: int = 5
    bucket_capacity: int = 5
    last_replenished_at: datetime = Field(default_factory=utc_now)


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID | None = None
    filename: str
    mime_type: str = "text/markdown"
    sha256_hash: str
    total_chunks: int = 0
    is_seeded: bool = False
    uploaded_at: datetime = Field(default_factory=utc_now)


class DocumentChunk(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    chunk_index: int
    content: str
    embedding: list[float] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=utc_now)

    @field_validator("embedding", mode="before")
    @classmethod
    def convert_vector_to_list(cls, v: Any) -> list[float] | None:
        if v is None:
            return None
        if hasattr(v, "tolist"):
            return [float(x) for x in v.tolist()]
        try:
            return [float(x) for x in v]
        except TypeError, ValueError:
            return v


def _wire_id(value: Any) -> Any:
    """UUIDs travel as their canonical string form."""
    return str(value) if isinstance(value, UUID) else value


def _wire_timestamp(value: Any) -> Any:
    """Datetimes travel as ISO-8601 strings."""
    return value.isoformat() if isinstance(value, datetime) else value


def _wire_count(value: Any) -> Any:
    """Message counts are never null on the wire: a missing count is zero."""
    return 0 if value is None else value


WireId = Annotated[str, BeforeValidator(_wire_id)]
WireTimestamp = Annotated[str, BeforeValidator(_wire_timestamp)]


class WireModel(BaseModel):
    """
    Wire schema with snake_case fields that serialise as camelCase. Built straight from objects
    or row dicts of the same shape (``model_validate``); UUIDs and datetimes become strings.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)


# Wire Schemas matching packages/contracts/src/auth.ts


class UserSession(WireModel):
    id: WireId
    email: str | None = None
    name: str
    avatar_url: str | None = None
    is_guest: bool
    created_at: WireTimestamp
    last_seen_at: WireTimestamp


class GuestPassRequest(BaseModel):
    # The device id re-opens a guest account, so it must be long enough to be unguessable.
    deviceId: str | None = Field(default=None, min_length=16, max_length=128)


class AuthTokens(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int


class GuestPassResponse(BaseModel):
    user: UserSession
    tokens: AuthTokens
    quotaRemaining: int
    bucketCapacity: int


class QuotaStatus(BaseModel):
    tokensRemaining: int
    bucketCapacity: int
    resetsAt: str


class GoogleAuthRequest(BaseModel):
    credential: str = Field(..., min_length=10, max_length=4096)


class TokenResponse(BaseModel):
    accessToken: str
    tokenType: str = "bearer"
    expiresIn: int
    user: UserSession
    quotaRemaining: int = 25
    bucketCapacity: int = 25


class DocumentMetadataWire(WireModel):
    id: WireId
    user_id: WireId | None = None
    filename: str
    mime_type: str
    sha256_hash: str
    total_chunks: int
    is_seeded: bool
    uploaded_at: WireTimestamp


class DocumentChunkWire(WireModel):
    id: WireId
    document_id: WireId
    chunk_index: int
    content: str
    metadata: dict[str, Any]
    created_at: WireTimestamp


class DocumentUploadResponseWire(WireModel):
    document: DocumentMetadataWire
    chunks_count: int
    preview_chunks: list[DocumentChunkWire]
    quota_remaining: int | None = None


class DocumentListResponseWire(WireModel):
    documents: list[DocumentMetadataWire]


class MeResponse(BaseModel):
    user: UserSession
    quota: QuotaStatus


class SuccessResponse(BaseModel):
    success: bool
    id: str | None = None


# Wire Schemas matching packages/contracts/src/chat.ts


class ChatConversationWire(WireModel):
    id: WireId
    user_id: WireId
    title: str
    created_at: WireTimestamp
    updated_at: WireTimestamp | None = None
    message_count: Annotated[int | None, BeforeValidator(_wire_count)] = None
    last_snippet: str | None = None


class ChatMessageWire(WireModel):
    id: WireId
    conversation_id: WireId
    role: Literal["user", "assistant", "system"]
    content: str
    plan_trace: Any = None
    reflection_summary: Any = None
    created_at: WireTimestamp


class ChatHistoryResponseWire(WireModel):
    conversations: list[ChatConversationWire]


class ChatConversationDetailWire(WireModel):
    conversation: ChatConversationWire
    messages: list[ChatMessageWire]


# Wire Schemas matching packages/contracts/src/agent.ts (SSE payloads, not routes)


class PlanStepWire(WireModel):
    step_number: int
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    tool: str | None = None


class CitationWire(WireModel):
    """A source shown to the model. The answer cites it inline as `[label]`, e.g. `[S1]`."""

    id: str
    label: str
    chunk_id: str
    document_id: str
    filename: str
    start_line: int | None = None
    end_line: int | None = None
    header_path: list[str]
    preview: str


class InjectionWarningWire(WireModel):
    """Retrieved text that looks like instructions (kept inside untrusted delimiters, but reported)."""

    filename: str
    reason: str


class SseStartEvent(BaseModel):
    sessionId: str
    query: str
    timestamp: str
    quotaRemaining: int | None = None


class SseNodeStartEvent(BaseModel):
    sessionId: str
    node: str


class SsePlanEvent(BaseModel):
    sessionId: str
    plan: list[PlanStepWire]


class RetrievalToolArguments(BaseModel):
    """What the agent passes to `hybrid_rag_search`; the same values the tool audit log records."""

    query: str
    limit: int
    documentScoped: bool


class SseToolCallEvent(BaseModel):
    """Sent just before a tool runs. The matching `tool_result` follows when it finishes."""

    sessionId: str
    tool: Literal["hybrid_rag_search"]
    arguments: RetrievalToolArguments


class SseToolResultEvent(BaseModel):
    tool: str
    chunksRetrieved: int
    citations: list[CitationWire]
    injectionWarnings: list[InjectionWarningWire]


class SseGroundingEvent(BaseModel):
    sessionId: str
    grounding: Literal["grounded", "weak", "none"]
    feedback: str | None = None


class SseTokenEvent(BaseModel):
    """One chunk of model output (or the fixed out-of-scope refusal, sent as a single chunk)."""

    sessionId: str
    token: str


class SseRedactEvent(BaseModel):
    """Replace everything streamed so far with ``response`` (sent after a canary-token leak)."""

    sessionId: str
    response: str


class SseErrorEvent(BaseModel):
    sessionId: str
    error: str


class AgentDoneEventWire(BaseModel):
    """Payload of the final `done` SSE event. The answer text itself arrives as `token` events."""

    sessionId: str
    conversationId: str | None = None
    query: str
    nodeHistory: list[str]
    plan: list[PlanStepWire]
    citations: list[CitationWire]
    injectionWarnings: list[InjectionWarningWire]
    mermaidDiagrams: list[str]
    grounding: Literal["grounded", "weak", "none"]
    model: str | None = None
    isComplete: bool
    completedAt: str | None = None


# Models that never appear in a route signature but are part of the wire contract.
SSE_WIRE_MODELS: list[type[BaseModel]] = [
    SseStartEvent,
    SseNodeStartEvent,
    SsePlanEvent,
    SseToolCallEvent,
    SseToolResultEvent,
    SseGroundingEvent,
    SseTokenEvent,
    SseRedactEvent,
    SseErrorEvent,
    AgentDoneEventWire,
]

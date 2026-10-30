from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    client_ip: str | None = None
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
        if hasattr(v, "to_numpy"):
            return [float(x) for x in v.to_numpy().tolist()]
        try:
            return [float(x) for x in v]
        except TypeError, ValueError:
            return v


# Wire Schemas matching packages/contracts/src/auth.ts


class UserSession(BaseModel):
    id: str
    email: str | None = None
    name: str
    avatarUrl: str | None = None
    isGuest: bool
    createdAt: str
    lastSeenAt: str


class GuestPassRequest(BaseModel):
    deviceId: str | None = None


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


class DocumentMetadataWire(BaseModel):
    id: str
    userId: str | None = None
    filename: str
    mimeType: str
    sha256Hash: str
    totalChunks: int
    isSeeded: bool
    uploadedAt: str


class DocumentChunkWire(BaseModel):
    id: str
    documentId: str
    chunkIndex: int
    content: str
    metadata: dict[str, Any]
    createdAt: str


class DocumentUploadResponseWire(BaseModel):
    document: DocumentMetadataWire
    chunksCount: int
    previewChunks: list[DocumentChunkWire]
    quotaRemaining: int | None = None


class DocumentListResponseWire(BaseModel):
    documents: list[DocumentMetadataWire]


class DocumentChunksResponseWire(BaseModel):
    chunks: list[DocumentChunkWire]


class MeResponse(BaseModel):
    user: UserSession
    quota: QuotaStatus


class SuccessResponse(BaseModel):
    success: bool
    id: str | None = None


# Wire Schemas matching packages/contracts/src/chat.ts


class ChatConversationWire(BaseModel):
    id: str
    userId: str
    title: str
    createdAt: str
    updatedAt: str | None = None
    messageCount: int | None = None
    lastSnippet: str | None = None


class ChatMessageWire(BaseModel):
    id: str
    conversationId: str
    role: Literal["user", "assistant", "system"]
    content: str
    planTrace: Any = None
    reflectionSummary: Any = None
    createdAt: str


class ChatHistoryResponseWire(BaseModel):
    conversations: list[ChatConversationWire]
    total: int


class ChatConversationDetailWire(BaseModel):
    conversation: ChatConversationWire
    messages: list[ChatMessageWire]


# Wire Schemas matching packages/contracts/src/agent.ts (SSE payloads, not routes)


class PlanStepWire(BaseModel):
    stepNumber: int
    description: str
    status: Literal["pending", "in_progress", "completed", "failed"]
    tool: str | None = None


class CitationWire(BaseModel):
    """A source shown to the model. The answer cites it inline as `[label]`, e.g. `[S1]`."""

    id: str
    label: str
    chunkId: str
    documentId: str
    filename: str
    startLine: int | None = None
    endLine: int | None = None
    headerPath: list[str]
    preview: str


class InjectionWarningWire(BaseModel):
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
    isComplete: bool
    completedAt: str | None = None


# Models that never appear in a route signature but are part of the wire contract.
SSE_WIRE_MODELS: list[type[BaseModel]] = [
    SseStartEvent,
    SseNodeStartEvent,
    SsePlanEvent,
    SseToolResultEvent,
    SseGroundingEvent,
    SseTokenEvent,
    SseRedactEvent,
    SseErrorEvent,
    AgentDoneEventWire,
]

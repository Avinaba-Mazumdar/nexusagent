from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class User(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    email: str | None = None
    hashed_password: str | None = None
    name: str = "Guest Reviewer"
    avatar_url: str | None = None
    is_guest: bool = True
    client_ip: str | None = None
    device_id: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)


class RateLimitBucket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    client_ip: str
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
    storage_path: str | None = None
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
    resetMinutes: int


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
    storagePath: str | None = None
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

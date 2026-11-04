"""Wire models build straight from ORM-style objects and row dicts, and serialise as camelCase.

These replaced hand-written mapper functions in the routes, so they pin the output shape the
contracts package depends on.
"""

from datetime import UTC, datetime
from uuid import UUID

from app.db.models import (
    ChatConversationWire,
    ChatMessageWire,
    Document,
    DocumentChunk,
    DocumentChunkWire,
    DocumentMetadataWire,
    DocumentUploadResponseWire,
    User,
    UserSession,
)

NOW = datetime(2026, 11, 1, 12, 30, tzinfo=UTC)
USER_ID = UUID("11111111-1111-4111-8111-111111111111")
DOC_ID = UUID("22222222-2222-4222-8222-222222222222")
CHUNK_ID = UUID("33333333-3333-4333-8333-333333333333")


def test_user_session_uses_string_ids_and_iso_timestamps():
    user = User(
        id=USER_ID,
        email="ada@example.com",
        name="Ada",
        is_guest=False,
        created_at=NOW,
        last_seen_at=NOW,
    )

    dumped = UserSession.model_validate(user).model_dump(by_alias=True)

    assert dumped == {
        "id": str(USER_ID),
        "email": "ada@example.com",
        "name": "Ada",
        "avatarUrl": None,
        "isGuest": False,
        "isAdmin": False,
        "createdAt": NOW.isoformat(),
        "lastSeenAt": NOW.isoformat(),
    }


def test_document_metadata_is_built_from_the_document_object():
    doc = Document(
        id=DOC_ID,
        uploaded_by=USER_ID,
        filename="rfc.md",
        mime_type="text/markdown",
        sha256_hash="ab" * 32,
        total_chunks=3,
        is_seeded=False,
        uploaded_at=NOW,
    )

    dumped = DocumentMetadataWire.model_validate(doc).model_dump(by_alias=True)

    assert dumped == {
        "id": str(DOC_ID),
        "uploadedBy": str(USER_ID),
        "filename": "rfc.md",
        "mimeType": "text/markdown",
        "sha256Hash": "ab" * 32,
        "totalChunks": 3,
        "isSeeded": False,
        "uploadedAt": NOW.isoformat(),
    }


def test_upload_response_nests_camel_case_document_and_chunks():
    doc = Document(
        id=DOC_ID,
        uploaded_by=USER_ID,
        filename="rfc.md",
        sha256_hash="cd" * 32,
        total_chunks=1,
        uploaded_at=NOW,
    )
    chunk = DocumentChunk(
        id=CHUNK_ID,
        document_id=DOC_ID,
        chunk_index=0,
        content="Quorum is a majority.",
        metadata={"startLine": 1},
        created_at=NOW,
    )

    response = DocumentUploadResponseWire(
        document=DocumentMetadataWire.model_validate(doc),
        chunks_count=1,
        preview_chunks=[DocumentChunkWire.model_validate(chunk)],
        quota_remaining=4,
    ).model_dump(by_alias=True)

    assert set(response) == {"document", "chunksCount", "previewChunks", "quotaRemaining"}
    assert response["previewChunks"] == [
        {
            "id": str(CHUNK_ID),
            "documentId": str(DOC_ID),
            "chunkIndex": 0,
            "content": "Quorum is a majority.",
            "metadata": {"startLine": 1},
            "createdAt": NOW.isoformat(),
        }
    ]


def test_conversation_without_a_message_count_reports_zero():
    row = {
        "id": DOC_ID,
        "user_id": USER_ID,
        "title": "Raft",
        "created_at": NOW,
        "updated_at": None,
        "message_count": None,
        "last_snippet": None,
    }

    dumped = ChatConversationWire.model_validate(row).model_dump(by_alias=True)

    assert dumped == {
        "id": str(DOC_ID),
        "userId": str(USER_ID),
        "title": "Raft",
        "createdAt": NOW.isoformat(),
        "updatedAt": None,
        "messageCount": 0,
        "lastSnippet": None,
    }


def test_message_keeps_its_trace_payloads_as_given():
    row = {
        "id": CHUNK_ID,
        "conversation_id": DOC_ID,
        "role": "assistant",
        "content": "Answer [S1].",
        "plan_trace": [{"stepNumber": 1}],
        "reflection_summary": None,
        "created_at": NOW,
    }

    dumped = ChatMessageWire.model_validate(row).model_dump(by_alias=True)

    assert dumped["conversationId"] == str(DOC_ID)
    assert dumped["planTrace"] == [{"stepNumber": 1}]
    assert dumped["reflectionSummary"] is None
    assert dumped["createdAt"] == NOW.isoformat()

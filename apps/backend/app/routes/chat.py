"""Seeded knowledge-base listing and Chat History endpoints for Google-authenticated users."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.auth import get_current_user
from app.db.models import User
from app.db.neon import NeonDatabase, get_db

router = APIRouter(prefix="/chat", tags=["Chat History & Seeded Knowledge Base"])


class CreateConversationRequestWire(BaseModel):
    title: str = Field(default="New Architectural Inquiry", max_length=255)


def ensure_google_user(current_user: User) -> None:
    """Enforce that chat history is strictly gated to verified non-guest Google accounts."""
    if current_user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat history is exclusively available for authenticated Google accounts.",
        )


@router.get("/documents")
async def list_seeded_documents(db: NeonDatabase = Depends(get_db)):
    """Return pre-indexed benchmark documents available for RAG."""
    docs = await db.get_seeded_documents()
    return {"documents": docs}


@router.get("/history")
async def list_chat_history(
    q: str | None = Query(None, description="Optional search query across conversation titles and message content"),
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """List persistent conversations for authenticated Google user."""
    ensure_google_user(current_user)
    conversations = await db.list_conversations(current_user.id, search_term=q, limit=limit)
    formatted = [
        {
            "id": str(c["id"]),
            "userId": str(c["user_id"]),
            "title": c["title"],
            "createdAt": c["created_at"].isoformat() if hasattr(c["created_at"], "isoformat") else str(c["created_at"]),
            "messageCount": int(c.get("message_count") or 0),
            "lastSnippet": c.get("last_snippet"),
        }
        for c in conversations
    ]
    return {"conversations": formatted, "total": len(formatted)}


@router.post("/history", status_code=status.HTTP_201_CREATED)
async def create_chat_conversation(
    payload: CreateConversationRequestWire,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Explicitly create a new conversation thread."""
    ensure_google_user(current_user)
    conv = await db.create_conversation(current_user.id, title=payload.title, conversation_id=None)
    return {
        "id": str(conv["id"]),
        "userId": str(conv["user_id"]),
        "title": conv["title"],
        "createdAt": conv["created_at"].isoformat() if hasattr(conv["created_at"], "isoformat") else str(conv["created_at"]),
        "messageCount": 0,
        "lastSnippet": None,
    }


@router.get("/history/{conversation_id}")
async def get_chat_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Fetch complete message history for a conversation."""
    ensure_google_user(current_user)
    conv, messages = await db.get_conversation_with_messages(current_user.id, conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized.",
        )

    formatted_messages = [
        {
            "id": str(m["id"]),
            "conversationId": str(m["conversation_id"]),
            "role": m["role"],
            "content": m["content"],
            "planTrace": m.get("plan_trace"),
            "reflectionSummary": m.get("reflection_summary"),
            "createdAt": m["created_at"].isoformat() if hasattr(m["created_at"], "isoformat") else str(m["created_at"]),
        }
        for m in messages
    ]
    return {
        "conversation": {
            "id": str(conv["id"]),
            "userId": str(conv["user_id"]),
            "title": conv["title"],
            "createdAt": conv["created_at"].isoformat() if hasattr(conv["created_at"], "isoformat") else str(conv["created_at"]),
        },
        "messages": formatted_messages,
    }


@router.delete("/history/{conversation_id}")
async def delete_chat_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """Delete a conversation and its messages."""
    ensure_google_user(current_user)
    deleted = await db.delete_conversation(current_user.id, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or unauthorized.",
        )
    return {"success": True, "id": str(conversation_id)}

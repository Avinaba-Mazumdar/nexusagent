"""Chat History endpoints for Google-authenticated users."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_user
from app.db.models import (
    ChatConversationDetailWire,
    ChatHistoryResponseWire,
    SuccessResponse,
    User,
)
from app.db.neon import NeonDatabase, get_db

router = APIRouter(prefix="/chat", tags=["Chat History"])


def ensure_google_user(current_user: User) -> None:
    """Enforce that chat history is strictly gated to verified non-guest Google accounts."""
    if current_user.is_guest:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Chat history is exclusively available for authenticated Google accounts.",
        )


def conversation_to_wire(c: dict) -> dict:
    return {
        "id": str(c["id"]),
        "userId": str(c["user_id"]),
        "title": c["title"],
        "createdAt": c["created_at"].isoformat(),
        "updatedAt": c["updated_at"].isoformat() if c.get("updated_at") else None,
        "messageCount": int(c.get("message_count") or 0),
        "lastSnippet": c.get("last_snippet"),
    }


def message_to_wire(m: dict) -> dict:
    return {
        "id": str(m["id"]),
        "conversationId": str(m["conversation_id"]),
        "role": m["role"],
        "content": m["content"],
        "planTrace": m.get("plan_trace"),
        "reflectionSummary": m.get("reflection_summary"),
        "createdAt": m["created_at"].isoformat(),
    }


@router.get("/history", response_model=ChatHistoryResponseWire)
async def list_chat_history(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: NeonDatabase = Depends(get_db),
):
    """List persistent conversations for authenticated Google user."""
    ensure_google_user(current_user)
    conversations = await db.list_conversations(current_user.id, limit=limit)
    return {"conversations": [conversation_to_wire(c) for c in conversations]}


@router.get("/history/{conversation_id}", response_model=ChatConversationDetailWire)
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

    return {
        "conversation": conversation_to_wire(conv),
        "messages": [message_to_wire(m) for m in messages],
    }


@router.delete("/history/{conversation_id}", response_model=SuccessResponse)
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

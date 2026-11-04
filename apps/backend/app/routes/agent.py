from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import AgentGraph, default_agent_graph, prefilter
from app.agent.run import AgentRun
from app.agent.state import Intent
from app.config import settings
from app.core.access import require_document_access
from app.core.audit_log import default_audit_logger
from app.core.auth import get_client_ip, get_current_user
from app.core.rate_limiter import default_chat_quota
from app.db.models import User
from app.db.neon import neon_db

router = APIRouter(prefix="/agent", tags=["Agent Autonomous Orchestration & SSE Streaming"])


class AgentStreamRequestWire(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language prompt or benchmark question for autonomous agent",
    )
    documentId: str | None = Field(
        None,
        description="Optional document UUID filter to scope retrieval to a specific document",
    )
    sessionId: str | None = Field(
        None,
        description="Optional existing session ID for conversation continuity",
    )


def generate_agent_stream(
    query: str,
    intent: Intent,
    user_id: UUID | None,
    document_id: UUID | None,
    session_id: str,
    graph: AgentGraph,
    is_guest: bool = True,
    quota_remaining: int | None = None,
    quota_charged: bool = True,
    chat_history: list[dict[str, str]] | None = None,
    conversation_id: UUID | None = None,
    usage_id: UUID | None = None,
) -> AsyncIterator[str]:
    """SSE frames for one agent run; the event order is documented on ``AgentRun``."""
    return AgentRun(
        query=query,
        intent=intent,
        user_id=user_id,
        document_id=document_id,
        session_id=session_id,
        graph=graph,
        is_guest=is_guest,
        quota_remaining=quota_remaining,
        quota_charged=quota_charged,
        chat_history=chat_history,
        conversation_id=conversation_id,
        usage_id=usage_id,
    ).frames()


@router.post("/stream")
async def stream_agent_execution(
    payload: AgentStreamRequestWire,
    request: Request,
    current_user: User = Depends(get_current_user),
    graph: AgentGraph = Depends(lambda: default_agent_graph),
):
    """
    Server-Sent Events (SSE) streaming endpoint for the agent pipeline.
    Enforces the rolling 24-hour chat quota with automatic 429 and retry headers.
    """
    client_ip = get_client_ip(request)

    doc_uuid: UUID | None = None
    if payload.documentId:
        try:
            doc_uuid = UUID(payload.documentId)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid documentId UUID format",
            )
        await require_document_access(neon_db, doc_uuid)

    session_id = uuid4().hex
    chat_history: list[dict[str, str]] = []
    resumed_conversation: UUID | None = None
    if payload.sessionId and not current_user.is_guest:
        try:
            requested = UUID(payload.sessionId)
        except ValueError:
            requested = None
        if requested:
            rows = await neon_db.get_conversation_history(
                current_user.id, requested, settings.CHAT_HISTORY_MESSAGES
            )
            if rows is not None:
                session_id = payload.sessionId
                resumed_conversation = requested
                chat_history = [{"role": r["role"], "content": r["content"]} for r in rows]

    # Prefilter refusals cost nothing and are not metered; router refusals are metered.
    if prefilter(payload.query):
        intent: Intent | None = "refuse"
        quota_charged = False
        usage_id: UUID | None = None
        remaining, _ = await default_chat_quota.status(current_user, client_ip)
    else:
        intent = None
        quota_charged = True
        usage_id, remaining = await default_chat_quota.reserve(current_user, client_ip)

    return StreamingResponse(
        generate_agent_stream(
            query=payload.query,
            intent=intent,
            user_id=current_user.id,
            document_id=doc_uuid,
            session_id=session_id,
            graph=graph,
            is_guest=current_user.is_guest,
            quota_remaining=remaining,
            quota_charged=quota_charged,
            chat_history=chat_history,
            conversation_id=resumed_conversation,
            usage_id=usage_id,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/audit-logs")
async def get_tool_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the caller's persisted tool execution audit records (``tool_audit_logs``)."""
    logs = await default_audit_logger.fetch_audit_logs_from_db(user_id=current_user.id, limit=limit)
    return {"logs": logs, "count": len(logs)}

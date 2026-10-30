"""
Model Context Protocol HTTP & SSE endpoints.
Provides:
  - GET /mcp/sse: SSE connection initialization for Claude Desktop & external agents
  - POST /mcp/messages: Inbound JSON-RPC 2.0 message handler for active SSE sessions
  - POST /mcp/v1: Direct HTTP JSON-RPC 2.0 gateway
"""

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import ValidationError

from app.core.auth import get_client_ip, get_current_user
from app.db.models import User
from app.mcp.dispatch import dispatch_mcp_method
from app.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)

logger = logging.getLogger("nexusagent.routes.mcp")

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol"])


# Active SSE sessions: sessionId -> McpSession
@dataclass
class McpSession:
    owner_id: UUID
    queue: asyncio.Queue[str]


SESSIONS: dict[str, McpSession] = {}
MAX_SESSIONS_PER_USER = 3
MAX_SESSIONS_TOTAL = 200
MAX_QUEUED_MESSAGES = 100


@router.post("/v1", response_model=None)
async def direct_jsonrpc_gateway(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> JsonRpcResponse | Response:
    """
    Direct HTTP JSON-RPC 2.0 gateway accepting tools/list, tools/call, and resources/list.
    Requires authentication: tools/call reaches the production database.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError, ValueError:
        return JsonRpcResponse(
            id=None,
            error=JsonRpcError(code=-32700, message="Parse error"),
        )

    try:
        req = JsonRpcRequest.model_validate(body)
    except ValidationError, ValueError, TypeError:
        return JsonRpcResponse(
            id=body.get("id") if isinstance(body, dict) else None,
            error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request"),
        )

    client_ip = get_client_ip(request)

    if req.id is None:
        await dispatch_mcp_method(req, user=current_user, client_ip=client_ip)
        return Response(status_code=202)

    try:
        return await dispatch_mcp_method(req, user=current_user, client_ip=client_ip)
    except Exception:
        logger.exception("Unexpected error in direct MCP gateway")
        return JsonRpcResponse(
            id=req.id,
            error=JsonRpcError(code=INTERNAL_ERROR, message="Internal error"),
        )


@router.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """
    MCP Server-Sent Events (SSE) stream initialization.
    Complies with MCP transport specification: emits 'endpoint' event with target URL for POST messages.
    Requires authentication: MCP clients reach the production database via these routes.
    """
    user_sessions_count = sum(1 for s in SESSIONS.values() if s.owner_id == current_user.id)
    if user_sessions_count >= MAX_SESSIONS_PER_USER or len(SESSIONS) >= MAX_SESSIONS_TOTAL:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many open MCP sessions",
            headers={"Retry-After": "60"},
        )

    session_id = uuid4().hex
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=MAX_QUEUED_MESSAGES)
    SESSIONS[session_id] = McpSession(owner_id=current_user.id, queue=queue)

    async def event_generator() -> AsyncGenerator[str]:
        try:
            # Standard MCP endpoint event pointing to the message handler
            endpoint_url = f"/api/mcp/messages?sessionId={session_id}"
            yield f"event: endpoint\ndata: {endpoint_url}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                # Wait for next JSON-RPC payload pushed to this session queue
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"event: message\ndata: {msg}\n\n"
                except TimeoutError:
                    if await request.is_disconnected():
                        break
                    yield ": ping\n\n"
        finally:
            SESSIONS.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _enqueue(queue: asyncio.Queue[str], response: JsonRpcResponse) -> None:
    """Push a response frame to the session's SSE stream, or 429 when the client is not reading."""
    try:
        queue.put_nowait(response.model_dump_json(exclude_none=True))
    except asyncio.QueueFull:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="MCP session queue full",
        )


@router.post("/messages")
async def mcp_messages_endpoint(
    request: Request,
    sessionId: str = Query(..., description="Active MCP SSE session ID"),
    current_user: User = Depends(get_current_user),
):
    """
    Inbound JSON-RPC 2.0 message handler for active SSE client sessions.
    Pushes response frame to client's SSE stream.
    """
    session = SESSIONS.get(sessionId)
    if not session or session.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session ID not found or SSE stream disconnected.",
        )
    queue = session.queue

    try:
        body = await request.json()
        req = JsonRpcRequest.model_validate(body)
    except json.JSONDecodeError, ValidationError, ValueError, TypeError:
        _enqueue(
            queue,
            JsonRpcResponse(
                id=None, error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request")
            ),
        )
        return JSONResponse(status_code=202, content={"status": "accepted"})

    client_ip = get_client_ip(request)

    try:
        res = await dispatch_mcp_method(req, user=current_user, client_ip=client_ip)
    except Exception:
        logger.exception("Error processing SSE message")
        res = JsonRpcResponse(
            id=req.id, error=JsonRpcError(code=INTERNAL_ERROR, message="Internal error")
        )

    # Notifications (no id) get no response frame. Enqueued outside the try so a full queue is a 429.
    if req.id is not None:
        _enqueue(queue, res)
    return JSONResponse(status_code=202, content={"status": "accepted"})

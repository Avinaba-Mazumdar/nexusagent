"""
Model Context Protocol (MCP v2) HTTP & SSE endpoints.
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

from app.core.auth import get_current_user
from app.db.models import User
from app.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)
from app.mcp.registry import default_mcp_registry

logger = logging.getLogger("nexusagent.routes.mcp")

router = APIRouter(prefix="/mcp", tags=["Model Context Protocol (MCP v2)"])

# Active SSE sessions: sessionId -> McpSession
@dataclass
class McpSession:
    owner_id: UUID
    queue: asyncio.Queue[str]


SESSIONS: dict[str, McpSession] = {}
MAX_SESSIONS_PER_USER = 3
MAX_SESSIONS_TOTAL = 200
MAX_QUEUED_MESSAGES = 100


async def dispatch_mcp_method(req: JsonRpcRequest, user_id: UUID | None = None) -> JsonRpcResponse:
    """Core dispatcher for JSON-RPC 2.0 MCP requests."""
    method = req.method
    params = req.params or {}

    if method == "initialize":
        return JsonRpcResponse(
            id=req.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False, "subscribe": False},
                },
                "serverInfo": {
                    "name": "nexusagent-mcp",
                    "version": "0.1.0",
                },
            },
        )

    elif method == "notifications/initialized" or method == "ping":
        return JsonRpcResponse(id=req.id, result={})

    elif method == "tools/list":
        tools = default_mcp_registry.get_tools()
        return JsonRpcResponse(id=req.id, result={"tools": tools})

    elif method == "tools/call":
        tool_name = params.get("name")
        tool_args = params.get("arguments", {})
        if not tool_name:
            return JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=INVALID_PARAMS, message="Missing parameter 'name'."),
            )

        call_res = await default_mcp_registry.call_tool(tool_name, tool_args, user_id=user_id)
        return JsonRpcResponse(id=req.id, result=call_res.model_dump())

    elif method == "resources/list":
        resources = default_mcp_registry.get_resources()
        return JsonRpcResponse(id=req.id, result={"resources": resources})

    elif method == "resources/read":
        uri = params.get("uri")
        if not uri:
            return JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=INVALID_PARAMS, message="Missing parameter 'uri'."),
            )

        try:
            read_res = await default_mcp_registry.read_resource(uri)
            return JsonRpcResponse(id=req.id, result=read_res)
        except ValueError:
            return JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=INVALID_PARAMS, message="Unknown resource"),
            )

    else:
        return JsonRpcResponse(
            id=req.id,
            error=JsonRpcError(code=METHOD_NOT_FOUND, message=f"Method '{method}' not found."),
        )


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
    except (json.JSONDecodeError, ValueError):
        return JsonRpcResponse(
            id=None,
            error=JsonRpcError(code=-32700, message="Parse error"),
        )

    try:
        req = JsonRpcRequest.model_validate(body)
    except (ValidationError, ValueError, TypeError):
        return JsonRpcResponse(
            id=body.get("id") if isinstance(body, dict) else None,
            error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request"),
        )

    if req.id is None:
        await dispatch_mcp_method(req, user_id=current_user.id)
        return Response(status_code=202)

    try:
        return await dispatch_mcp_method(req, user_id=current_user.id)
    except Exception:
        logger.exception("Unexpected error in direct MCP gateway")
        return JsonRpcResponse(
            id=req.id,
            error=JsonRpcError(code=INTERNAL_ERROR, message="Internal error"),
        )


@router.get("/sse")
async def mcp_sse_endpoint(
    request: Request,
    once: bool = False,
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
        # 1. Emit the standard MCP endpoint event pointing to the message handler
        endpoint_url = f"/api/mcp/messages?sessionId={session_id}"
        yield f"event: endpoint\ndata: {endpoint_url}\n\n"

        if once:
            SESSIONS.pop(session_id, None)
            return

        try:
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
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError):
        err_res = JsonRpcResponse(
            id=None,
            error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request"),
        )
        try:
            queue.put_nowait(err_res.model_dump_json(exclude_none=True))
        except asyncio.QueueFull:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="MCP session queue full",
            )
        return JSONResponse(status_code=202, content={"status": "accepted"})

    try:
        res = await dispatch_mcp_method(req, user_id=current_user.id)
        if req.id is not None:
            try:
                queue.put_nowait(res.model_dump_json(exclude_none=True))
            except asyncio.QueueFull:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="MCP session queue full",
                )
        return JSONResponse(status_code=202, content={"status": "accepted"})
    except Exception:
        logger.exception("Error processing SSE message")
        err_res = JsonRpcResponse(
            id=req.id,
            error=JsonRpcError(code=INTERNAL_ERROR, message="Internal error"),
        )
        if req.id is not None:
            try:
                queue.put_nowait(err_res.model_dump_json(exclude_none=True))
            except asyncio.QueueFull:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="MCP session queue full",
                )
        return JSONResponse(status_code=202, content={"status": "accepted"})

from fastapi import HTTPException

from app.core.rate_limiter import default_rate_limiter
from app.db.models import User
from app.mcp.protocol import (
    INVALID_PARAMS,
    METHOD_NOT_FOUND,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)
from app.mcp.registry import InvalidToolArguments, default_mcp_registry


async def dispatch_mcp_method(
    req: JsonRpcRequest,
    user: User | None = None,
    client_ip: str | None = None,
) -> JsonRpcResponse:
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

        try:
            default_mcp_registry.validate_arguments(tool_name, tool_args)
        except InvalidToolArguments as exc:
            return JsonRpcResponse(
                id=req.id, error=JsonRpcError(code=INVALID_PARAMS, message=str(exc))
            )

        if user is not None:
            try:
                await default_rate_limiter.check_and_consume(
                    user_id=user.id,
                    client_ip=client_ip or "127.0.0.1",
                    is_guest=user.is_guest,
                )
            except HTTPException as exc:
                if exc.status_code == 429:
                    return JsonRpcResponse(
                        id=req.id,
                        error=JsonRpcError(
                            code=-32000,
                            message="Quota exhausted. It replenishes hourly.",
                        ),
                    )
                raise

        call_res = await default_mcp_registry.call_tool(
            tool_name, tool_args, user_id=user.id if user else None
        )
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

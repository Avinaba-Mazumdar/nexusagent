"""
MCP Stdio Transport CLI Server.
Allows external AI clients (Claude Desktop, Cursor, Antigravity) to connect via command line:
  python -m app.mcp.server
"""

import asyncio
import json
import logging
import sys

from pydantic import ValidationError

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

# Configure logging to stderr so stdio stdout remains pure JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("nexusagent.mcp.stdio")


async def handle_jsonrpc_request(req_dict: dict) -> dict:
    """Process incoming JSON-RPC 2.0 request dictionary and return response dictionary."""
    try:
        req = JsonRpcRequest.model_validate(req_dict)
    except (ValidationError, ValueError, TypeError):
        return JsonRpcResponse(
            id=req_dict.get("id"),
            error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request"),
        ).model_dump(exclude_none=True)

    method = req.method
    params = req.params or {}

    try:
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
            ).model_dump(exclude_none=True)

        elif method == "notifications/initialized":
            return {}

        elif method == "ping":
            return JsonRpcResponse(id=req.id, result={}).model_dump(exclude_none=True)

        elif method == "tools/list":
            tools = default_mcp_registry.get_tools()
            return JsonRpcResponse(id=req.id, result={"tools": tools}).model_dump(exclude_none=True)

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            if not tool_name:
                return JsonRpcResponse(
                    id=req.id,
                    error=JsonRpcError(code=INVALID_PARAMS, message="Missing parameter 'name'."),
                ).model_dump(exclude_none=True)

            call_res = await default_mcp_registry.call_tool(tool_name, tool_args)
            return JsonRpcResponse(id=req.id, result=call_res.model_dump()).model_dump(
                exclude_none=True
            )

        elif method == "resources/list":
            resources = default_mcp_registry.get_resources()
            return JsonRpcResponse(id=req.id, result={"resources": resources}).model_dump(
                exclude_none=True
            )

        elif method == "resources/read":
            uri = params.get("uri")
            if not uri:
                return JsonRpcResponse(
                    id=req.id,
                    error=JsonRpcError(code=INVALID_PARAMS, message="Missing parameter 'uri'."),
                ).model_dump(exclude_none=True)

            read_res = await default_mcp_registry.read_resource(uri)
            return JsonRpcResponse(id=req.id, result=read_res).model_dump(exclude_none=True)

        else:
            return JsonRpcResponse(
                id=req.id,
                error=JsonRpcError(code=METHOD_NOT_FOUND, message=f"Method '{method}' not found."),
            ).model_dump(exclude_none=True)

    except Exception:
        logger.exception("Error processing MCP method %s", method)
        return JsonRpcResponse(
            id=req.id,
            error=JsonRpcError(code=INTERNAL_ERROR, message="Internal error"),
        ).model_dump(exclude_none=True)


async def main():
    """Stdio main loop reading lines from stdin and writing JSON-RPC to stdout."""
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    loop = asyncio.get_running_loop()
    await loop.connect_read_pipe(lambda: protocol, sys.stdin)

    while True:
        line_bytes = await reader.readline()
        if not line_bytes:
            break

        line = line_bytes.decode("utf-8").strip()
        if not line:
            continue

        try:
            req_data = json.loads(line)
            res_data = await handle_jsonrpc_request(req_data)
            if res_data:  # Notifications might yield empty response
                sys.stdout.write(json.dumps(res_data) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            err_res = JsonRpcResponse(
                id=None,
                error=JsonRpcError(code=-32700, message=f"Parse Error: {e!s}"),
            ).model_dump(exclude_none=True)
            sys.stdout.write(json.dumps(err_res) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())

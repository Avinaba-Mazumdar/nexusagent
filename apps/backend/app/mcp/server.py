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

from app.mcp.dispatch import dispatch_mcp_method
from app.mcp.protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
)

# Configure logging to stderr so stdio stdout remains pure JSON-RPC
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("nexusagent.mcp.stdio")


async def handle_jsonrpc_request(req_dict: dict) -> dict:
    """Process incoming JSON-RPC 2.0 request dictionary and return response dictionary."""
    try:
        req = JsonRpcRequest.model_validate(req_dict)
    except ValidationError, ValueError, TypeError:
        return JsonRpcResponse(
            id=req_dict.get("id"),
            error=JsonRpcError(code=INVALID_REQUEST, message="Invalid Request"),
        ).model_dump(exclude_none=True)

    try:
        # Stdio server is a local, trusted process; calls are unmetered (user=None).
        resp = await dispatch_mcp_method(req)
        if req.id is None:
            return {}
        return resp.model_dump(exclude_none=True)
    except Exception:
        logger.exception("Error processing MCP method %s", req.method)
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
            if res_data and req_data.get("id") is not None:  # Notifications produce no response
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

"""
Model Context Protocol JSON-RPC 2.0 wire specifications.
Complies with official MCP protocol specifications (protocolVersion: 2024-11-05).
"""

from typing import Any

from pydantic import BaseModel, Field

# Standard JSON-RPC 2.0 Error Codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


class JsonRpcError(BaseModel):
    code: int
    message: str
    data: Any | None = None


class JsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    method: str
    params: dict[str, Any] | None = None


class JsonRpcResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str | int | None = None
    result: Any | None = None
    error: JsonRpcError | None = None


class ToolInputSchema(BaseModel):
    type: str = "object"
    properties: dict[str, Any] = Field(default_factory=dict)
    required: list[str] = Field(default_factory=list)


class ToolDefinition(BaseModel):
    name: str
    description: str
    inputSchema: ToolInputSchema


class ResourceDefinition(BaseModel):
    uri: str
    name: str
    description: str | None = None
    mimeType: str = "text/markdown"


class ToolCallContent(BaseModel):
    type: str = "text"
    text: str


class ToolCallResult(BaseModel):
    content: list[ToolCallContent]
    isError: bool = False

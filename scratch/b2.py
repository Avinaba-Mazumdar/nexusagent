from ed import rep

# documents.py: unused request param
rep(
    "app/routes/documents.py",
    "async def upload_document(\n    request: Request,\n    file:",
    "async def upload_document(\n    file:",
)

# main.py
rep(
    "app/main.py",
    """            "NexusAgent keeps abuse counters and MCP rate limits in process memory; "
            "run exactly one worker (see README).\"""",
    """            "NexusAgent keeps abuse counters and MCP rate limits in process memory; "
            + "run exactly one worker (see README).\"""",
)
rep("app/main.py", "async def lifespan(app: FastAPI):", "async def lifespan(_app: FastAPI) -> AsyncIterator[None]:")
rep(
    "app/main.py",
    "async def mcp_rate_limit_middleware(request: Request, call_next):",
    "async def mcp_rate_limit_middleware(\n    request: Request, call_next: Callable[[Request], Awaitable[Response]]\n) -> Response:",
)
rep("app/main.py", "from contextlib import asynccontextmanager\n", "from collections.abc import AsyncIterator, Awaitable, Callable\nfrom contextlib import asynccontextmanager\n")
rep("app/main.py", "from fastapi.responses import JSONResponse\n", "from fastapi.responses import JSONResponse, Response\n")

# run.py attribute annotations
rep("app/agent/run.py", "        self.state = AgentState(", "        self.state: AgentState = AgentState(")
rep(
    "app/agent/run.py",
    """        self._tokens_sent = False
        self._scrubber = StreamingScrubber()
        self._usage_sent = 0
        self._events_sent = 0""",
    """        self._tokens_sent: bool = False
        self._scrubber: StreamingScrubber = StreamingScrubber()
        self._usage_sent: int = 0
        self._events_sent: int = 0""",
)
rep(
    "app/agent/run.py",
    """                name = call.get("name", "")
                if name in TOOL_ARGS:
                    self._send(tool_call_frame(self.session_id, name, call.get("args") or {}))""",
    """                name = call["name"]
                if name in TOOL_ARGS:
                    self._send(tool_call_frame(self.session_id, name, call["args"]))""",
)

# state.py: typed tool calls, no Any
rep("app/agent/state.py", "from typing import Any, ClassVar, Literal\n", "from typing import ClassVar, Literal\n")
rep("app/agent/state.py", "from langchain_core.messages import AnyMessage\n", "from langchain_core.messages import AnyMessage\nfrom langchain_core.messages.tool import ToolCall\n")
rep("app/agent/state.py", "    arguments: dict[str, Any] = Field(default_factory=dict)", "    arguments: dict[str, object] = Field(default_factory=dict)")
rep("app/agent/state.py", "    pending_tool_calls: list[dict[str, Any]] = Field(default_factory=list)", "    pending_tool_calls: list[ToolCall] = Field(default_factory=list)")

# config.py
rep(
    "app/config.py",
    """                try:
                    return json.loads(v_str)
                except json.JSONDecodeError, TypeError, ValueError:
                    pass""",
    """                try:
                    parsed = cast(object, json.loads(v_str))
                except json.JSONDecodeError, TypeError, ValueError:
                    parsed = None
                if isinstance(parsed, list):
                    return [str(origin) for origin in cast(list[object], parsed)]""",
)
rep(
    "app/config.py",
    """        if isinstance(v, list):
            return [str(origin) for origin in v]""",
    """        if isinstance(v, list):
            return [str(origin) for origin in cast(list[object], v)]""",
)
rep(
    "app/config.py",
    """                f"TRUSTED_PROXY_HOPS must be between 0 and {MAX_TRUSTED_PROXY_HOPS} "
                "(Render = 1, Cloudflare in front of Render = 2).\"""",
    """                f"TRUSTED_PROXY_HOPS must be between 0 and {MAX_TRUSTED_PROXY_HOPS} "
                + "(Render = 1, Cloudflare in front of Render = 2).\"""",
)
rep(
    "app/config.py",
    """                "TRUSTED_PROXY_HOPS must be >= 1 outside development/test "
                "(Render = 1). With 0 every client shares the proxy's IP address.\"""",
    """                "TRUSTED_PROXY_HOPS must be >= 1 outside development/test "
                + "(Render = 1). With 0 every client shares the proxy's IP address.\"""",
)
# Settings fields are uppercase by convention, not constants: fill dev defaults via setattr.
rep(
    "app/config.py",
    """            self.CORS_ORIGINS = [
                *(o for o in local_origins if o not in self.CORS_ORIGINS),
                *self.CORS_ORIGINS,
            ]
            if not self.JWT_SECRET_KEY:
                self.JWT_SECRET_KEY = "nexusagent-local-dev-only-secret-not-for-production\"""",
    """            # Settings fields are uppercase by convention, not constants, so the dev defaults
            # are filled in with setattr (plain assignment reads as a constant redefinition).
            origins = [
                *(o for o in local_origins if o not in self.CORS_ORIGINS),
                *self.CORS_ORIGINS,
            ]
            setattr(self, "CORS_ORIGINS", origins)
            if not self.JWT_SECRET_KEY:
                setattr(self, "JWT_SECRET_KEY", "nexusagent-local-dev-only-secret-not-for-production")""",
)
rep("app/config.py", "    model_config = SettingsConfigDict(", "    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(")
rep("app/config.py", "from pathlib import Path\n", "from pathlib import Path\nfrom typing import ClassVar, cast\n")
print("ok")

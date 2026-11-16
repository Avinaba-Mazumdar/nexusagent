import re

from ed import ROOT, rep

S = "app/agent/sse.py"
rep(
    S,
    '''def tool_call_frame(session_id: str, tool: str, arguments: dict[str, Any]) -> str:
    """Announce a tool call before it runs; its `tool_result` follows when it finishes."""
    return format_sse(
        "tool_call",
        SseToolCallEvent(
            sessionId=session_id,
            tool=tool,  # type: ignore
            arguments=arguments,
        ),
    )''',
    '''def tool_call_frame(session_id: str, tool: str, arguments: Mapping[str, object]) -> str:
    """Announce a tool call before it runs; its `tool_result` follows when it finishes."""
    # Validation checks ``tool`` against the event's literal set of tool names.
    event = SseToolCallEvent.model_validate(
        {"sessionId": session_id, "tool": tool, "arguments": dict(arguments)}
    )
    return format_sse("tool_call", event)''',
)
rep(S, "from typing import Any\n\n", "from collections.abc import Mapping\n\n")
# every local `frames = []` holds SSE frames
import os

p = os.path.join(ROOT, S)
raw = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
s = re.sub(r"(\n    )frames = \[\]\n", r"\1frames: list[str] = []\n", s)
s = s.replace("def _preload_frames(session_id: str, state: AgentState)", "def _preload_frames(state: AgentState)")
s = s.replace("frames.extend(_preload_frames(session_id, state))", "frames.extend(_preload_frames(state))")
s = s.replace("def _tools_frames(session_id: str, state: AgentState, events", "def _tools_frames(state: AgentState, events")
s = s.replace("frames.extend(_tools_frames(session_id, state, new_events))", "frames.extend(_tools_frames(state, new_events))")
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)

M = "app/mcp/server.py"
rep(M, "    result_data = {\n        \"results\": [", "    result_data: dict[str, object] = {\n        \"results\": [")
rep(M, "    result_data = {\n        \"id\": id,", "    result_data: dict[str, object] = {\n        \"id\": id,")

rep("app/config.py", "            self.__dict__.update(dev_defaults)", "            vars(self).update(dev_defaults)")
print("ok")

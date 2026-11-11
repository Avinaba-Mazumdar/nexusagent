"""Server-Sent Event framing for the agent stream.

Every frame the agent run sends is built here, so event names and payload shapes live in one
module. The payload models are in ``app.db.models`` and ``SSE_WIRE_MODELS`` exports them to the
contracts package.
"""

from collections.abc import Callable

from pydantic import BaseModel

from app.agent.graph import RETRIEVAL_LIMIT, RETRIEVAL_TOOL
from app.agent.state import AgentState
from app.db.models import (
    AgentDoneEventWire,
    CitationWire,
    InjectionWarningWire,
    PlanStepWire,
    SseErrorEvent,
    SseGroundingEvent,
    SseNodeStartEvent,
    SsePlanEvent,
    SseStartEvent,
    SseTokenEvent,
    SseToolCallEvent,
    SseToolResultEvent,
    SseUsageEvent,
    WebSourceWire,
)


def format_sse(event_type: str, payload: BaseModel) -> str:
    """Format a typed payload (see ``SSE_WIRE_MODELS``) as one Server-Sent Event frame."""
    return f"event: {event_type}\ndata: {payload.model_dump_json(by_alias=True)}\n\n"


# Frames the run sends around the graph.


def start_frame(session_id: str, query: str, created_at: str, quota_remaining: int | None) -> str:
    return format_sse(
        "start",
        SseStartEvent(
            sessionId=session_id,
            query=query,
            timestamp=created_at,
            quotaRemaining=quota_remaining,
        ),
    )


def node_start_frame(session_id: str, node: str) -> str:
    return format_sse("node_start", SseNodeStartEvent(sessionId=session_id, node=node))


def tool_call_frame(session_id: str, state: AgentState) -> str:
    """Announce the retrieval call before it runs; its `tool_result` follows when it finishes."""
    return format_sse(
        "tool_call",
        SseToolCallEvent(
            sessionId=session_id,
            tool=RETRIEVAL_TOOL,
            arguments={
                "query": state.query,
                "limit": RETRIEVAL_LIMIT,
                "documentScoped": state.document_id is not None,
            },
        ),
    )


def token_frame(session_id: str, text: str) -> str:
    """One chunk of model output (or the fixed refusal, sent as a single chunk)."""
    return format_sse("token", SseTokenEvent(sessionId=session_id, token=text))


def error_frame(session_id: str, error: str) -> str:
    return format_sse("error", SseErrorEvent(sessionId=session_id, error=error))


def usage_frames(session_id: str, state: AgentState, already_sent: int = 0) -> list[str]:
    """Frames for new usage records produced since ``already_sent``."""
    frames = []
    for u in state.usage[already_sent:]:
        frames.append(
            format_sse(
                "usage",
                SseUsageEvent(
                    sessionId=session_id,
                    step=u.step,
                    model=u.model,
                    inputTokens=u.input_tokens,
                    outputTokens=u.output_tokens,
                    totalTokens=u.total_tokens,
                ),
            )
        )
    return frames


def done_frame(
    session_id: str,
    conversation_id: str | None,
    query: str,
    state: AgentState,
    quota_remaining: int | None = None,
) -> str:
    return format_sse(
        "done",
        AgentDoneEventWire(
            sessionId=session_id,
            conversationId=conversation_id,
            query=query,
            nodeHistory=state.node_history,
            plan=[PlanStepWire.model_validate(s) for s in state.plan],
            citations=[CitationWire.model_validate(c) for c in state.citations],
            injectionWarnings=[
                InjectionWarningWire.model_validate(w) for w in state.injection_warnings
            ],
            webSources=[WebSourceWire(title=s.title, url=s.url) for s in state.web_sources],
            grounding=state.grounding,
            model=state.model,
            quotaRemaining=quota_remaining,
            isComplete=True,
            completedAt=state.completed_at.isoformat() if state.completed_at else None,
        ),
    )


# Frames a finished node reports.


def _router_frames(session_id: str, state: AgentState) -> list[str]:
    plan = [PlanStepWire.model_validate(s) for s in state.plan]
    return [format_sse("plan", SsePlanEvent(sessionId=session_id, plan=plan))]


def _chat_frames(session_id: str, state: AgentState) -> list[str]:
    frames = []
    if state.web_search_queries:
        frames.append(
            format_sse(
                "tool_call",
                SseToolCallEvent(
                    sessionId=session_id,
                    tool="google_search",
                    arguments={"queries": state.web_search_queries},
                ),
            )
        )
        frames.append(
            format_sse(
                "tool_result",
                SseToolResultEvent(
                    tool="google_search",
                    chunksRetrieved=len(state.web_sources),
                    citations=[],
                    injectionWarnings=[],
                    durationMs=state.search_duration_ms,
                ),
            )
        )
    return frames


def _retriever_frames(session_id: str, state: AgentState) -> list[str]:
    return [
        format_sse(
            "tool_result",
            SseToolResultEvent(
                tool=RETRIEVAL_TOOL,
                chunksRetrieved=len(state.retrieved_chunks),
                citations=[CitationWire.model_validate(c) for c in state.citations],
                injectionWarnings=[
                    InjectionWarningWire.model_validate(w) for w in state.injection_warnings
                ],
                durationMs=state.retrieval_duration_ms,
            ),
        )
    ]


def _grounding_frames(session_id: str, state: AgentState) -> list[str]:
    return [
        format_sse(
            "grounding",
            SseGroundingEvent(
                sessionId=session_id,
                grounding=state.grounding,
                feedback=state.grounding_feedback,
            ),
        )
    ]


_NODE_FRAMES: dict[str, Callable[[str, AgentState], list[str]]] = {
    "router": _router_frames,
    "chat": _chat_frames,
    "retriever": _retriever_frames,
    "grounding": _grounding_frames,
}


def node_frames(node: str, session_id: str, state: AgentState, usage_sent: int = 0) -> list[str]:
    """The frames a node reports when it finishes, including usage frames for LLM nodes."""
    frames = []
    builder = _NODE_FRAMES.get(node)
    if builder:
        frames.extend(builder(session_id, state))
    if node in {"router", "chat", "answer"}:
        frames.extend(usage_frames(session_id, state, already_sent=usage_sent))
    return frames

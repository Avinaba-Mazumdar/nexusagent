"""Server-Sent Event framing for the agent stream.

Every frame the agent run sends is built here, so event names and payload shapes live in one
module. The payload models are in ``app.db.models`` and ``SSE_WIRE_MODELS`` exports them to the
contracts package.
"""

from typing import Any

from pydantic import BaseModel

from app.agent.state import AgentState, ToolEvent
from app.agent.tools import RAG_TOOL_NAME, WEB_TOOL_NAME
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


def tool_call_frame(session_id: str, tool: str, arguments: dict[str, Any]) -> str:
    """Announce a tool call before it runs; its `tool_result` follows when it finishes."""
    return format_sse(
        "tool_call",
        SseToolCallEvent(
            sessionId=session_id,
            tool=tool,  # type: ignore
            arguments=arguments,
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
            invalidCitations=state.invalid_citations,
            uncited=state.uncited,
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
                    webSources=[WebSourceWire(title=s.title, url=s.url) for s in state.web_sources],
                    durationMs=state.search_duration_ms,
                ),
            )
        )
    return frames


def _preload_frames(session_id: str, state: AgentState) -> list[str]:
    frames = []
    first_event = state.tool_events[0] if state.tool_events else None
    duration_ms = first_event.duration_ms if first_event else state.retrieval_duration_ms
    frames.append(
        format_sse(
            "tool_result",
            SseToolResultEvent(
                tool=RAG_TOOL_NAME,
                chunksRetrieved=len(state.retrieved_chunks),
                citations=[CitationWire.model_validate(c) for c in state.citations],
                injectionWarnings=[
                    InjectionWarningWire.model_validate(w) for w in state.injection_warnings
                ],
                durationMs=duration_ms,
            ),
        )
    )
    frames.append(
        format_sse(
            "grounding",
            SseGroundingEvent(
                sessionId=session_id,
                grounding=state.grounding,
                feedback=state.grounding_feedback,
            ),
        )
    )
    return frames


def _tools_frames(session_id: str, state: AgentState, events: list[ToolEvent]) -> list[str]:
    frames = []
    for ev in events:
        citations = (
            [CitationWire.model_validate(c) for c in state.citations]
            if ev.tool == RAG_TOOL_NAME
            else []
        )
        web_sources = (
            [WebSourceWire(title=s.title, url=s.url) for s in state.web_sources]
            if ev.tool == WEB_TOOL_NAME
            else []
        )
        frames.append(
            format_sse(
                "tool_result",
                SseToolResultEvent(
                    tool=ev.tool,
                    chunksRetrieved=ev.results,
                    citations=citations,
                    injectionWarnings=[],
                    webSources=web_sources,
                    error=ev.error,
                    durationMs=ev.duration_ms,
                ),
            )
        )
    frames.append(
        format_sse(
            "grounding",
            SseGroundingEvent(
                sessionId=session_id,
                grounding=state.grounding,
                feedback=state.grounding_feedback,
            ),
        )
    )
    return frames


def node_frames(
    node: str,
    session_id: str,
    state: AgentState,
    usage_sent: int = 0,
    events_sent: int = 0,
) -> list[str]:
    """The frames a node reports when it finishes, including usage frames for LLM nodes."""
    frames = []
    if node == "router":
        frames.extend(_router_frames(session_id, state))
    elif node == "chat":
        frames.extend(_chat_frames(session_id, state))
    elif node == "preload":
        frames.extend(_preload_frames(session_id, state))
    elif node == "tools":
        new_events = state.tool_events[events_sent:]
        frames.extend(_tools_frames(session_id, state, new_events))

    if node in {"router", "chat", "agent", "tools"}:
        frames.extend(usage_frames(session_id, state, already_sent=usage_sent))
    return frames

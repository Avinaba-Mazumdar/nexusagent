import asyncio
import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import (
    AgentGraph,
    classify_query_intent,
    default_agent_graph,
    route_after_planner,
)
from app.agent.state import AgentState, Citation, InjectionWarning, PlanStep
from app.config import settings
from app.core.audit_log import default_audit_logger
from app.core.auth import get_client_ip, get_current_user
from app.core.rate_limiter import default_rate_limiter
from app.db.models import AgentDoneEventWire, User
from app.db.neon import neon_db
from app.routes.documents import require_document_access

logger = logging.getLogger("nexusagent.routes.agent")

router = APIRouter(prefix="/agent", tags=["Agent Autonomous Orchestration & SSE Streaming"])

TITLE_MAX_CHARS = 60


class AgentStreamRequestWire(BaseModel):
    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="Natural language prompt or architectural inquiry for autonomous agent",
    )
    documentId: str | None = Field(
        None,
        description="Optional document UUID filter to scope retrieval to a specific RFC/document",
    )
    sessionId: str | None = Field(
        None,
        description="Optional existing session ID for conversation continuity",
    )


def format_sse(event_type: str, data: dict) -> str:
    """Format structured payload into valid Server-Sent Event frame."""
    json_str = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_str}\n\n"


def plan_step_to_wire(s: PlanStep) -> dict:
    return {
        "stepNumber": s.step_number,
        "description": s.description,
        "status": s.status,
        "tool": s.tool,
    }


def citation_to_wire(c: Citation) -> dict:
    return {
        "id": c.id,
        "label": c.label,
        "chunkId": c.chunk_id,
        "documentId": c.document_id,
        "filename": c.filename,
        "startLine": c.start_line,
        "endLine": c.end_line,
        "headerPath": c.header_path,
        "preview": c.preview,
    }


def warning_to_wire(w: InjectionWarning) -> dict:
    return {"filename": w.filename, "reason": w.reason}


def next_node(finished: str, state: AgentState) -> str | None:
    """The node LangGraph runs after ``finished`` (the graph is a fixed pipeline)."""
    if finished == "planner":
        return route_after_planner(state)
    return {"retriever": "grounding", "grounding": "synthesizer"}.get(finished)


async def persist_turn(user_id: UUID, session_id: str, query: str, state: AgentState) -> str | None:
    """Save the turn for a signed-in user. Returns the conversation id, or None on failure."""
    try:
        title = query[:TITLE_MAX_CHARS] + "..." if len(query) > TITLE_MAX_CHARS else query
        conv = await neon_db.create_conversation(
            user_id, title=title, conversation_id=UUID(session_id)
        )
        if not conv or "id" not in conv:
            logger.warning(f"Could not persist conversation {session_id} for user {user_id}")
            return None
        await neon_db.save_turn(
            conv["id"],
            query,
            state.response,
            plan_trace=[plan_step_to_wire(s) for s in state.plan],
            reflection_summary={
                "grounding": state.grounding,
                "citations": [citation_to_wire(c) for c in state.citations],
                "mermaidDiagrams": state.mermaid_diagrams,
            },
        )
        return str(conv["id"])
    except Exception as save_err:  # noqa: BLE001
        logger.warning(f"Could not persist conversation history: {save_err}")
        return None


async def generate_agent_stream(
    query: str,
    user_id: UUID | None,
    document_id: UUID | None,
    session_id: str,
    graph: AgentGraph,
    is_guest: bool = True,
    quota_remaining: int | None = None,
    quota_charged: bool = True,
    chat_history: list[dict[str, str]] | None = None,
    conversation_id: UUID | None = None,
) -> AsyncIterator[str]:
    """
    Run the agent pipeline and yield SSE frames:
    start -> node_start / plan / tool_result / grounding -> token* -> done | error.
    """
    initial_state = AgentState(
        session_id=session_id,
        user_id=user_id,
        conversation_id=conversation_id,
        query=query,
        document_id=document_id,
        chat_history=chat_history or [],
        intent=classify_query_intent(query),
    )

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    start_payload: dict[str, str | int] = {
        "sessionId": session_id,
        "query": query,
        "timestamp": initial_state.created_at.isoformat(),
    }
    if quota_remaining is not None:
        start_payload["quotaRemaining"] = quota_remaining
    await event_queue.put(format_sse("start", start_payload))

    async def refund_if_charged() -> None:
        if user_id and quota_charged:
            try:
                await default_rate_limiter.refund(user_id=user_id, is_guest=is_guest)
            except Exception as refund_err:  # noqa: BLE001
                logger.warning(f"Could not refund rate limit token: {refund_err}")

    async def run_pipeline():
        tokens_sent = False

        async def on_token(text: str) -> None:
            nonlocal tokens_sent
            tokens_sent = True
            await event_queue.put(format_sse("token", {"sessionId": session_id, "token": text}))

        try:
            final_state = initial_state
            await event_queue.put(
                format_sse("node_start", {"node": "planner", "sessionId": session_id})
            )
            async for node_name, step_state in graph.stream_steps(initial_state, on_token=on_token):
                final_state = step_state

                if node_name == "planner":
                    await event_queue.put(
                        format_sse(
                            "plan",
                            {
                                "sessionId": session_id,
                                "plan": [plan_step_to_wire(s) for s in step_state.plan],
                            },
                        )
                    )
                elif node_name == "retriever":
                    await event_queue.put(
                        format_sse(
                            "tool_result",
                            {
                                "tool": "hybrid_rag_search",
                                "chunksRetrieved": len(step_state.retrieved_chunks),
                                "citations": [citation_to_wire(c) for c in step_state.citations],
                                "injectionWarnings": [
                                    warning_to_wire(w) for w in step_state.injection_warnings
                                ],
                            },
                        )
                    )
                elif node_name == "grounding":
                    await event_queue.put(
                        format_sse(
                            "grounding",
                            {
                                "sessionId": session_id,
                                "grounding": step_state.grounding,
                                "feedback": step_state.grounding_feedback,
                            },
                        )
                    )

                upcoming = next_node(node_name, step_state)
                if upcoming:
                    await event_queue.put(
                        format_sse("node_start", {"node": upcoming, "sessionId": session_id})
                    )

            if final_state.error:
                await refund_if_charged()
                await event_queue.put(
                    format_sse("error", {"error": final_state.error, "sessionId": session_id})
                )
                return

            # Planner refusals are fixed text, not model output: send them as one chunk.
            if not tokens_sent and final_state.response:
                await event_queue.put(
                    format_sse("token", {"sessionId": session_id, "token": final_state.response})
                )

            # Persist before `done` so a client refetch sees the conversation; shield it so a
            # disconnect cannot cancel the write half-way.
            conversation_id_out: str | None = None
            if user_id and not is_guest:
                conversation_id_out = await asyncio.shield(
                    persist_turn(user_id, session_id, query, final_state)
                )

            await event_queue.put(
                format_sse(
                    "done",
                    AgentDoneEventWire.model_validate(
                        {
                            "sessionId": session_id,
                            "conversationId": conversation_id_out,
                            "query": query,
                            "response": final_state.response,
                            "nodeHistory": final_state.node_history,
                            "plan": [plan_step_to_wire(s) for s in final_state.plan],
                            "citations": [citation_to_wire(c) for c in final_state.citations],
                            "injectionWarnings": [
                                warning_to_wire(w) for w in final_state.injection_warnings
                            ],
                            "mermaidDiagrams": final_state.mermaid_diagrams,
                            "grounding": final_state.grounding,
                            "isComplete": True,
                            "completedAt": final_state.completed_at.isoformat()
                            if final_state.completed_at
                            else None,
                        }
                    ).model_dump(),
                )
            )

        except asyncio.CancelledError:
            logger.info("Agent pipeline cancelled (client disconnect or abort)")
            # Once the model has produced output the cost is incurred; refund only earlier aborts.
            if not tokens_sent:
                await refund_if_charged()
            raise
        except Exception:
            logger.exception("Error during agent SSE streaming")
            await refund_if_charged()
            masked_error = "Internal error. Reference: " + session_id[:8]
            await event_queue.put(
                format_sse("error", {"error": masked_error, "sessionId": session_id})
            )
        finally:
            await event_queue.put(None)

    pipeline_task = asyncio.create_task(run_pipeline())

    try:
        while True:
            chunk = await event_queue.get()
            if chunk is None:
                break
            yield chunk
    finally:
        if not pipeline_task.done():
            pipeline_task.cancel()


@router.post("/stream")
async def stream_agent_execution(
    payload: AgentStreamRequestWire,
    request: Request,
    current_user: User = Depends(get_current_user),
    graph: AgentGraph = Depends(lambda: default_agent_graph),
):
    """
    Server-Sent Events (SSE) streaming endpoint for the agent pipeline.
    Enforces the token-bucket rate limiter with automatic 429 and retry headers.
    """
    client_ip = get_client_ip(request)

    doc_uuid: UUID | None = None
    if payload.documentId:
        try:
            doc_uuid = UUID(payload.documentId)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid documentId UUID format",
            )
        await require_document_access(neon_db, doc_uuid, current_user)

    # Out-of-scope refusals cost nothing, so they are not metered.
    quota_charged = classify_query_intent(payload.query) != "out_of_scope"
    if quota_charged:
        remaining = await default_rate_limiter.check_and_consume(
            user_id=current_user.id,
            client_ip=client_ip,
            is_guest=current_user.is_guest,
        )
    else:
        remaining = await default_rate_limiter.get_quota(
            user_id=current_user.id,
            is_guest=current_user.is_guest,
        )

    session_id = uuid4().hex
    chat_history: list[dict[str, str]] = []
    resumed_conversation: UUID | None = None
    if payload.sessionId and not current_user.is_guest:
        try:
            requested = UUID(payload.sessionId)
        except ValueError:
            requested = None
        if requested:
            rows = await neon_db.get_conversation_history(
                current_user.id, requested, settings.CHAT_HISTORY_MESSAGES
            )
            if rows is not None:
                session_id = payload.sessionId
                resumed_conversation = requested
                chat_history = [{"role": r["role"], "content": r["content"]} for r in rows]

    return StreamingResponse(
        generate_agent_stream(
            query=payload.query,
            user_id=current_user.id,
            document_id=doc_uuid,
            session_id=session_id,
            graph=graph,
            is_guest=current_user.is_guest,
            quota_remaining=remaining,
            quota_charged=quota_charged,
            chat_history=chat_history,
            conversation_id=resumed_conversation,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
            "Content-Type": "text/event-stream; charset=utf-8",
        },
    )


@router.get("/audit-logs")
async def get_tool_audit_logs(
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    """Retrieve the caller's persisted tool execution audit records (``tool_audit_logs``)."""
    logs = await default_audit_logger.fetch_audit_logs_from_db(user_id=current_user.id, limit=limit)
    return {"logs": logs, "count": len(logs)}

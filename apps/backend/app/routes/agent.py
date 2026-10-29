import asyncio
import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import AgentGraph, classify_query_intent, default_agent_graph
from app.agent.state import AgentState, Citation, PlanStep
from app.core.audit_log import default_audit_logger
from app.core.auth import get_client_ip, get_current_user
from app.core.rate_limiter import default_rate_limiter
from app.db.models import User
from app.db.neon import neon_db
from app.routes.documents import require_document_access

logger = logging.getLogger("nexusagent.routes.agent")

router = APIRouter(prefix="/agent", tags=["Agent Autonomous Orchestration & SSE Streaming"])


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
        "chunkId": c.chunk_id,
        "documentId": c.document_id,
        "filename": c.filename,
        "startLine": c.start_line,
        "endLine": c.end_line,
        "headerPath": c.header_path,
        "preview": c.preview,
    }


async def generate_agent_stream(
    query: str,
    user_id: UUID | None,
    document_id: UUID | None,
    session_id: str,
    graph: AgentGraph,
    is_guest: bool = True,
    client_ip: str = "127.0.0.1",
    quota_remaining: int | None = None,
    chat_history: list[dict[str, str]] | None = None,
) -> AsyncIterator[str]:
    """
    Asynchronously run AgentGraph pipeline and yield SSE event chunks:
    plan -> node_start -> tool_call -> tool_result -> critic -> token -> done.
    """
    initial_state = AgentState(
        session_id=session_id,
        user_id=user_id,
        query=query,
        document_id=document_id,
        chat_history=chat_history or [],
    )

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    # Pre-seed initial start event
    start_payload = {
        "sessionId": session_id,
        "query": query,
        "timestamp": initial_state.created_at.isoformat(),
    }
    if quota_remaining is not None:
        start_payload["quotaRemaining"] = quota_remaining

    await event_queue.put(format_sse("start", start_payload))

    async def run_pipeline():
        try:
            final_state = initial_state
            async for node_name, step_state in graph.stream_steps(initial_state):
                final_state = step_state

                # 1. Yield node_start event
                await event_queue.put(
                    format_sse(
                        "node_start",
                        {
                            "node": node_name,
                            "sessionId": session_id,
                            "iteration": step_state.iteration_count,
                        },
                    )
                )

                # 2. Yield node-specific events
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
                            },
                        )
                    )

                elif node_name == "critic":
                    await event_queue.put(
                        format_sse(
                            "critic",
                            {
                                "sessionId": session_id,
                                "reflectionScore": step_state.reflection_score,
                                "isGrounded": step_state.is_grounded,
                                "needsReplan": step_state.needs_replan,
                                "feedback": step_state.reflection_feedback,
                                "iteration": step_state.iteration_count,
                            },
                        )
                    )

                elif node_name == "synthesizer":
                    response_text = step_state.response
                    words = response_text.split(" ")
                    for i in range(0, len(words), 3):
                        chunk = " ".join(words[i : i + 3]) + " "
                        await event_queue.put(
                            format_sse(
                                "token",
                                {
                                    "sessionId": session_id,
                                    "token": chunk,
                                },
                            )
                        )
                        await asyncio.sleep(0.01)

            if final_state.error:
                if user_id:
                    try:
                        await default_rate_limiter.refund(
                            user_id=user_id, client_ip=client_ip, is_guest=is_guest
                        )
                    except Exception as refund_err:  # noqa: BLE001
                        logger.warning(f"Could not refund rate limit token: {refund_err}")
                await event_queue.put(
                    format_sse("error", {"error": final_state.error, "sessionId": session_id})
                )
                return

            # 3. Final completion event
            await event_queue.put(
                format_sse(
                    "done",
                    {
                        "sessionId": session_id,
                        "query": query,
                        "response": final_state.response,
                        "nodeHistory": final_state.node_history,
                        "plan": [plan_step_to_wire(s) for s in final_state.plan],
                        "citations": [citation_to_wire(c) for c in final_state.citations],
                        "mermaidDiagrams": final_state.mermaid_diagrams,
                        "reflectionScore": final_state.reflection_score,
                        "isGrounded": final_state.is_grounded,
                        "iterationCount": final_state.iteration_count,
                        "isComplete": True,
                        "completedAt": final_state.completed_at.isoformat()
                        if final_state.completed_at
                        else None,
                    },
                )
            )

            # Persist chat turn to DB if authenticated Google user
            if user_id and not is_guest:
                try:
                    conv_id = None
                    try:
                        conv_id = UUID(session_id)
                    except ValueError:
                        pass
                    title = (query[:60] + "...") if len(query) > 60 else query
                    conv = await neon_db.create_conversation(
                        user_id, title=title, conversation_id=conv_id
                    )
                    if conv and "id" in conv:
                        actual_conv_id = conv["id"]
                        await neon_db.save_message(actual_conv_id, role="user", content=query)
                        await neon_db.save_message(
                            actual_conv_id,
                            role="assistant",
                            content=final_state.response,
                            plan_trace=[plan_step_to_wire(s) for s in final_state.plan],
                            reflection_summary={
                                "reflectionScore": final_state.reflection_score,
                                "isGrounded": final_state.is_grounded,
                                "mermaidDiagrams": final_state.mermaid_diagrams,
                            },
                        )
                    else:
                        logger.warning(
                            f"Could not persist conversation {conv_id} for user {user_id}"
                        )
                except Exception as save_err:  # noqa: BLE001
                    logger.warning(f"Could not persist conversation history: {save_err}")

        except Exception:
            logger.exception("Error during agent SSE streaming")
            if user_id:
                try:
                    await default_rate_limiter.refund(
                        user_id=user_id, client_ip=client_ip, is_guest=is_guest
                    )
                except Exception as refund_err:  # noqa: BLE001
                    logger.warning(f"Could not refund rate limit token: {refund_err}")
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
    Server-Sent Events (SSE) streaming endpoint for autonomous agent DAG execution.
    Enforces token-bucket rate limiter with automatic 429 and retry headers.
    """
    client_ip = get_client_ip(request)

    if classify_query_intent(payload.query) != "out_of_scope":
        remaining = await default_rate_limiter.check_and_consume(
            user_id=current_user.id,
            client_ip=client_ip,
            is_guest=current_user.is_guest,
        )
    else:
        remaining = await default_rate_limiter.get_quota(
            user_id=current_user.id,
            client_ip=client_ip,
            is_guest=current_user.is_guest,
        )

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

    session_id = uuid4().hex
    chat_history: list[dict[str, str]] = []
    if payload.sessionId and not current_user.is_guest:
        try:
            requested = UUID(payload.sessionId)
        except ValueError:
            requested = None
        if requested and await neon_db.get_conversation(current_user.id, requested):
            session_id = payload.sessionId
            rows = await neon_db.get_conversation_messages(current_user.id, requested)
            chat_history = [{"role": r["role"], "content": r["content"]} for r in rows][-2 * 6 :]

    return StreamingResponse(
        generate_agent_stream(
            query=payload.query,
            user_id=current_user.id,
            document_id=doc_uuid,
            session_id=session_id,
            graph=graph,
            is_guest=current_user.is_guest,
            client_ip=client_ip,
            quota_remaining=remaining,
            chat_history=chat_history,
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
    """
    Retrieve immutable tool execution audit records (Neon ``tool_audit_logs``
    first, in-memory ring fallback when the database is unavailable).
    """
    logs = await default_audit_logger.fetch_audit_logs_from_db(user_id=current_user.id, limit=limit)
    return {"logs": logs, "count": len(logs)}

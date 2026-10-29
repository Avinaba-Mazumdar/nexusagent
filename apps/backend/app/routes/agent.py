import asyncio
import json
import logging
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.agent.graph import AgentGraph, default_agent_graph
from app.agent.state import AgentState
from app.core.auth import get_client_ip, get_current_user, validate_byok_key
from app.core.hitl_coordinator import default_hitl_coordinator
from app.core.rate_limiter import default_rate_limiter
from app.db.models import User

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


async def generate_agent_stream(
    query: str,
    user_id: UUID | None,
    document_id: UUID | None,
    session_id: str,
    graph: AgentGraph,
    is_guest: bool = True,
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
    )

    event_queue: asyncio.Queue[str | None] = asyncio.Queue()

    # Pre-seed initial start event
    await event_queue.put(
        format_sse(
            "start",
            {
                "sessionId": session_id,
                "query": query,
                "timestamp": initial_state.created_at.isoformat(),
            },
        )
    )

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
                                "plan": [
                                    {
                                        "stepNumber": s.step_number,
                                        "description": s.description,
                                        "status": s.status,
                                        "tool": s.tool,
                                    }
                                    for s in step_state.plan
                                ],
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
                                "citations": [
                                    {
                                        "id": c.id,
                                        "chunkId": c.chunk_id,
                                        "documentId": c.document_id,
                                        "filename": c.filename,
                                        "startLine": c.start_line,
                                        "endLine": c.end_line,
                                        "headerPath": c.header_path,
                                        "preview": c.preview,
                                    }
                                    for c in step_state.citations
                                ],
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

            # 3. Final completion event
            await event_queue.put(
                format_sse(
                    "done",
                    {
                        "sessionId": session_id,
                        "query": query,
                        "response": final_state.response,
                        "nodeHistory": final_state.node_history,
                        "plan": [
                            {
                                "stepNumber": s.step_number,
                                "description": s.description,
                                "status": s.status,
                                "tool": s.tool,
                            }
                            for s in final_state.plan
                        ],
                        "citations": [
                            {
                                "id": c.id,
                                "chunkId": c.chunk_id,
                                "documentId": c.document_id,
                                "filename": c.filename,
                                "startLine": c.start_line,
                                "endLine": c.end_line,
                                "headerPath": c.header_path,
                                "preview": c.preview,
                            }
                            for c in final_state.citations
                        ],
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
                    from app.db.neon import neon_db
                    conv_id = None
                    try:
                        conv_id = UUID(session_id)
                    except ValueError:
                        pass
                    title = (query[:60] + "...") if len(query) > 60 else query
                    conv = await neon_db.create_conversation(user_id, title=title, conversation_id=conv_id)
                    if conv and "id" in conv:
                        actual_conv_id = conv["id"]
                        await neon_db.save_message(actual_conv_id, role="user", content=query)
                        await neon_db.save_message(
                            actual_conv_id,
                            role="assistant",
                            content=final_state.response,
                            plan_trace=[
                                {
                                    "stepNumber": s.step_number,
                                    "description": s.description,
                                    "status": s.status,
                                    "tool": s.tool,
                                }
                                for s in final_state.plan
                            ],
                            reflection_summary={
                                "reflectionScore": final_state.reflection_score,
                                "isGrounded": final_state.is_grounded,
                                "mermaidDiagrams": final_state.mermaid_diagrams,
                            },
                        )
                except Exception as save_err:
                    logger.warning(f"Could not persist conversation history: {save_err}")

        except Exception as e:
            logger.exception("Error during agent SSE streaming")
            await event_queue.put(format_sse("error", {"error": str(e), "sessionId": session_id}))
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
    byok_key: str | None = Header(None, alias="X-User-API-Key"),
    graph: AgentGraph = Depends(lambda: default_agent_graph),
):
    """
    Server-Sent Events (SSE) streaming endpoint for autonomous agent DAG execution.
    Enforces token-bucket rate limiter with automatic 429 and retry headers.
    """
    client_ip = get_client_ip(request)
    byok_key = validate_byok_key(byok_key)

    # Token bucket rate limiting (Neon DB with memory tier fallback)
    await default_rate_limiter.check_and_consume(
        user_id=current_user.id,
        client_ip=client_ip,
        is_guest=current_user.is_guest,
        byok_key=byok_key,
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

    session_id = payload.sessionId or uuid4().hex

    return StreamingResponse(
        generate_agent_stream(
            query=payload.query,
            user_id=current_user.id,
            document_id=doc_uuid,
            session_id=session_id,
            graph=graph,
            is_guest=current_user.is_guest,
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
    limit: int = 50,
    current_user: User = Depends(get_current_user),
):
    """
    Retrieve immutable tool execution audit records (Neon ``tool_audit_logs``
    first, in-memory ring fallback when the database is unavailable).
    """
    logs = await default_hitl_coordinator.fetch_audit_logs_from_db(limit=limit)
    return {"logs": logs, "count": len(logs)}

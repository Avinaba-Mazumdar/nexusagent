"""One agent request: runs the LangGraph pipeline and turns it into an ordered SSE frame stream."""

import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

from app.agent.graph import AgentGraph, next_node
from app.agent.sse import (
    done_frame,
    error_frame,
    node_frames,
    node_start_frame,
    redact_frame,
    start_frame,
    token_frame,
    tool_call_frame,
)
from app.agent.state import AgentState, Intent
from app.core.rate_limiter import default_rate_limiter
from app.services.conversations import persist_turn

logger = logging.getLogger("nexusagent.agent.run")

# The only node that calls a tool; its `tool_call` frame is sent before the call starts.
TOOL_NODE = "retriever"


class AgentRun:
    """
    One request's pipeline run. The graph's output is queued as frames, and ``frames()`` yields
    them in this order: start, then per node node_start (+ tool_call before the retriever) and its
    plan/tool_result/grounding frame, then token*, then done or error.

    Quota: a run that fails before any token reaches the client refunds its charge. A run that
    was aborted after retrieval keeps it, so a client cannot take the retrieval work for free.
    """

    def __init__(
        self,
        *,
        query: str,
        intent: Intent,
        user_id: UUID | None,
        document_id: UUID | None,
        session_id: str,
        graph: AgentGraph,
        is_guest: bool = True,
        quota_remaining: int | None = None,
        quota_charged: bool = True,
        chat_history: list[dict[str, str]] | None = None,
        conversation_id: UUID | None = None,
    ) -> None:
        self.query = query
        self.session_id = session_id
        self.user_id = user_id
        self.graph = graph
        self.is_guest = is_guest
        self.quota_remaining = quota_remaining
        self.quota_charged = quota_charged
        self.state = AgentState(
            session_id=session_id,
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            document_id=document_id,
            chat_history=chat_history or [],
            intent=intent,
        )
        self._frames: asyncio.Queue[str | None] = asyncio.Queue()
        self._tokens_sent = False

    async def frames(self) -> AsyncIterator[str]:
        """Run the pipeline in a task and yield its frames as they are produced."""
        self._send(
            start_frame(
                self.session_id,
                self.query,
                self.state.created_at.isoformat(),
                self.quota_remaining,
            )
        )
        pipeline = asyncio.create_task(self._run_pipeline())
        try:
            while (frame := await self._frames.get()) is not None:
                yield frame
        finally:
            # The client went away: stop the pipeline. Its quota charge stays (see class docstring).
            if not pipeline.done():
                pipeline.cancel()

    def _send(self, frame: str) -> None:
        self._frames.put_nowait(frame)

    async def _run_pipeline(self) -> None:
        try:
            self._send(node_start_frame(self.session_id, "planner"))
            final_state = self.state
            async for node_name, step_state in self.graph.stream_steps(
                self.state, on_token=self._on_token
            ):
                final_state = step_state
                for frame in node_frames(node_name, self.session_id, step_state):
                    self._send(frame)
                self._announce_next(node_name, step_state)

            if final_state.error:
                # Failures such as "no model configured" happen before any output and stay refundable.
                await self._refund_unless_streamed()
                self._send(error_frame(self.session_id, final_state.error))
                return

            await self._finish(final_state)

        except asyncio.CancelledError:
            logger.info("Agent pipeline cancelled (client disconnect or abort)")
            raise
        except Exception:
            logger.exception("Error during agent SSE streaming")
            await self._refund_unless_streamed()
            masked_error = "Internal error. Reference: " + self.session_id[:8]
            self._send(error_frame(self.session_id, masked_error))
        finally:
            self._frames.put_nowait(None)

    async def _on_token(self, text: str) -> None:
        self._tokens_sent = True
        self._send(token_frame(self.session_id, text))

    def _announce_next(self, finished: str, state: AgentState) -> None:
        upcoming = next_node(finished, state)
        if upcoming is None:
            return
        self._send(node_start_frame(self.session_id, upcoming))
        if upcoming == TOOL_NODE:
            self._send(tool_call_frame(self.session_id, state))

    async def _finish(self, final_state: AgentState) -> None:
        # Planner refusals are fixed text, not model output: send them as one chunk.
        if not self._tokens_sent and final_state.response:
            self._send(token_frame(self.session_id, final_state.response))
        # After a canary leak the streamed text is withdrawn and replaced by the alert.
        elif final_state.canary_leaked:
            self._send(redact_frame(self.session_id, final_state.response))

        # Persist before `done` so a client refetch sees the conversation; shield it so a
        # disconnect cannot cancel the write half-way.
        conversation_id: str | None = None
        if self.user_id and not self.is_guest:
            conversation_id = await asyncio.shield(
                persist_turn(self.user_id, self.session_id, self.query, final_state)
            )
        self._send(done_frame(self.session_id, conversation_id, self.query, final_state))

    async def _refund_unless_streamed(self) -> None:
        if self._tokens_sent or not (self.user_id and self.quota_charged):
            return
        try:
            await default_rate_limiter.refund(user_id=self.user_id)
        except Exception as refund_err:  # noqa: BLE001
            logger.warning(f"Could not refund rate limit token: {refund_err}")

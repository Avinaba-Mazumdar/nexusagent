"""Saving an answered turn to the user's chat history."""

import logging
from uuid import UUID

from app.agent.state import AgentState
from app.db.models import CitationWire, PlanStepWire
from app.db.neon import neon_db

logger = logging.getLogger("nexusagent.services.conversations")

TITLE_MAX_CHARS = 60


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
            plan_trace=[
                PlanStepWire.model_validate(s).model_dump(by_alias=True) for s in state.plan
            ],
            reflection_summary={
                "grounding": state.grounding,
                "citations": [
                    CitationWire.model_validate(c).model_dump(by_alias=True)
                    for c in state.citations
                ],
                "mermaidDiagrams": state.mermaid_diagrams,
            },
        )
        return str(conv["id"])
    except Exception as save_err:  # noqa: BLE001
        logger.warning(f"Could not persist conversation history: {save_err}")
        return None

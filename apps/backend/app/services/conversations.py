"""Saving an answered turn to the user's chat history."""

import logging
from uuid import UUID

from app.agent.state import AgentState
from app.core.security_guardrails import detect_prompt_injection
from app.db.models import CitationWire, PlanStepWire, WebSourceWire
from app.db.neon import neon_db

logger = logging.getLogger("nexusagent.services.conversations")

TITLE_MAX_CHARS = 60
WITHHELD_ANSWER = "This answer was withheld because it matched a prompt-injection pattern."


def persistable_turn(query: str, response: str) -> tuple[str, str] | None:
    """Text safe to store as memory. ``None`` drops the turn.

    A query that matches an injection pattern is not stored. A matching answer is
    replaced with a placeholder. A rephrased attack is not detected.
    """
    injected, _reason = detect_prompt_injection(query)
    if injected:
        return None
    answer_injected, _reason = detect_prompt_injection(response)
    if answer_injected:
        response = WITHHELD_ANSWER
    return query, response


async def persist_turn(user_id: UUID, session_id: str, query: str, state: AgentState) -> str | None:
    """Save the turn for a signed-in user. Returns the conversation id, or None on failure."""
    stored = persistable_turn(query, state.response)
    if stored is None:
        return None
    query, response = stored
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
            response,
            plan_trace=[
                PlanStepWire.model_validate(s).model_dump(by_alias=True) for s in state.plan
            ],
            reflection_summary={
                "grounding": state.grounding,
                "citations": [
                    CitationWire.model_validate(c).model_dump(by_alias=True)
                    for c in state.citations
                ],
                "webSources": [
                    WebSourceWire(title=s.title, url=s.url).model_dump() for s in state.web_sources
                ],
                "uncited": state.uncited,
            },
        )
        return str(conv["id"])
    except Exception as save_err:  # noqa: BLE001
        logger.warning(f"Could not persist conversation history: {save_err}")
        return None

"""Server-Sent Event framing for the agent stream."""

from pydantic import BaseModel


def format_sse(event_type: str, payload: BaseModel) -> str:
    """Format a typed payload (see ``SSE_WIRE_MODELS``) as one Server-Sent Event frame."""
    return f"event: {event_type}\ndata: {payload.model_dump_json(by_alias=True)}\n\n"

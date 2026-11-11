"""LLM creation, streaming, and model routing."""

import functools
import inspect
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import Any

import httpx
from google.genai.errors import ServerError
from langchain_core.messages import AIMessage, BaseMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import (
    GoogleModelNotFoundError,
    GooglePermissionDeniedError,
    GoogleRateLimitError,
)

from app.agent.model_router import ModelRouter
from app.config import settings

TokenSink = Callable[[str], Awaitable[None]]

default_model_router = ModelRouter(settings.GEMINI_MODELS)


@functools.lru_cache(maxsize=32)
def _get_llm(api_key: str, model: str):
    # One attempt per model: on a 429 the router moves on instead of backing off on the same model.
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0.1,
        api_key=api_key,
        max_retries=1,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
    )


class AllModelsRateLimited(Exception):
    """Every configured model is cooling down after hitting its quota."""

    def __init__(self, retry_at: float | None):
        self.retry_at = retry_at


def _retry_hint(retry_at: float | None) -> str:
    if retry_at is None:
        return "Please try again later."
    minutes = max(1, round((retry_at - time.time()) / 60))
    if minutes < 90:
        return f"Please try again in about {minutes} minute{'s' if minutes != 1 else ''}."
    return f"Please try again in about {round(minutes / 60)} hours (daily quotas reset at midnight Pacific time)."


def _chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", chunk)
    if isinstance(content, list):
        return "".join(c.get("text", "") if isinstance(c, dict) else str(c) for c in content)
    return str(content or "")


async def _stream_llm(
    llm_chain: Any,
    messages: Sequence[BaseMessage],
    on_token: TokenSink | None = None,
) -> Any:
    """Stream model output, forwarding text tokens to ``on_token`` and returning the merged chunk."""
    merged = None
    async for chunk in llm_chain.astream(messages):
        merged = chunk if merged is None else merged + chunk
        text = _chunk_text(chunk)
        if text and on_token:
            await on_token(text)
    return merged or AIMessage(content="")


async def call_with_routing(
    router: ModelRouter,
    *,
    prefer_lite: bool = False,
    run: Callable[..., Awaitable[Any]],
) -> tuple[Any, str]:
    """`run(llm)` performs one call and returns its result. Moves to the next model on 429/404/403/5xx/timeout
    if nothing was streamed yet. Returns (result, model)."""
    forwarded = False

    def mark_forwarded() -> None:
        nonlocal forwarded
        forwarded = True

    sig = inspect.signature(run)
    accepts_mark = len(sig.parameters) >= 2

    for model in router.candidates(prefer_lite=prefer_lite):
        llm = _get_llm(settings.GEMINI_API_KEY, model)
        try:
            result = await (run(llm, mark_forwarded) if accepts_mark else run(llm))
            return result, model
        except GoogleRateLimitError as exc:
            if forwarded:
                raise
            router.mark_rate_limited(model, exc)
        except GoogleModelNotFoundError, GooglePermissionDeniedError:
            if forwarded:
                raise
            router.mark_unavailable(model)
        except ServerError, TimeoutError, httpx.TimeoutException:
            if forwarded:
                raise
            router.mark_overloaded(model)
    raise AllModelsRateLimited(router.next_available_at())

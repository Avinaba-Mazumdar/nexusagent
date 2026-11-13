"""LLM creation, streaming, and model routing."""

import asyncio
import contextlib
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

from app.agent.model_health import persist_cooldown
from app.agent.model_router import ModelRouter
from app.config import settings

TokenSink = Callable[[str], Awaitable[None]]

default_model_router = ModelRouter(settings.TEXT_MODELS, scope="chat", on_cooldown=persist_cooldown)

ALL_MODELS_LIMITED_MESSAGE = "Every free-tier Gemini and Gemma model has reached its usage limit. "


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


class FirstTokenTimeout(Exception):
    """No token arrived before the first-token deadline. The socket itself did not time out."""


class AllModelsRateLimited(Exception):
    """Every configured model failed. ``quota`` is false when none of the failures was a 429."""

    def __init__(self, retry_at: float | None, *, quota: bool = True):
        self.retry_at = retry_at
        self.quota = quota


def failure_message(exc: AllModelsRateLimited) -> str:
    """User-facing text. A slow model is not an exhausted quota."""
    if not exc.quota:
        return "The language model is taking too long to respond. Please try again shortly."
    return ALL_MODELS_LIMITED_MESSAGE + _retry_hint(exc.retry_at)


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
    """Stream model output, forwarding text tokens to ``on_token`` and returning the merged chunk.

    Raises ``FirstTokenTimeout`` if the first chunk takes longer than
    ``settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS``. That is a slow start, not a stalled socket, so
    ``call_with_routing`` tries the next model without recording a shared outage.
    """
    stream = llm_chain.astream(messages)
    deadline = settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS
    merged = None
    try:
        try:
            first = await asyncio.wait_for(anext(stream), deadline) if deadline > 0 else None
        except StopAsyncIteration:
            return AIMessage(content="")
        except TimeoutError as exc:
            raise FirstTokenTimeout(
                f"no response within {deadline:g} s (first-token deadline)"
            ) from exc
        pending = [first] if deadline > 0 else []
        async for chunk in _chain(pending, stream):
            merged = chunk if merged is None else merged + chunk
            text = _chunk_text(chunk)
            if text and on_token:
                await on_token(text)
    finally:
        aclose = getattr(stream, "aclose", None)
        if aclose is not None:
            with contextlib.suppress(Exception):
                await aclose()
    return merged or AIMessage(content="")


async def _chain(head: list[Any], rest: Any) -> Any:
    for item in head:
        yield item
    async for item in rest:
        yield item


async def call_with_routing(
    router: ModelRouter,
    *,
    prefer_lite: bool = False,
    run: Callable[..., Awaitable[Any]],
) -> tuple[Any, str]:
    """`run(llm)` performs one call and returns its result. Moves to the next model on 429/404/403/5xx/timeout
    if nothing was streamed yet. Returns (result, model)."""
    forwarded = False
    saw_quota = False

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
            saw_quota = True
            router.mark_rate_limited(model, exc)
        except (GoogleModelNotFoundError, GooglePermissionDeniedError) as exc:
            if forwarded:
                raise
            router.mark_unavailable(model, exc)
        except FirstTokenTimeout:
            if forwarded:
                raise
            router.mark_slow(model)
        except (TimeoutError, httpx.TimeoutException) as exc:
            if forwarded:
                raise
            router.mark_timed_out(model, exc)
        except ServerError as exc:
            if forwarded:
                raise
            router.mark_overloaded(model, exc)
    raise AllModelsRateLimited(router.next_available_at(), quota=saw_quota)

"""LLM creation, streaming, and model routing."""

import asyncio
import contextlib
import functools
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Sequence
from typing import Protocol, cast, override

import httpx
from google.genai.errors import ServerError
from langchain_core.language_models import LanguageModelInput
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.messages.ai import add_ai_message_chunks
from langchain_core.runnables import Runnable
from langchain_core.tools import BaseTool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_google_genai.chat_models import (
    GoogleModelNotFoundError,
    GooglePermissionDeniedError,
    GoogleRateLimitError,
)
from pydantic import BaseModel

from app.agent.model_health import persist_cooldown
from app.agent.model_router import ModelRouter
from app.config import settings

TokenSink = Callable[[str], Awaitable[None]]
MarkForwarded = Callable[[], None]

default_model_router = ModelRouter(settings.TEXT_MODELS, scope="chat", on_cooldown=persist_cooldown)

ALL_MODELS_LIMITED_MESSAGE = "Every free-tier Gemini and Gemma model has reached its usage limit. "


class ChunkStream(Protocol):
    """A chat model, or one with tools bound, that streams its reply.

    Chat models stream ``AIMessageChunk``s; a tool binding is typed as yielding the base class.
    """

    def astream(self, input: Sequence[BaseMessage], /) -> AsyncIterator[AIMessage]: ...


class ChatModel(ChunkStream, Protocol):
    """The part of ``ChatGoogleGenerativeAI`` the agent uses, with complete types."""

    @property
    def model(self) -> str: ...

    def bind_tools(
        self, tools: Sequence[dict[str, object] | BaseTool], /
    ) -> Runnable[LanguageModelInput, AIMessage]: ...

    def with_structured_output(
        self, schema: type[BaseModel], /, *, include_raw: bool = False
    ) -> Runnable[LanguageModelInput, dict[str, object] | BaseModel]: ...


@functools.lru_cache(maxsize=32)
def get_llm(api_key: str, model: str) -> ChatModel:
    # One attempt per model: on a 429 the router moves on instead of backing off on the same model.
    return ChatGoogleGenerativeAI(
        model=model,
        temperature=0.1,
        api_key=api_key,
        max_retries=1,
        timeout=settings.LLM_TIMEOUT_SECONDS,
        max_output_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
    )


def with_tools(llm: ChatModel, tools: Sequence[dict[str, object] | BaseTool]) -> ChunkStream:
    """Bind tools for a streamed call."""
    return llm.bind_tools(tools)


class FirstTokenTimeout(Exception):
    """No token arrived before the first-token deadline. The socket itself did not time out."""


class AllModelsRateLimited(Exception):
    """Every configured model failed. ``quota`` is false when none of the failures was a 429."""

    @override
    def __init__(self, retry_at: float | None, *, quota: bool = True):
        super().__init__(retry_at)
        self.retry_at: float | None = retry_at
        self.quota: bool = quota


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


def chunk_text(chunk: object) -> str:
    """The text of a message or chunk: a string, or the text parts of a content-block list."""
    content = cast(object, getattr(chunk, "content", chunk))
    if isinstance(content, list):
        parts: list[str] = []
        for block in cast(list[object], content):
            if isinstance(block, dict):
                parts.append(str(cast(dict[str, object], block).get("text", "")))
            else:
                parts.append(str(block))
        return "".join(parts)
    return str(content or "")


async def stream_llm(
    llm_chain: ChunkStream,
    messages: Sequence[BaseMessage],
    on_token: TokenSink | None = None,
) -> AIMessage:
    """Stream model output, forwarding text tokens to ``on_token`` and returning the merged chunk.

    Raises ``FirstTokenTimeout`` if the first chunk takes longer than
    ``settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS``. That is a slow start, not a stalled socket, so
    ``call_with_routing`` tries the next model without recording a shared outage.
    """
    stream = llm_chain.astream(messages)
    deadline = settings.LLM_FIRST_TOKEN_TIMEOUT_SECONDS
    merged: AIMessage | None = None
    try:
        pending: list[AIMessage] = []
        if deadline > 0:
            try:
                pending.append(await asyncio.wait_for(anext(stream), deadline))
            except StopAsyncIteration:
                return AIMessage(content="")
            except TimeoutError as exc:
                raise FirstTokenTimeout(
                    f"no response within {deadline:g} s (first-token deadline)"
                ) from exc
        async for chunk in _chain(pending, stream):
            merged = chunk if merged is None else _merge(merged, chunk)
            text = chunk_text(chunk)
            if text and on_token:
                await on_token(text)
    finally:
        aclose = cast(object, getattr(stream, "aclose", None))
        if callable(aclose):
            with contextlib.suppress(Exception):
                await cast(Callable[[], Awaitable[None]], aclose)()
    return merged or AIMessage(content="")


def _merge(merged: AIMessage, chunk: AIMessage) -> AIMessage:
    """Append a streamed chunk. Only chunks can be merged; a stream yields nothing else."""
    if isinstance(merged, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
        return add_ai_message_chunks(merged, chunk)
    raise TypeError(f"cannot merge {type(chunk).__name__} into {type(merged).__name__}")


async def _chain[T](head: list[T], rest: AsyncIterator[T]) -> AsyncIterator[T]:
    for item in head:
        yield item
    async for item in rest:
        yield item


async def call_with_routing[T](
    router: ModelRouter,
    *,
    prefer_lite: bool = False,
    run: Callable[[ChatModel, MarkForwarded], Awaitable[T]],
) -> tuple[T, str]:
    """`run(llm, mark_forwarded)` performs one call and returns its result. It calls
    ``mark_forwarded`` once output reached the client. Moves to the next model on
    429/404/403/5xx/timeout if nothing was streamed yet. Returns (result, model)."""
    forwarded = False
    saw_quota = False

    def mark_forwarded() -> None:
        nonlocal forwarded
        forwarded = True

    for model in router.candidates(prefer_lite=prefer_lite):
        llm = get_llm(settings.GEMINI_API_KEY, model)
        try:
            result = await run(llm, mark_forwarded)
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

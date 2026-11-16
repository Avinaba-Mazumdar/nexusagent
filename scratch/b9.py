from ed import rep

L = "app/agent/llm.py"
rep(
    L,
    '''class ChunkStream(Protocol):
    """A chat model, or one with tools bound, whose ``astream`` yields message chunks."""

    def astream(self, input: Sequence[BaseMessage], /) -> AsyncIterator[AIMessageChunk]: ...


@functools.lru_cache(maxsize=32)
def get_llm(api_key: str, model: str) -> ChatGoogleGenerativeAI:''',
    '''class ChunkStream(Protocol):
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
def get_llm(api_key: str, model: str) -> ChatModel:''',
)
rep(
    L,
    '''def with_tools(
    llm: ChatGoogleGenerativeAI, tools: Sequence[dict[str, object] | BaseTool]
) -> ChunkStream:
    """Bind tools. The binding is typed as returning whole messages, but streams chunks."""
    return cast(ChunkStream, llm.bind_tools(tools))''',
    '''def with_tools(llm: ChatModel, tools: Sequence[dict[str, object] | BaseTool]) -> ChunkStream:
    """Bind tools for a streamed call."""
    return llm.bind_tools(tools)''',
)
rep(
    L,
    """    merged: AIMessageChunk | None = None
    try:
        pending: list[AIMessageChunk] = []""",
    """    merged: AIMessage | None = None
    try:
        pending: list[AIMessage] = []""",
)
rep(
    L,
    """            # Adding two AI chunks yields an AI chunk; the library types it as the base class.
            merged = chunk if merged is None else cast(AIMessageChunk, merged + chunk)""",
    """            merged = chunk if merged is None else _merge(merged, chunk)""",
)
rep(
    L,
    "async def _chain[T](",
    '''def _merge(merged: AIMessage, chunk: AIMessage) -> AIMessage:
    """Append a streamed chunk. Only chunks can be merged; a stream yields nothing else."""
    if isinstance(merged, AIMessageChunk) and isinstance(chunk, AIMessageChunk):
        return add_ai_message_chunks(merged, chunk)
    raise TypeError(f"cannot merge {type(chunk).__name__} into {type(merged).__name__}")


async def _chain[T](''',
)
rep(L, "    run: Callable[[ChatGoogleGenerativeAI, MarkForwarded], Awaitable[T]],", "    run: Callable[[ChatModel, MarkForwarded], Awaitable[T]],")
rep(L, "from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage\n", "from langchain_core.language_models import LanguageModelInput\nfrom langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage\nfrom langchain_core.messages.ai import add_ai_message_chunks\nfrom langchain_core.runnables import Runnable\n")
rep(L, "from langchain_google_genai.chat_models import (", "from pydantic import BaseModel\nfrom langchain_google_genai.chat_models import (")

G = "app/agent/graph.py"
rep(G, "from langchain_google_genai import ChatGoogleGenerativeAI\n", "")
rep(G, "    ChunkStream,\n", "    ChatModel,\n    ChunkStream,\n")
rep(G, "    async def _execute_route(llm: ChatGoogleGenerativeAI, _mark: MarkForwarded) -> object:", "    async def _execute_route(llm: ChatModel, _mark: MarkForwarded) -> object:")
rep(G, "    async def _execute_chat(llm: ChatGoogleGenerativeAI, mark_forwarded: MarkForwarded) -> AIMessage:", "    async def _execute_chat(llm: ChatModel, mark_forwarded: MarkForwarded) -> AIMessage:")
rep(G, "    async def _execute(llm: ChatGoogleGenerativeAI, mark_forwarded: MarkForwarded) -> AIMessage:", "    async def _execute(llm: ChatModel, mark_forwarded: MarkForwarded) -> AIMessage:")

T = "app/agent/tools.py"
rep(T, "from langchain_google_genai import ChatGoogleGenerativeAI\n", "")
rep(T, "from app.agent.llm import MarkForwarded, call_with_routing, chunk_text\n", "from app.agent.llm import ChatModel, MarkForwarded, call_with_routing, chunk_text\n")
rep(T, "    async def _execute(llm: ChatGoogleGenerativeAI, _mark: MarkForwarded) -> AIMessage:", "    async def _execute(llm: ChatModel, _mark: MarkForwarded) -> AIMessage:")
print("ok")

from ed import rep

T = "app/agent/tools.py"
rep(T, "from typing import Any\n", "from typing import ClassVar, cast\n")
rep(T, "from langchain_core.messages import HumanMessage, SystemMessage\n", "from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage\n")
rep(T, "from pydantic import BaseModel, Field\n", "from langchain_google_genai import ChatGoogleGenerativeAI\nfrom pydantic import BaseModel, ConfigDict, Field, ValidationError\n")
rep(T, "from app.agent.llm import _chunk_text, call_with_routing\n", "from app.agent.llm import MarkForwarded, call_with_routing, chunk_text\n")
rep(
    T,
    '''    "Answer the search request in at most 5 short factual sentences, using Google Search. "
    "State numbers''',
    '''    "Answer the search request in at most 5 short factual sentences, using Google Search. "
    + "State numbers''',
)
rep(
    T,
    '''def web_sources_from(merged: Any) -> tuple[list[str], list[WebSource]]:
    """Extract web search queries and validated web sources from merged response metadata."""
    resp_meta = getattr(merged, "response_metadata", None) or {}
    grounding_meta = resp_meta.get("grounding_metadata") or {}
    queries = [str(q) for q in (grounding_meta.get("web_search_queries") or [])]

    chunks = grounding_meta.get("grounding_chunks") or []
    sources: list[WebSource] = []
    seen_urls: set[str] = set()
    for c in chunks:
        web = c.get("web") if isinstance(c, dict) else getattr(c, "web", None)
        if not web:
            continue
        uri = web.get("uri") if isinstance(web, dict) else getattr(web, "uri", None)
        if not uri or not (str(uri).startswith("http://") or str(uri).startswith("https://")):
            continue
        title = (web.get("title") if isinstance(web, dict) else getattr(web, "title", None)) or uri
        uri_str = str(uri)
        if uri_str not in seen_urls:
            seen_urls.add(uri_str)
            sources.append(WebSource(title=str(title), url=uri_str))
            if len(sources) >= MAX_WEB_SOURCES:
                break
    return queries, sources''',
    '''class _GroundingWeb(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    uri: str | None = None
    title: str | None = None


class _GroundingChunk(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    web: _GroundingWeb | None = None


class _GroundingMetadata(BaseModel):
    """Google Search grounding metadata, as a dict or as the SDK's objects."""

    model_config: ClassVar[ConfigDict] = ConfigDict(from_attributes=True)

    web_search_queries: list[str] | None = None
    grounding_chunks: list[_GroundingChunk] | None = None


def web_sources_from(merged: object) -> tuple[list[str], list[WebSource]]:
    """Extract web search queries and validated web sources from merged response metadata."""
    resp_meta = cast(object, getattr(merged, "response_metadata", None))
    raw = cast(dict[str, object], resp_meta).get("grounding_metadata") if isinstance(resp_meta, dict) else None
    if not raw:
        return [], []
    try:
        grounding = _GroundingMetadata.model_validate(raw)
    except ValidationError:
        return [], []
    queries = list(grounding.web_search_queries or [])

    sources: list[WebSource] = []
    seen_urls: set[str] = set()
    for chunk in grounding.grounding_chunks or []:
        web = chunk.web
        if web is None:
            continue
        uri = web.uri
        if not uri or not (uri.startswith("http://") or uri.startswith("https://")):
            continue
        if uri not in seen_urls:
            seen_urls.add(uri)
            sources.append(WebSource(title=web.title or uri, url=uri))
            if len(sources) >= MAX_WEB_SOURCES:
                break
    return queries, sources''',
)
rep(
    T,
    """    messages = [SystemMessage(content=WEB_SEARCH_PROMPT), HumanMessage(content=query)]
    started = time.perf_counter()

    async def _execute(llm: Any) -> Any:
        return await llm.bind_tools([{"google_search": {}}]).ainvoke(messages)
""",
    """    messages: list[BaseMessage] = [
        SystemMessage(content=WEB_SEARCH_PROMPT),
        HumanMessage(content=query),
    ]
    started = time.perf_counter()

    async def _execute(llm: ChatGoogleGenerativeAI, _mark: MarkForwarded) -> AIMessage:
        return await llm.bind_tools([{"google_search": {}}]).ainvoke(messages)
""",
)
rep(
    T,
    """    summary = _chunk_text(merged)
    queries, sources = web_sources_from(merged)
    usage = getattr(merged, "usage_metadata", None) or {}""",
    """    summary = chunk_text(merged)
    queries, sources = web_sources_from(merged)
    usage = merged.usage_metadata""",
)
rep(
    T,
    """        usage={
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
        },""",
    """        usage={
            "input_tokens": usage["input_tokens"] if usage else 0,
            "output_tokens": usage["output_tokens"] if usage else 0,
            "total_tokens": usage["total_tokens"] if usage else 0,
        },""",
)
rep(T, "    tools = [\n        StructuredTool.from_function(", "    tools: list[StructuredTool] = [\n        StructuredTool.from_function(")
rep(
    T,
    '''                "Search the indexed LLM benchmark documents (Artificial Analysis, BenchLM, CursorBench, "
                "OpenRouter) with a new query."''',
    '''                "Search the indexed LLM benchmark documents (Artificial Analysis, BenchLM, CursorBench, "
                + "OpenRouter) with a new query."''',
)
print("ok")

import re

from ed import rep

C = "tests/conftest.py"
rep(
    C,
    '''    ``results`` is a fixed list, or a function of the call number (1, 2, ...).
    """

    def __init__(
        self,
        results: Sequence[HybridSearchResult] | Callable[[int], Sequence[HybridSearchResult]],
    ) -> None:
        super().__init__()
        self.results: (
            Sequence[HybridSearchResult] | Callable[[int], Sequence[HybridSearchResult]]
        ) = results
        self.calls: int = 0''',
    '''    ``results`` is a fixed list, or a function of the query and the call number (1, 2, ...).
    Every query is recorded in ``queries``.
    """

    def __init__(self, results: Sequence[HybridSearchResult] | SearchResults) -> None:
        super().__init__()
        self.results: Sequence[HybridSearchResult] | SearchResults = results
        self.queries: list[str] = []''',
)
rep(
    C,
    """        self.calls += 1
        results = self.results(self.calls) if callable(self.results) else self.results
        return list(results)""",
    """        self.queries.append(query)
        if callable(self.results):
            return list(self.results(query, len(self.queries)))
        return list(self.results)""",
)
rep(
    C,
    "class StaticSearch(HybridSearchEngine):",
    "type SearchResults = Callable[[str, int], Sequence[HybridSearchResult]]\n\n\nclass StaticSearch(HybridSearchEngine):",
)
rep(
    C,
    "@pytest.fixture\ndef fake_rate_db(",
    '''type AuditCalls = list[dict[str, object]]


@pytest.fixture
def audit_calls(monkeypatch: pytest.MonkeyPatch) -> AuditCalls:
    """Record ``log_tool_audit`` calls (their keyword arguments) instead of writing audit rows."""
    from app.core.audit_log import default_audit_logger

    calls: AuditCalls = []

    async def log_tool_audit(**kwargs: object) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(default_audit_logger, "log_tool_audit", log_tool_audit)
    return calls


@pytest.fixture
def fake_rate_db(''',
)

D = "tests/test_agent_dag.py"
rep(
    D,
    '''class _FakeSearch(HybridSearchEngine):
    def __init__(self, chunks=None):  # no super(): never touches the database
        self._chunks = chunks or [_chunk("c-1", 0.9), _chunk("c-2", 0.8)]

    async def search(self, query: str, *args: Any, **kwargs: Any) -> list[HybridSearchResult]:
        return list(self._chunks)
''',
    '''def _fake_search() -> StaticSearch:
    return StaticSearch([_chunk("c-1", 0.9), _chunk("c-2", 0.8)])
''',
)
rep(D, '    search_engine = _FakeSearch([_chunk("c-1", 0.9), _chunk("c-2", 0.8)])', "    search_engine = _fake_search()")
rep(D, "AgentGraph(search_engine=_FakeSearch())", "AgentGraph(search_engine=_fake_search())", 7)
rep(
    D,
    """    call_count = 0

    class MultiSearch(HybridSearchEngine):
        def __init__(self):  # no super(): never touches the database
            pass

        async def search(self, query: str, *args: Any, **kwargs: Any) -> list[HybridSearchResult]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return [_chunk("c-1", 0.9), _chunk("c-2", 0.8)]
            return [_chunk("c-2", 0.8), _chunk("c-3", 0.7)]

    graph = AgentGraph(search_engine=MultiSearch())""",
    """    def results(_query: str, call: int) -> list[HybridSearchResult]:
        if call == 1:
            return [_chunk("c-1", 0.9), _chunk("c-2", 0.8)]
        return [_chunk("c-2", 0.8), _chunk("c-3", 0.7)]

    graph = AgentGraph(search_engine=StaticSearch(results))""",
)
rep(
    D,
    """    searches: list[str] = []

    class RecordingSearch(HybridSearchEngine):
        def __init__(self):
            pass

        async def search(self, query: str, *args: Any, **kwargs: Any) -> list[HybridSearchResult]:
            searches.append(query)
            return [_chunk("c-1", 0.9)]
""",
    """    search = StaticSearch([_chunk("c-1", 0.9)])
""",
)
rep(D, "    graph = AgentGraph(search_engine=RecordingSearch())", "    graph = AgentGraph(search_engine=search)")
rep(D, '    assert searches == ["Compare model latency"]', '    assert search.queries == ["Compare model latency"]')
rep(
    D,
    """    class FlakySearch(HybridSearchEngine):
        def __init__(self):
            pass

        async def search(self, query: str, *args: Any, **kwargs: Any) -> list[HybridSearchResult]:
            if query == "model latency":
                raise RuntimeError("database down")
            return [_chunk("c-1", 0.9)]
""",
    """    def flaky(query: str, _call: int) -> list[HybridSearchResult]:
        if query == "model latency":
            raise RuntimeError("database down")
        return [_chunk("c-1", 0.9)]
""",
)
rep(D, "    graph = AgentGraph(search_engine=FlakySearch())", "    graph = AgentGraph(search_engine=StaticSearch(flaky))")
rep(D, "    async def fail_web_search(query: str):", "    async def fail_web_search(_query: str) -> WebSearchResult:")
rep(
    D,
    "    async def fail_routing(*args, **kwargs):",
    "    async def fail_routing(*_args: object, **_kwargs: object) -> NoReturn:",
)
rep(
    D,
    '    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]',
    "    tool_msgs = [m for m in final_state.agent_messages if isinstance(m, ToolMessage)]",
)
rep(
    D,
    '''    chunk = {
        "response_metadata": {
            "grounding_metadata": {
                "web_search_queries": ["query"],
                "grounding_chunks": [
                    {"web": {"title": "XSS", "uri": "javascript:alert(1)"}},
                    {"web": {"title": "Valid", "uri": "https://example.com/valid"}},
                ],
            }
        }
    }
    queries, sources = web_sources_from(type("Merged", (), chunk)())''',
    '''    merged = FakeChunk(
        response_metadata={
            "grounding_metadata": {
                "web_search_queries": ["query"],
                "grounding_chunks": [
                    {"web": {"title": "XSS", "uri": "javascript:alert(1)"}},
                    {"web": {"title": "Valid", "uri": "https://example.com/valid"}},
                ],
            }
        }
    )
    queries, sources = web_sources_from(merged)''',
)
rep(D, '    state.pending_tool_calls = [{"name": "web_search", "args": {}}]', '    state.pending_tool_calls = [{"name": "web_search", "args": {}, "id": "c1"}]')
rep(D, "    assert [t.name for t in build_tools(cast(HybridSearchEngine, None))] == [RAG_TOOL_NAME]", "    assert [t.name for t in build_tools(StaticSearch([]))] == [RAG_TOOL_NAME]")
rep(D, "from tests.conftest import FakeLLM\n", "from tests.conftest import AuditCalls, FakeChunk, FakeLLM, StaticSearch\n")
rep(D, "from typing import Any, cast\nfrom unittest.mock import AsyncMock\n", "from typing import NoReturn\n")
rep(D, "from app.rag.hybrid_search import HybridSearchEngine, HybridSearchResult\n", "from app.rag.hybrid_search import HybridSearchResult\n")

# audit recorder: replace the AsyncMock(side_effect=lambda **kw: ...) blocks with the fixture
import os

from ed import ROOT

p = os.path.join(ROOT, D)
raw = open(p, encoding="utf-8", newline="").read()
crlf = "\r\n" in raw
s = raw.replace("\r\n", "\n")
block = re.compile(
    r"    audit_calls = \[\]\n    monkeypatch\.setattr\(\n        default_audit_logger,\n        \"log_tool_audit\",\n        AsyncMock\(side_effect=lambda \*\*kw: audit_calls\.append\(kw\)\),\n    \)\n\n?"
)
n = len(block.findall(s))
s = block.sub("", s)
print("audit blocks removed:", n)
open(p, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)
print("ok")

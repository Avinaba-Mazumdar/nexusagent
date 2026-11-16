import os, re
from ed import ROOT, rep
D = "tests/test_agent_dag.py"
rep(
    D,
    '    tool_msgs = [m for m in final_state.agent_messages if getattr(m, "type", "") == "tool"]',
    "    tool_msgs = [m for m in final_state.agent_messages if isinstance(m, ToolMessage)]",
    4,
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

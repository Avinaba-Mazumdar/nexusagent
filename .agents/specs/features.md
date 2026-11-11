# NexusAgent — Implementation Board

> **Definition of Done (DoD) Quality Gate:**
> No task or phase may be checked `[x]` until:
>
> 1. **Tested**: Automated tests pass (`pnpm test` / `uv run pytest`)
> 2. **Linted**: Zero linter errors or warnings (`pnpm lint` / `uv run ruff check`)
> 3. **Formatted**: Code formatted cleanly (`uv run ruff format --check`)
> 4. **Verified**: Functionality verified on running servers
>
> Status words: `[Done]` everything checked, `[Partial]` some items open, `[Removed]` intentionally dropped.

---

### Phase 1: Single Schema & Shared DB [Done]

- [x] Single idempotent schema file `db/schema.sql` (applied manually in Neon SQL editor)
- [x] Removed startup runtime migrations (`migrations/` directory deleted)
- [x] Production and local dev share the same Neon database (`NEON_DATABASE_URL`)
- [x] Added `is_admin` and `machine_hash` to `users` model and table

### Phase 2: Rolling 24-Hour Quotas [Done]

- [x] `chat_usage` table replacing `rate_limit_buckets`
- [x] Guest users: 5 chats per rolling 24 hours, checked across user ID, device hash, machine hash, and client IP
- [x] Google users: 25 chats per rolling 24 hours, checked by user ID
- [x] Atomic quota deduction in Neon SQL (`count_chat_usage_24h` / `record_chat_usage`)
- [x] Header quota badge reflects rolling window

### Phase 3: Admin-Only PDF/Markdown RAG with LlamaIndex [Done]

- [x] Ingestion restricted to administrators (`is_admin = TRUE`); non-admins receive HTTP 403
- [x] Integrated LlamaIndex (`MarkdownNodeParser` + `SentenceSplitter`) for Markdown and PDF chunking
- [x] Pre-seeded 4 benchmark documents (Artificial Analysis, BenchLM, CursorBench, OpenRouter)
- [x] UI hides upload controls for non-admin users

### Phase 4: Agent Routing & Google Search Grounding [Done]

- [x] Free unmetered pre-filter: queries > 60 words or containing code blocks are refused instantly
- [x] Structured routing node using Gemini: `smalltalk`, `benchmark`, or `refuse`
- [x] Smalltalk / live facts handled via `google_search` tool binding with deduplicated web sources
- [x] Benchmark questions routed to hybrid RAG retriever → grounding check → answer synthesis
- [x] Rate limit failover across free-tier Gemini models

### Phase 5: Observability & Telemetry [Done]

- [x] Live token usage tracking (input, output, and total tokens per DAG step and session total)
- [x] Tool execution telemetry with duration and arguments summary (`hybrid_rag_search` and `google_search`)
- [x] Web sources rendered under assistant messages for live searches
- [x] Dynamic DAG node visualization based on execution path

### Phase 6: Public MCP Server [Done]

- [x] Official `mcp` SDK server mounted at `/mcp` (Streamable HTTP)
- [x] Public read-only access (no auth token required by connectors)
- [x] Standard `search` and `fetch` tools matching ChatGPT and Claude specifications
- [x] Per-IP rate limiting (60 req/min via `SlidingWindowCounter`)
- [x] Frontend Connect card with instructions for Claude, ChatGPT Developer mode, Cursor, and Claude Code

### Phase 7: Code Trim & Hardening [Done]

- [x] Removed token hold-back buffer and redaction logic
- [x] Removed diagram library and viewers in favor of clean Markdown tables and text
- [x] Scrubbing of sensitive keys and untrusted content delimiters preserved

### Phase 8: Rebrand & Documentation [Done]

- [x] Universal tagline: "NexusAgent: an open-source LLM benchmark assistant"
- [x] Updated README with technology index, rolling quotas, admin access, and MCP connection
- [x] Disclosed machine ID hashing and IP quota tracking in Privacy Policy
- [x] System Architecture and Active Board updated

### Phase 9: Bounded Tool-Calling Agent [Done]

- [x] Refactored LangGraph agent DAG to bounded tool-calling loop: `router -> refuse | chat | preload -> agent <-> tools`
- [x] Initial benchmark passages preloaded in `preload_node`, self-healing in direct `agent_node` calls
- [x] Extracted LLM routing & streaming to `apps/backend/app/agent/llm.py` and tools to `apps/backend/app/agent/tools.py`
- [x] Bounded loop safeguards: maximum 2 tool rounds, maximum 2 tool calls per round
- [x] Untrusted tool output wrapping in `<untrusted_tool_output>` XML boundaries with tag stripping
- [x] Citation validation: reports missing labels in `invalid_citations` and sets `uncited: true` when model cites no sources
- [x] Frontend observability panel and stream hook updated with `preload`, `agent`, and `tools` nodes, web search badges, and uncited warnings

### Phase 10: Security Audit

- [ ] `security-audit` skill run on the release commit; all confirmed findings of severity medium or higher fixed or accepted in writing in `roadmap.md`

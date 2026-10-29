# NexusAgent — Phased Implementation Board

> **Definition of Done (DoD) Quality Gate:**
> No task or phase may be checked `[x]` until:
>
> 1. **Tested**: Automated tests pass (`pnpm test` / `uv run pytest`)
> 2. **Linted**: Zero linter errors or warnings (`pnpm lint` / `uv run ruff check`)
> 3. **Formatted**: Code formatted cleanly (`pnpm format:check` / `uv run ruff format --check`)
> 4. **Verified**: End-to-end functionality visually or functionally verified on running servers
>
> Backend gate: `uv run pytest` must be green **offline**. Tests needing a live Neon instance are marked `@pytest.mark.db` and skip (not fail) when `NEON_DATABASE_URL` is absent.

---

### Phase 1: Scaffold Project [Completed]

- [x] Setup pnpm and Turborepo monorepo configuration
- [x] Init Next.js 16 App Router frontend (`apps/frontend`)
- [x] Init Python 3.14 FastAPI backend (`apps/backend`)
- [x] Setup Neon PostgreSQL connection and environment
      Verification: Run local dev servers (`pnpm dev:fe`, `pnpm dev:be`), verify health endpoint and DB connection.

### Phase 2: Base UI & Database Schemas [Completed]

- [x] Setup shadcn/ui components and theme tokens
- [x] Setup Neon PostgreSQL schema migrations (UUID, pgvector, core tables)
- [x] Setup frontend and backend API communication routes
- [x] Setup 4-zone command center UI layout
      Verification: Run local servers, inspect Neon tables, verify frontend renders layout and shadcn components without errors.

### Phase 3: User Authentication [Completed]

- [x] Backend guest pass issuance & Argon2 password hashing (`core/auth.py`)
- [x] Frontend guest sign-in button wiring & session state header
- [x] Google OAuth client setup & backend token verification flow
- [x] Auth token persistence (cookies/localStorage) & API client interceptor
      Verification: Click "Guest Sign In" in UI -> Header updates with active user session and quota badge; test Google sign-in flow.

### Phase 4: Document Ingestion & Parsing [Completed]

- [x] Build document upload endpoint (`POST /api/documents/upload`)
- [x] Implement LlamaIndex markdown hierarchical parser (`rag/parser.py`)
- [x] Split content into 800-char chunks with line-level section metadata
- [x] Persist parsed documents and chunks into Neon `documents` and `document_chunks`
      Verification: Upload sample RFC markdown, verify database contains document record and chunk rows with line metadata.

### Phase 5: Vector Embeddings & Hybrid Search [Completed]

- [x] Implement dense embedding generation using pgvector HNSW index
- [x] Implement full-text BM25 lexical search using Postgres `tsvector` GIN index
- [x] Implement Reciprocal Rank Fusion (RRF) ranking algorithm (`rag/hybrid_search.py`)
- [x] Expose search endpoint `POST /api/rag/search`
      Verification: Query RFC text via search endpoint, verify top-K results return ranked chunks with similarity scores and line numbers.

### Phase 6: AST Python Code Execution Sandbox [Removed — audit S-01]

The AST-denylist sandbox was escapable (`random._os.system(...)`, `[eval][0](...)`) and ran on the API host, so it was a remote-code-execution vector. Removed: `core/sandbox.py`, `POST /api/sandbox/run`, the MCP `python_sandbox` tool, the agent `sandbox` node, and `packages/contracts/src/sandbox.ts`. Regression guard: `tests/test_mcp.py::test_code_execution_is_not_exposed`. Reintroduction requires the isolation boundary defined in `AGENTs.md` ASI-05.

### Phase 7: LangGraph Agent DAG Pipeline [Completed]

- [x] Define strongly-typed `AgentState` schema (`agent/state.py`)
- [x] Implement planner, retriever, and synthesizer nodes (`agent/graph.py`)
- [x] Implement reflection critic node with loop-back condition (capped at 10 iterations)
- [x] Wire hybrid search into agent graph
      Verification: Invoke agent via test script, assert graph executes state transitions (plan -> retrieve -> reflect -> synthesize).

### Phase 8: Real-Time SSE Streaming & Observability [Completed]

- [x] Implement FastAPI Server-Sent Events endpoint `POST /api/agent/stream`
- [x] Stream structured events (`plan`, `node_start`, `tool_call`, `tool_result`, `token`, `done`)
- [x] Build Next.js SSE client hook (`hooks/useAgentStream.ts`)
- [x] Implement reactive execution DAG tracker in observability panel
      Verification: Trigger streaming query from UI or curl, verify incremental SSE tokens and node status events arrive in real-time.

### Phase 9: Interactive Canvas & Diagram Rendering [Completed]

- [x] Implement streaming Markdown renderer with code syntax highlighting
- [x] Integrate dynamic Mermaid.js SVG rendering with pan and zoom controls
- [x] Implement interactive Citation Pills with line jump and hover previews
- [x] Wire agent stream output to canvas viewer
      Verification: Stream response containing Mermaid code block and citations; verify SVG diagram renders and citation click highlights source.

### Phase 10: Model Context Protocol (MCP v2) Integration [Completed]

- [x] Implement FastAPI MCP SSE endpoint (`/api/mcp/sse`) and CLI stdio entrypoint
- [x] Register tools (`hybrid_rag_search`, `mcp_sql_audit`) with Pydantic schemas (`python_sandbox` removed — audit S-01)
- [x] Build frontend MCP Inspector panel to test tool calls and view JSON-RPC payloads
- [x] Add client connection configuration for Claude Desktop and Cursor
      Verification: Connect Claude or run MCP Inspector UI, call `hybrid_rag_search`, verify valid JSON-RPC response.

### Phase 11: Human-in-the-Loop & Security Controls [Completed]

- [x] Implement HITL approval modal in UI and backend pause/resume endpoint (`/api/agent/approval`)
- [x] Implement prompt injection delimiters (`<untrusted_document_context>`) and UUID canary tokens
- [x] Implement token-bucket rate limiter for guest and registered users
- [x] Add immutable audit logging to `tool_audit_logs` table
      Verification: Trigger tool requiring approval, verify agent suspends until approved; exceed rate limit and verify HTTP 429.

### Phase 12: Deterministic Showcase & 1-Click Guest Experience [Completed]

- [x] Bundle pre-seeded knowledge benchmarks (BenchLM, CursorBench, OpenRouter, Artificial Analysis)
- [x] Implement deterministic cached execution simulator for zero-cost demos
- [x] Polish 1-Click Guest experience with pre-loaded quota badge
- [x] Run end-to-end demo flow validation
      Verification: Open app in guest mode with zero API keys, run demo scenario, verify instant cached DAG trace and rendered diagram.

### Post-Phase-12 Sturdiness Pass [Applied]

- [x] Hermetic offline suite restored: DB-bound showcase/HITL-audit tests marked `@pytest.mark.db` (skip offline, pass against live Neon)
- [x] HITL approval timeout configurable via `HITL_APPROVAL_TIMEOUT_SECONDS` (30s human-paced default; test conftest overrides to 1s)
- [x] New guards: unresolved approvals fail closed on timeout; test asserts production default stays human-paced
- [x] `tool_audit_logs` writes retry once and log at error level before degrading to the memory ring

### Security-Hardening Pass (Applied)

- [x] MCP lockdown: `/api/mcp/{v1,sse,messages}` now require Bearer auth; `mcp_sql_audit` runs single-statement allowlisted queries in a read-only transaction with a mutating/privileged-function denylist (`setval`, `pg_advisory_lock`, `pg_read_file`, `pg_sleep`, …) and bounded timeout
- [x] Mermaid XSS fix: `securityLevel: 'strict'` + SVG sanitizer (scripts, foreignObject, event handlers, `javascript:` URLs stripped) in `MermaidViewer`
- [x] BYOK hardening: `X-User-API-Key` validated against a provider prefix/length allowlist (`validate_byok_key`); junk keys fall back to the rate-limited tier
- [x] Quota keying: `get_client_ip` uses the socket IP unless `TRUST_PROXY_HEADERS=true` (X-Forwarded-For rotation no longer bypasses guest quota)
- [x] HITL approval ownership: `resolve_approval` binds the approval to its owning session; cross-session resolution is rejected
- [x] `/api/agent/audit-logs` reads persisted `tool_audit_logs` rows (memory ring only as fallback)
- [x] Indirect injection defense: retriever scans retrieved chunks (`sanitize_retrieved_chunks`), drops injected content, prunes citations, surfaces an observability warning

### Phase 13: FastMCP Transition, Gemini 3.x Upgrade & Live Benchmark Vault [Completed]

- [x] Migrate Model Context Protocol server from manual custom router to official `FastMCP` (`apps/backend/app/routes/mcp.py`)
- [x] Integrate LangSmith `@traceable` decorators across agent execution nodes
- [x] Fix guest session quota retention across browser page refreshes
- [x] Upgrade LLM synthesis to active Gemini frontier models (`gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.5-flash`) with automatic cascading fallbacks
- [x] Implement robust offline deterministic synthesis fallback with sanitized citations, Mermaid diagrams, and conversational greeting handling
- [x] Ingest live scraped benchmark datasets across Artificial Analysis, BenchLM (Bench-Align v5), CursorBench 4.0, and OpenRouter
- [x] Modernize UI with light-mode enterprise palette (`#F4F5F8` canvas, `#004EA1` signature blue) and mobile responsive DAG pipeline

# NexusAgent — Implementation Board

> **Definition of Done (DoD) Quality Gate:**
> No task or phase may be checked `[x]` until:
>
> 1. **Tested**: Automated tests pass (`pnpm test` / `uv run pytest`)
> 2. **Linted**: Zero linter errors or warnings (`pnpm lint` / `uv run ruff check`)
> 3. **Formatted**: Code formatted cleanly (`uv run ruff format --check`)
> 4. **Verified**: Functionality verified on running servers
>
> Backend gate: `uv run pytest` must be green **offline**. Tests needing a live Neon instance are marked `@pytest.mark.db` and skip (not fail) when `TEST_DATABASE_URL` is absent.
>
> Status words: `[Done]` everything checked, `[Partial]` some items open, `[Removed]` intentionally dropped (kept for history).

---

### Phase 1: Scaffold [Done]

- [x] pnpm + Turborepo monorepo
- [x] Next.js 16 App Router frontend (`apps/frontend`)
- [x] Python 3.14 FastAPI backend (`apps/backend`)
- [x] Neon PostgreSQL connection, migrations applied at startup (`migrations/`)

### Phase 2: Base UI & Database [Done]

- [x] shadcn/ui primitives and Tailwind v4 theme tokens (`styles/globals.css`)
- [x] Schema migrations (users, buckets, documents, chunks, conversations, messages, audit log)
- [x] Frontend/backend API client (`lib/api-client.ts`)
- [x] Three-column chat layout: workspace sidebar, chat canvas, observability panel (+ mobile tab bar)

### Phase 3: Authentication [Done]

- [x] Guest pass (device-bound, IP-throttled)
- [x] Google sign-in: ID token verified locally against Google's keys; accounts keyed on Google `sub`
- [x] Revocable sessions (`token_version`, `POST /api/auth/logout`), 7-day cap on refresh chains
- [Removed] Password auth (Argon2): replaced by Google OAuth + guest JWTs

### Phase 4: Document Ingestion [Done]

- [x] `POST /api/documents/upload` (1 MB, strict UTF-8, extension-based type, chunk cap, one upload at a time per user)
- [x] LlamaIndex markdown parser, ~800-char chunks with line metadata (`rag/parser.py`)
- [x] Persist documents and chunks transactionally; `DELETE /api/documents/{id}`

### Phase 5: Hybrid Search [Done]

- [x] Dense pgvector (HNSW) search, filtered to the pinned embedding model
- [x] Lexical tsvector search (OR of query terms)
- [x] Reciprocal Rank Fusion (`rag/hybrid_search.py`); falls back to lexical-only if embedding fails
- [x] `POST /api/rag/search`

### Phase 6: Code Execution Sandbox [Removed]

The AST-denylist sandbox was escapable and ran on the API host. Removed together with its route, MCP tool and agent node. Regression guard: `tests/test_mcp.py::test_code_execution_is_not_exposed`. Reintroduction requires the isolation boundary in `AGENTs.md` (ASI-05).

### Phase 7: Agent Pipeline [Done]

- [x] Typed `AgentState` (`agent/state.py`)
- [x] Nodes: planner → retriever → grounding → synthesizer (`agent/graph.py`)
- [x] Grounding check reports `grounded | weak | none` from retrieval results
- [Removed] Reflection critic with re-planning loop: it was a constant formula and never looped

### Phase 8: Streaming & Observability [Done]

- [x] `POST /api/agent/stream` (SSE): `start`, `node_start`, `plan`, `tool_result`, `grounding`, `token`, `done`, `error`
- [x] `token` events carry the model's chunks as they arrive
- [x] `useAgentStream` hook and observability panel (client-measured first-token and total latency)
- [ ] `tool_call` event (the pipeline emits `tool_result` only)

### Phase 9: Canvas [Done]

- [x] Markdown renderer on react-markdown (tables, callouts, code blocks with copy)
- [x] Mermaid diagrams with pan/zoom, sanitised SVG
- [x] Citations: answers cite `[S1]`; pills open a dialog with the full source passage
- [ ] Syntax highlighting in code blocks

### Phase 10: MCP [Partial]

- [x] Hand-rolled JSON-RPC 2.0 server: HTTP gateway, SSE transport, stdio (`python -m app.mcp.server`)
- [x] `hybrid_rag_search` with Pydantic-validated arguments, metered per user, results wrapped as untrusted content
- [x] Frontend MCP inspector
- [ ] Client configuration snippets for Claude Desktop and Cursor
- [ ] Migrate to the official `fastmcp` SDK (current server is custom and spec-version `2024-11-05`)

### Phase 11: Security Controls [Done]

- [x] `<untrusted_document_context>` delimiters, canary token (never forwarded to the client), secret scrubbing
- [x] Instruction-like retrieved text is reported to the user (`injectionWarnings`)
- [x] Token-bucket quota per user (not per IP), per-IP caps for guests, auth-endpoint throttles
- [x] `tool_audit_logs` is append-only by database trigger; 30-day retention via `scripts/prune_guests.py`
- [x] Per-request CSP nonce (`proxy.ts`), no script `unsafe-inline`
- [Removed] Human-in-the-loop approval: all tools are read-only, so there is nothing to approve

### Phase 12: Demo Experience [Partial]

- [x] Pre-seeded benchmark knowledge base (`knowledge_base/`, `scripts/seed_kb.py`)
- [x] One-click guest access with quota badge and refill time
- [x] Source URL and retrieval date for every benchmark table (knowledge base re-scraped 2026-10-30)
- [Removed] Deterministic offline simulator: a Gemini API key is required for answers and uploads

### Phase 13: Quality [Partial]

- [x] Offline backend suite and frontend suite green; CI workflow in `.github/workflows/ci.yml`
- [x] Route across all Gemini free-tier text models (`GEMINI_MODELS`, `ModelRouter`); a rate-limited model is skipped until its quota resets
- [x] Generate `packages/contracts` types from the backend OpenAPI schema (`pnpm contracts:generate`; CI fails on drift)
- [Removed] LangSmith tracing (data privacy)

# NexusAgent — System Architecture

This document describes what the code does today. Where something is **not implemented** it says so. The database schema lives only in [`migrations/`](../../migrations); this file does not repeat it.

---

## 1. What it is

A chat application that answers architecture and AI-benchmark questions with cited sources. Questions are answered by Gemini over a hybrid (vector + keyword) search of a bundled benchmark knowledge base and the user's own uploaded Markdown/text documents. The same search is exposed to external agents through a Model Context Protocol (MCP) server.

```
Browser (Next.js 16)                         FastAPI backend                      External
┌──────────────────────┐   REST + SSE    ┌──────────────────────────┐
│ Chat canvas          │ ──────────────▶ │ routes/  auth, agent,    │ ──▶ Gemini API (answers, embeddings)
│ Workspace sidebar    │                 │   documents, rag, chat,  │
│ Observability panel  │ ◀────────────── │   mcp, health            │ ──▶ Google (ID-token signing keys)
│ MCP inspector        │   tokens (SSE)  │ agent/   LangGraph       │
└──────────────────────┘                 │ rag/     parser, search  │ ──▶ Neon PostgreSQL 18
                                         │ mcp/     JSON-RPC server │       (pgvector + tsvector)
 Claude Desktop / Cursor ── MCP (HTTP/SSE/stdio) ─▶ core/ auth, limits, audit, guardrails
```

---

## 2. Stack

| Layer    | Technology                                                                                                                                                                                                                                     |
| -------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | Next.js 16 (App Router, React 19, React Compiler), TypeScript, Tailwind CSS v4, Radix UI primitives, Zustand, react-markdown, Mermaid                                                                                                          |
| Backend  | Python 3.14, FastAPI, asyncpg, LangGraph, LangChain Google GenAI                                                                                                                                                                               |
| Data     | Neon PostgreSQL 18: `pgvector` (HNSW, cosine) and `tsvector` (GIN)                                                                                                                                                                             |
| Models   | Chat: `GEMINI_MODELS` (default: the eight Gemini free-tier text models, `gemini-3.8-flash` first; `ModelRouter` skips a model that returned 429 until its quota resets). Embeddings: `EMBEDDING_MODEL` (default `gemini-embedding-001`, 768-d) |
| Monorepo | pnpm workspaces + Vite+ (`vp`: oxlint, oxfmt, task runner); `uv` for Python                                                                                                                                                                    |

Authoritative versions are in `apps/backend/pyproject.toml` and `apps/frontend/package.json`.

---

## 3. Repository layout

```
apps/backend/app/
  main.py            app, CORS, routers, DB-outage handler
  config.py          settings (env), production safety checks
  core/              auth (JWT, Google), rate_limiter, audit_log, security_guardrails
  db/                neon.py (all SQL), models.py (Pydantic), migrations.py (runner)
  agent/             state.py, graph.py (the pipeline)
  rag/               parser.py, embeddings.py, hybrid_search.py
  mcp/               protocol.py, registry.py (tools/resources), dispatch.py, server.py (stdio)
  routes/            health, auth, documents, rag, agent, chat, mcp
apps/frontend/       app/ (pages), proxy.ts (CSP), components/, hooks/, lib/
packages/contracts/  shared TypeScript types (hand-written)
migrations/          core schema, applied once at startup under an advisory lock
knowledge_base/      Markdown benchmark corpus; scripts/seed_kb.py embeds it
scripts/             seed_kb.py, prune_guests.py (guests + audit retention)
```

---

## 4. Request flows

### 4.1 Agent run (`POST /api/agent/stream`, Server-Sent Events)

1. Authenticate (Bearer JWT). Validate `documentId` access. Classify intent once (`greeting | architectural | out_of_scope`).
2. Charge one quota token unless the query is out of scope. Resume a saved conversation (Google users only) and load the last `CHAT_HISTORY_MESSAGES` messages.
3. Run the LangGraph pipeline, a straight line with no loops:

    `planner → retriever → grounding → synthesizer`

    - **planner**: mints the per-run canary token and builds the plan; out-of-scope queries are answered with a fixed refusal and skip the rest.
    - **retriever**: hybrid search (limit 5), sanitises chunks, labels them `S1..Sn`, records an audit row.
    - **grounding**: reports `grounded | weak | none` from the retrieved chunks. It is a plain function, not an LLM step.
    - **synthesizer**: streams Gemini's answer. The prompt contains the labelled, delimited sources; the answer cites `[S1]`.

4. SSE events: `start`, `node_start`, `plan`, `tool_result` (citations, `injectionWarnings`), `grounding`, `token` (the model's chunks), then `done` or `error`. The turn is saved (Google users) **before** `done`, so `done` carries `conversationId`.
5. On error, or when a disconnect happens before any output, the charged token is refunded.

### 4.2 Document ingestion (`POST /api/documents/upload`)

Validate (extension, strict UTF-8, ≤ 1 MB, ≤ 400 chunks) → deduplicate by SHA-256 per user → parse in a worker thread → embed in batches of 100 → store document and chunks in one transaction → charge `ceil(chunks/100)` tokens. One upload per user at a time. `DELETE /api/documents/{id}` removes an upload and its chunks.

### 4.3 Hybrid search

The embedding + dense query run concurrently with the lexical query. Lexical search ORs the alphanumeric query terms. Results are fused with Reciprocal Rank Fusion. If the embedding call fails, search degrades to lexical-only. Dense search only considers chunks embedded with the current `EMBEDDING_MODEL`.

### 4.4 MCP

Transports: `POST /api/mcp/v1` (HTTP JSON-RPC), `GET /api/mcp/sse` + `POST /api/mcp/messages` (SSE sessions), and `python -m app.mcp.server` (stdio, local and unmetered). Methods: `initialize`, `ping`, `tools/list`, `tools/call`, `resources/list`, `resources/read`. One tool, `hybrid_rag_search`, whose argument schema is generated from its Pydantic model. The SSE + `POST /messages` transport follows protocol revision `2024-11-05`; newer MCP revisions replace it with Streamable HTTP, so verify your client (for example Claude Desktop or Cursor) before relying on it. HTTP transports require a Bearer token and meter `tools/call`. **Not implemented:** an MCP client, and the official `fastmcp` SDK.

---

## 5. Data model (summary)

`users` (guest or Google; `google_sub`, `token_version`), `rate_limit_buckets` (one row per user), `documents` / `document_chunks` (embedding, `embedding_model`, generated `search_vector`, JSON metadata with line numbers), `agent_conversations` / `messages`, `tool_audit_logs`. Definitions live in `migrations/20260901000000_core_schema.sql`.

---

## 6. Limits and concurrency

- **Quota**: one atomic upsert per consume on `rate_limit_buckets` (hourly refill). Guests 5/hour, Google users 25/hour (configurable). Guests also have per-IP signup and request caps held in process memory, so run **one API worker**.
- **Sessions**: JWTs carry `tv` (token version) and `auth_time`. Logout bumps `token_version`, revoking all tokens. Refresh cannot extend a login beyond `MAX_SESSION_AGE_DAYS`.
- **Failure mode**: if Postgres is unreachable, requests get `503` with `Retry-After`; production refuses to start without a database.
- **MCP SSE sessions** (max 3 per user, 200 total) live in memory.
- **Per-process state**: the guest and auth per-IP counters (`SlidingWindowCounter`), the MCP SSE sessions and the model router's cool-downs live in process memory. They reset on every restart or cold start and are not shared between instances, so the API refuses to start in production when `WEB_CONCURRENCY` is above 1 (a free Render instance is a single instance).
- **Request bodies** are capped before parsing and authentication: 1 MB + 16 KB on `/api/documents/upload`, 64 KB elsewhere (`MAX_UPLOAD_REQUEST_BYTES`, `MAX_JSON_REQUEST_BYTES`). Cap them at the reverse proxy as well.
- **Client IP**: per-IP limits use the socket address unless `TRUSTED_PROXY_HOPS` is set; then the `X-Forwarded-For` entry added by the nth trusted proxy from the right is used (the left-most entries are client-controlled and ignored).
- **Dense search** sets `hnsw.iterative_scan = relaxed_order` on pgvector 0.8+ (otherwise `hnsw.ef_search = 200`), so the document filter cannot starve the HNSW candidates.

---

## 7. Security

| OWASP ASI                  | What is implemented                                                                                                                                                                                                                                                                                                              |
| -------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ASI-01 Prompt injection    | Retrieved text is escaped and wrapped in `<untrusted_document_context>`; the system prompt forbids following it. Instruction-like chunks are kept inside the delimiters and reported to the user. A per-run canary token is scanned for in the streamed output and never forwarded. These reduce risk; they do not eliminate it. |
| ASI-02 Data disclosure     | Credentials and private keys in ingested text are redacted before storage and prompting.                                                                                                                                                                                                                                         |
| ASI-04 Data poisoning      | Uploads are private to the uploader; the seeded corpus is read-only.                                                                                                                                                                                                                                                             |
| ASI-05 Code execution      | None. No user- or model-supplied code is executed. A previous AST sandbox was removed as escapable; any future one needs OS-level isolation.                                                                                                                                                                                     |
| ASI-06 Excessive agency    | The only tool is a read-only search. There is no approval gate because there is nothing mutating to approve; adding such a tool requires one.                                                                                                                                                                                    |
| ASI-07 Resource exhaustion | Per-user token bucket on every paid path (agent, upload, search, MCP); per-IP guest caps; auth-endpoint throttles; upload size and chunk caps.                                                                                                                                                                                   |
| ASI-08 Protocol            | MCP tool arguments validated by Pydantic; results wrapped as untrusted content; session ownership checked.                                                                                                                                                                                                                       |
| ASI-10 Audit               | `tool_audit_logs` is append-only by trigger; the retention job (`scripts/prune_guests.py`, 30 days) is the only deleter.                                                                                                                                                                                                         |

Web layer: per-request CSP nonce with `'strict-dynamic'` (`proxy.ts`), no script `unsafe-inline`; HSTS, `X-Frame-Options`, `nosniff`; Mermaid in `securityLevel: strict` with DOMPurify; model output rendered without raw HTML; Google ID tokens verified locally (signature, audience, issuer, expiry) and accounts keyed on `sub`; production hides `/docs` and database details on `/api/health`.

Known limits: tokens live in `localStorage` (an XSS would expose them; the CSP is the mitigation); Gemini API data use depends on the API plan (see the privacy policy).

---

## 8. Operations

- Run one process: `uvicorn app.main:app --workers 1` (enforced via `WEB_CONCURRENCY`).
- Environment: see `apps/backend/.env.example` and `apps/frontend/.env.example`. `NEXT_PUBLIC_API_URL` is required at frontend build time in production.
- After changing `EMBEDDING_MODEL`, run `uv run python scripts/seed_kb.py`; seeded document IDs are stable across runs. Re-upload your own documents so they are embedded with the new model.
- `.github/workflows/maintenance.yml` runs `scripts/prune_guests.py` every 6 hours (guests older than 24 h, audit rows older than 30 days); it needs the repository secret `NEON_DATABASE_URL`.

---

## 9. Testing

- Backend: `cd apps/backend && uv run pytest -q`. Offline by default; tests marked `db` need `TEST_DATABASE_URL` pointing at a disposable database.
- Frontend: `pnpm --filter @nexusagent/frontend test` (Vitest + Testing Library), plus `typecheck` and `lint`.
- CI: `.github/workflows/ci.yml` runs both suites, lint, format check and the production build.

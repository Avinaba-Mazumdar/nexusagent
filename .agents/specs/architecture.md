# NexusAgent — System Architecture

This document describes what the code does today. The database schema lives only in [`db/schema.sql`](../../db/schema.sql); this file does not repeat it.

---

## 1. What it is

An open-source LLM benchmark assistant that evaluates frontier AI models against benchmark data (Artificial Analysis, BenchLM, CursorBench, and OpenRouter metrics). Questions are classified by a router: smalltalk and live queries (e.g. weather) use Gemini with Google Search grounding; benchmark questions use a hybrid (vector + keyword) search over the pre-indexed corpus. The knowledge base is also exposed to external AI assistants (Claude, ChatGPT, Cursor, Claude Code) through a public, read-only Model Context Protocol (MCP) server.

```
Browser (Next.js 16)                         FastAPI backend                      External
┌──────────────────────┐   REST + SSE    ┌──────────────────────────┐
│ Chat canvas          │ ──────────────▶ │ routes/  auth, agent,    │ ──▶ Gemini API (answers, embeddings)
│ Workspace sidebar    │                 │   documents, rag, chat,  │ ──▶ Google Search Grounding (live facts)
│ Observability panel  │ ◀────────────── │   health                 │ ──▶ Google (ID-token signing keys)
│ Connect MCP card     │   tokens (SSE)  │ agent/   LangGraph DAG   │
└──────────────────────┘                 │ rag/     LlamaIndex, RRF │ ──▶ Neon PostgreSQL 18
                                         │ mcp/     FastMCP server  │       (pgvector + tsvector)
 Claude / ChatGPT / Cursor ─ MCP (/mcp) ─▶ core/    quotas, audit   │
```

---

## 2. Stack

| Layer    | Technology                                                                                                                                                      |
| -------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | Next.js 16 (App Router, React 19, React Compiler), TypeScript, Tailwind CSS v4, shadcn/ui primitives, Zustand, react-markdown                                   |
| Backend  | Python 3.14, FastAPI, asyncpg, LangGraph, LangChain Google GenAI, LlamaIndex, FastMCP                                                                           |
| Data     | Neon PostgreSQL 18: `pgvector` (HNSW, cosine distance) and `tsvector` (GIN)                                                                                     |
| Models   | Chat: `GEMINI_MODELS` (free-tier text models, `gemini-3.8-flash` first; failover on 429). Embeddings: `EMBEDDING_MODEL` (default `gemini-embedding-001`, 768-d) |
| Monorepo | pnpm workspaces + Vite+ (`vp`: oxlint, oxfmt, task runner); `uv` for Python                                                                                     |

---

## 3. Repository layout

```
apps/backend/app/
  main.py            app, CORS, routers, mcp mounting, rate limiter, DB-outage handler
  config.py          settings (env), production safety checks
  core/              auth (JWT, Google), rate_limiter (rolling 24h quota), audit_log, security_guardrails
  db/                neon.py (all SQL), models.py (Pydantic & wire contracts)
  agent/             state.py, graph.py (LangGraph DAG), sse.py, run.py
  rag/               ingest.py (LlamaIndex PDF/Markdown parser), embeddings.py, hybrid_search.py
  mcp/               server.py (FastMCP Streamable HTTP server at /mcp)
  routes/            health, auth, documents (admin only), rag, agent, chat
apps/frontend/       app/ (pages), proxy.ts (CSP), components/, hooks/, lib/
packages/contracts/  shared TypeScript types & OpenAPI wire schemas
db/                  schema.sql (single source of truth, applied by hand in Neon)
knowledge_base/      Markdown benchmark corpus; scripts/seed_kb.py embeds it
scripts/             seed_kb.py, prune_guests.py (guests + audit retention)
```

---

## 4. Request flows

### 4.1 Agent run (`POST /api/agent/stream`, Server-Sent Events)

1. Authenticate (Bearer JWT). Validate `documentId` access.
2. Free, unmetered pre-filter: queries over 60 words or containing code blocks are refused immediately (`REFUSAL`) without reserving quota.
3. For all other queries, reserve one chat quota token against the rolling 24-hour limit.
4. Run the LangGraph DAG pipeline:
    - **router**: Calls `gemini-2.5-flash-lite` with structured output (`RouteDecision`) to classify into `smalltalk`, `benchmark`, or `refuse`.
    - On `refuse`: Returns fixed `REFUSAL`.
    - On `smalltalk`: Routed to **chat** node. Binds `google_search` tool for live facts (e.g. weather). Extracts search queries and web sources from grounding metadata.
    - On `benchmark`: Routed to **retriever** → **grounding** → **answer**.
        - `retriever`: Executes hybrid RAG search (vector + BM25 with RRF, limit 5), sanitizes chunks, labels them `[S1]..[Sn]`, and logs to `tool_audit_logs`.
        - `grounding`: Deterministic lexical check reporting `grounded | weak | none`.
        - `answer`: Streams synthesis prompt with delimited reference context. Inline citations cite `[S1]..[Sn]`.
5. SSE events: `start`, `node_start`, `plan`, `usage` (token counts per step), `tool_call` (`hybrid_rag_search` or `google_search`), `tool_result` (with duration and citations), `grounding`, `token` (streamed text), and `done` (with summary metadata and `webSources`).
6. Turn persistence: Google-authenticated users have their turns saved to `messages` for persistent chat history.

### 4.2 Document ingestion (`POST /api/documents/upload`)

1. Admin-only: Enforces `is_admin = TRUE`. Non-admins receive HTTP 403.
2. File validation: PDF (`.pdf`) or Markdown (`.md`), strictly valid, up to 1 MB.
3. Parsing: LlamaIndex `MarkdownElementNodeParser` for Markdown; PyPDF / LlamaIndex `SentenceSplitter` (chunk size 512, overlap 64) for PDF.
4. Storage: Embeds chunks in batches of 100 with `gemini-embedding-001`, and inserts documents + document_chunks in Neon PostgreSQL within a single transaction.

### 4.3 Hybrid search (`POST /api/rag/search`)

Dense vector search (`pgvector` cosine similarity) and sparse keyword search (`tsvector` BM25) run concurrently against `document_chunks`. Scores are combined via Reciprocal Rank Fusion (RRF, $k=60$). If vector search fails, degrades gracefully to lexical-only search.

### 4.4 Public MCP server (`/mcp`)

FastMCP Streamable HTTP server mounted at `/mcp` (e.g. `https://nexusagent-oss.onrender.com/mcp` in production, or `http://localhost:8000/mcp` locally):

- Stateless HTTP mode with JSON response formatting.
- Rate-limited to 60 requests/minute per client IP via `SlidingWindowCounter`.
- Two tools following ChatGPT / Claude standard connector specifications:
    - `search(query: str) -> dict`: Searches the benchmark knowledge base and returns up to 8 matching passages with `id`, `title`, and `url`.
    - `fetch(id: str) -> dict`: Retrieves the full text and metadata of a specific passage by `document_id:chunk_id`.

---

## 5. Quotas and Limits

- **Rolling 24-hour quotas**:
    - Tracked in `chat_usage` table. Quota remaining = limit minus count of rows in the last 24 hours.
    - Guests: 5 chats / 24h, enforced against guest UUID, device hash, machine hash, and client IP.
    - Google accounts: 25 chats / 24h, keyed by user ID.
- **Single-worker deployment**: In-memory rate limiters (`SlidingWindowCounter`) and MCP session lifecycle require running one API worker (`uvicorn app.main:app --workers 1`).
- **Request size caps**: 1 MB + 16 KB on `/api/documents/upload`, 64 KB elsewhere (`MAX_UPLOAD_REQUEST_BYTES`, `MAX_JSON_REQUEST_BYTES`).

---

## 6. Security

- **OWASP ASI-01 (Prompt injection)**: Retrieved document chunks are sanitized, delimiter tags escaped, and wrapped in strict `<untrusted_document_context>` XML tags.
- **OWASP ASI-02 (Sensitive info disclosure)**: Private keys, AWS keys, JWTs, and database credentials are automatically scrubbed from ingested text via regex patterns.
- **OWASP ASI-04 (Data poisoning)**: Knowledge base documents are uploaded and managed exclusively by administrators (`is_admin = TRUE`).
- **OWASP ASI-06 (Excessive agency)**: Tools are strictly read-only (`search`, `fetch`, `google_search`).
- **OWASP ASI-10 (Audit)**: `tool_audit_logs` is protected by database triggers that reject `UPDATE` and `DELETE` queries except by the maintenance retention job.

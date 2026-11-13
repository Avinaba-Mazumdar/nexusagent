# NexusAgent — System Architecture

This document describes what the code does today. The database schema lives only in [`db/schema.sql`](../../db/schema.sql); this file does not repeat it.

---

## 1. What it is

An open-source LLM benchmark assistant that evaluates frontier AI models against benchmark data (Artificial Analysis, BenchLM, CursorBench, and OpenRouter metrics). Questions are classified by a router: smalltalk and live queries (e.g. weather) use Gemini with Google Search grounding; benchmark questions use a bounded agent loop (`preload` initial RAG retrieval → `agent` model ⟷ `tools` node executing `hybrid_rag_search` and `web_search`) with citation validation. The knowledge base is also exposed to external AI assistants (Claude, ChatGPT, Cursor, Claude Code) through a public, read-only Model Context Protocol (MCP) server.

```
Browser (Next.js 16)                         FastAPI backend                      External
┌──────────────────────┐   REST + SSE    ┌──────────────────────────┐
│ Chat canvas          │ ──────────────▶ │ routes/  auth, agent,    │ ──▶ Gemini API (answers, embeddings)
│ Workspace sidebar    │                 │   documents, rag, chat,  │ ──▶ Google Search Grounding (live facts)
│ Observability panel  │ ◀────────────── │   health                 │ ──▶ Google (ID-token signing keys)
│ Connect MCP card     │   tokens (SSE)  │ agent/   LangGraph DAG   │
└──────────────────────┘                 │ rag/     LlamaIndex, RRF │ ──▶ Neon PostgreSQL 18
                                         │ mcp/     official SDK    │       (pgvector + tsvector)
 Claude / ChatGPT / Cursor ─ MCP (/mcp) ─▶ core/    quotas, audit   │
```

---

## 2. Stack

| Layer    | Technology                                                                                                                                                           |
| -------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Frontend | Next.js 16 (App Router, React 19, React Compiler), TypeScript, Tailwind CSS v4, shadcn/ui primitives, Zustand, react-markdown                                        |
| Backend  | Python 3.14, FastAPI, asyncpg, LangGraph, LangChain Google GenAI, LlamaIndex, official `mcp` Python SDK (`MCPServer`)                                                |
| Data     | Neon PostgreSQL 18: `pgvector` (HNSW, cosine distance) and `tsvector` (GIN)                                                                                          |
| Models   | Chat: `TEXT_MODELS` (`GEMINI_MODELS` best-first, then hosted `GEMMA_MODELS`; failover on 429). Embeddings: `EMBEDDING_MODEL` (default `gemini-embedding-001`, 768-d) |
| Monorepo | pnpm workspaces + Vite+ (`vp`: oxlint, oxfmt, task runner); `uv` for Python                                                                                          |

---

## 3. Repository layout

```
apps/backend/app/
  main.py            app, CORS, routers, mcp mounting, rate limiter, DB-outage handler
  config.py          settings (env), production safety checks
  core/              auth (JWT, Google), rate_limiter (rolling 24h quota), audit_log, security_guardrails
  db/                neon.py (all SQL), models.py (Pydantic & wire contracts)
  agent/             state.py, graph.py (LangGraph DAG), llm.py, tools.py, sse.py, run.py
  rag/               ingest.py (LlamaIndex PDF/Markdown parser), embeddings.py, hybrid_search.py
  mcp/               server.py (official mcp Python SDK Streamable HTTP server at /mcp)
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
3. For all other queries, reserve one chat quota token against the rolling 24-hour limit. A router refusal is refunded (up to 10 per user per hour).
4. Run the LangGraph DAG pipeline:
    - **router**: Calls the first available model whose name contains `lite` (see `ModelRouter.candidates(prefer_lite=True)`) with structured output (`RouteDecision`) to classify into `smalltalk`, `benchmark`, or `refuse`.
    - On `refuse`: Returns fixed `REFUSAL`.
    - On `smalltalk`: Routed to **chat** node. Binds `google_search` tool for live facts (e.g. weather). Extracts search queries and web sources from grounding metadata.
    - On `benchmark`: Routed to **preload** → **agent** ⟷ **tools**.
        - `preload`: Executes initial hybrid RAG search (vector + tsvector with RRF, limit 5), sanitizes chunks, labels them `[S1]..[Sn]`, computes deterministic grounding (`grounded | weak | none`), and logs to `tool_audit_logs`.
        - `agent`: Streams synthesis with delimited untrusted reference context. If the model determines more evidence is needed, it issues tool calls (`hybrid_rag_search` or `web_search`) up to a maximum of 2 tool rounds and 2 calls per round.
        - `tools`: Validates arguments via Pydantic, executes read-only tools (`hybrid_rag_search` or `web_search`), wraps outputs in `<untrusted_tool_output>` tags, logs execution to `tool_audit_logs`, and returns execution results back to `agent`.
        - Once synthesis completes, verifies inline citations against known source labels: populates `invalidCitations` and marks `uncited: true` if no valid labels were cited.
5. SSE events: `start`, `node_start`, `plan`, `usage` (token counts per step), `tool_call` (`hybrid_rag_search`, `web_search`, or `google_search`), `tool_result` (with duration and citations), `grounding`, `token` (streamed text), and `done` (with summary metadata, `invalidCitations`, `uncited`, and `webSources`).
6. Turn persistence: Google-authenticated users have their turns saved to `messages` for persistent chat history.

### 4.2 Document ingestion (`POST /api/documents/upload`)

1. Admin-only: Enforces `is_admin = TRUE`. Non-admins receive HTTP 403.
2. File validation: PDF (`.pdf`) or Markdown (`.md`), strictly valid, up to 5 MB (`routes/documents.py:37`).
3. Parsing: LlamaIndex `MarkdownNodeParser` for Markdown; PyPDF / LlamaIndex `SentenceSplitter` (chunk size 512, overlap 64) for PDF.
4. Storage: Embeds chunks in batches of 100 with `gemini-embedding-001`, and inserts documents + document_chunks in Neon PostgreSQL within a single transaction.

### 4.3 Hybrid search (`POST /api/rag/search`)

Dense vector search (`pgvector` cosine similarity) and sparse keyword search (`tsvector`, ranked with `ts_rank_cd`) run concurrently against `document_chunks`. Scores are combined via Reciprocal Rank Fusion (RRF, $k=60$). If vector search fails, degrades gracefully to lexical-only search.

### 4.4 Public MCP server (`/mcp`)

Official `mcp` Python SDK (`MCPServer`) Streamable HTTP server mounted at `/mcp` (e.g. `https://nexusagent.onrender.com/mcp` in production, or `http://localhost:8000/mcp` locally):

- Stateless HTTP mode with JSON response formatting.
- Rate-limited to 60 requests/minute per client IP via `SlidingWindowCounter`. All MCP clients together are limited to 120 requests per minute.
- Two tools following ChatGPT / Claude standard connector specifications:
    - `search(query: str) -> dict`: Searches the benchmark knowledge base and returns up to 8 matching passages with `id`, `title`, and `url`.
    - `fetch(id: str) -> dict`: Retrieves the full text and metadata of a specific passage by `document_id:chunk_id`.
- DNS rebinding protection is on. `Host` must be the public site, `api.` plus that host, or localhost (and `testserver` in development and test). An absent `Origin` is allowed, so server-side connectors still work. A present `Origin` must be a configured CORS origin or a localhost port.

---

## 5. Quotas and Limits

- **Rolling 24-hour quotas**:
    - Tracked in `chat_usage` table. Quota remaining = limit minus count of rows in the last 24 hours.
    - Guests: 5 chats / 24h, enforced against guest UUID, device hash, machine hash, and client IP.
    - Google accounts: 25 chats / 24h, keyed by user ID.
- **Single-worker deployment**: In-memory rate limiters (`SlidingWindowCounter`) and MCP session lifecycle require running one API worker (`uvicorn app.main:app --workers 1`).
- **Request size caps**: 5 MB + 16 KB on `/api/documents/upload` (`config.py:64`), 64 KB elsewhere (`MAX_UPLOAD_REQUEST_BYTES`, `MAX_JSON_REQUEST_BYTES`).
- **Guest signups**: 5 new guest accounts per IP per hour. The count is recent guest rows in `users`, so a process restart does not clear it. An in-memory limiter is checked as well.

---

## 6. Security

### OWASP Top 10:2025

| ID  | Risk                                   | Control in this project                                                                                                                                                                                                                                      |
| :-- | :------------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| A01 | Broken Access Control                  | Admin routes require `is_admin`. Guest identity is the HttpOnly device cookie. Mutating `/api/` requests that carry the session cookie must send an allowed `Origin`.                                                                                        |
| A02 | Security Misconfiguration              | `TRUSTED_PROXY_HOPS` is 0–2, and production requires at least 1. A forwarded value is used only when it parses as an IP. Local development and production share one Neon database. MCP DNS rebinding protection allows the public hosts and localhost.       |
| A03 | Software Supply Chain Failures         | Dependencies and GitHub Actions are pinned, and vulnerability audits run in CI.                                                                                                                                                                              |
| A04 | Cryptographic Failures                 | Session and device cookies are HttpOnly, Secure outside development, and SameSite=Lax. The database stores the SHA-256 of the device id. Production requires a JWT secret of at least 32 characters.                                                         |
| A05 | Injection                              | SQL uses bound parameters. Retrieved text has delimiter breakouts escaped before it is wrapped as untrusted context.                                                                                                                                         |
| A06 | Insecure Design                        | A guest account is keyed by the server-issued device cookie. A `deviceId` in the JSON body cannot open an account. Signup limits count recent `users` rows. The injection pattern list does not grant or deny access.                                        |
| A07 | Authentication Failures                | Google ID tokens are verified. Sessions carry issuer, audience, and a token version that logout bumps.                                                                                                                                                       |
| A08 | Software or Data Integrity Failures    | Schema changes are applied by hand from `db/schema.sql`. Clients do not write model cooldown rows.                                                                                                                                                           |
| A09 | Security Logging and Alerting Failures | `nexusagent.security` logs presented-credential failures, CSRF rejects, quota 429s, and injection flags. A repeated burst from one IP is logged once at ERROR as `security_event=alert`. A missing credential on `/api/auth/me` is not logged.               |
| A10 | Mishandling of Exceptional Conditions  | A first-token deadline skips that model for 30 seconds in memory and does not tell the user the quota is exhausted. A real socket timeout still records a shared cooldown. Shutdown still flushes and disconnects if the cooldown sync task already crashed. |

### 6.1 OWASP Top 10 for LLM Applications 2025

| ID    | Risk                             | Control in this project                                                                                                                                                                                                                                                                                      |
| :---- | :------------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LLM01 | Prompt Injection                 | Known injection patterns in a user query are refused before the model. Matching passages are not indexed, not returned by MCP, and not placed in the prompt. Other retrieved text stays inside delimiters. A rephrased attack is contained by those delimiters, not by the pattern list.                     |
| LLM02 | Sensitive Information Disclosure | Ingest, retrieval, and tool output scrub private keys, AWS keys, JWTs, `sk-` and GitHub tokens, database URIs, and Google API keys (`AIza`). Model output is scrubbed before it is streamed and before it is stored. API errors are masked.                                                                  |
| LLM03 | Supply Chain                     | Dependencies and GitHub Actions are pinned with frozen lockfiles, vulnerability audits run in CI, and unneeded dependencies are pruned.                                                                                                                                                                      |
| LLM04 | Data and Model Poisoning         | Only an admin can upload, and uploads are PDF or Markdown under 5 MB and 400 chunks. Passages that match the injection patterns are stored only as a withheld placeholder and are not embedded. Retrieval and MCP fetch also withhold matches already in the database.                                       |
| LLM05 | Improper Output Handling         | Model outputs are rendered without raw HTML or image embedding, links are restricted to http(s), and nonces protect the Content Security Policy.                                                                                                                                                             |
| LLM06 | Excessive Agency                 | All model tools (`hybrid_rag_search`, `web_search`) and MCP tools (`search`, `fetch`) are strictly read-only, bound to a validated registry, and capped at 2 rounds of 2 calls.                                                                                                                              |
| LLM07 | System Prompt Leakage            | System prompts contain no secrets or internal credentials, and all authorization is enforced strictly in application code.                                                                                                                                                                                   |
| LLM08 | Vector and Embedding Weaknesses  | The benchmark corpus is public by design, ingestion is admin-only, and vector searches strictly use a single consistent embedding model.                                                                                                                                                                     |
| LLM09 | Misinformation                   | `[S1]` labels are checked against the labels the model was given. A cited sentence that does not share wording with its passage downgrades the grounding badge. An answer that cites none of the retrieved passages is not marked grounded.                                                                  |
| LLM10 | Unbounded Consumption            | Chat quota fails closed at 5 or 25 per rolling 24 hours. Bodies, output tokens, and tool calls are capped. MCP hybrid search may spend at most `MCP_EMBEDDINGS_PER_DAY` embedding calls per rolling day; further MCP searches use lexical retrieval only. Chat and `/api/rag/search` stay on the chat quota. |

### 6.2 OWASP Top 10 for Agentic Applications

| ID    | Risk                                 | Control in this project                                                                                                                                                                                     |
| :---- | :----------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| ASI01 | Agent Goal Hijack                    | The router pre-determines intent before reference passages are read, prompt-data boundaries are strictly enforced, and tool execution is bounded to a maximum of 2 rounds.                                  |
| ASI02 | Tool Misuse and Exploitation         | All tools are read-only, arguments are strictly validated against Pydantic schemas, and every invocation writes an immutable record to `tool_audit_logs`.                                                   |
| ASI03 | Identity and Privilege Abuse         | The agent possesses no privileged runtime credentials, admin status is enforced in the database, and user sessions are cryptographically signed.                                                            |
| ASI04 | Agentic Supply Chain Vulnerabilities | NexusAgent operates solely as an MCP server with internal tool registries and loads no remote or third-party MCP tools.                                                                                     |
| ASI05 | Unexpected Code Execution            | The application executes no user- or model-supplied code via `exec`, `eval`, or subprocesses.                                                                                                               |
| ASI06 | Memory and Context Poisoning         | The knowledge base is admin-managed, guest chats maintain no cross-session state, and persistent chat history is accessible only by the owning authenticated user.                                          |
| ASI07 | Insecure Inter-Agent Communication   | The public MCP server is strictly read-only, provides stateless HTTP responses, and is rate-limited per IP with total capacity ceilings.                                                                    |
| ASI08 | Cascading Failures                   | Automatic failover rotates across free-tier Gemini and Gemma models on rate limits, keyword search acts as a fallback when embeddings fail, and tool errors degrade gracefully without aborting the answer. |
| ASI09 | Human-Agent Trust Exploitation       | Inline source citations, live grounding status badges, token counts, and web search source attribution are displayed transparently in the user interface.                                                   |
| ASI10 | Rogue Agents                         | The LangGraph workflow has no self-modification or spawning capability, runs in a bounded deterministic loop, and audits every tool call to an append-only ledger.                                          |

# NexusAgent

> **NexusAgent: an open-source LLM benchmark assistant**

NexusAgent is an open-source LLM benchmark assistant that helps developers and technical leaders evaluate frontier AI models. It answers queries against pre-indexed benchmark datasets (Artificial Analysis, BenchLM, CursorBench, and OpenRouter metrics), handles quick chats with live Google Search grounding, and provides transparent token and tool telemetry.

---

## ⚡ Technologies & Implementation

NexusAgent brings together modern agentic and information retrieval libraries in a clean, production-grade architecture:

- **LangGraph** (`apps/backend/app/agent/graph.py`): Orchestrates a stateful DAG pipeline (`router` → `chat` with Google Search | `retriever` → `grounding` → `answer`).
- **LangChain** (`apps/backend/app/agent/graph.py`): Uses `langchain-google-genai` for chat streaming and Pydantic structured output (`RouteDecision`).
- **LlamaIndex** (`apps/backend/app/rag/ingest.py`): Ingests benchmark documents with hierarchical Markdown parsing (`MarkdownElementNodeParser`) and sentence-aware chunking (`SentenceSplitter`) for PDF and Markdown files.
- **Model Context Protocol (MCP)** (`apps/backend/app/mcp/server.py`): Official FastMCP implementation exposing a public, read-only Streamable HTTP server at `/mcp` with standard `search` and `fetch` tools for external assistants (Claude, ChatGPT, Cursor, Claude Code).
- **Gemini API & Model Routing** (`apps/backend/app/agent/graph.py`): Intelligent model failover across free-tier Gemini models with rate-limit tracking and automatic degradation.
- **Google Search Grounding** (`apps/backend/app/agent/graph.py`): Dynamic search tool binding for live small talk (e.g., weather and quick facts) returning deduplicated web source citations.
- **Hybrid RAG Search** (`apps/backend/app/rag/hybrid_search.py`): Dense vector search (`pgvector` with cosine distance) combined with sparse keyword search (`tsvector` BM25), fused via Reciprocal Rank Fusion (RRF).
- **Neon PostgreSQL 18**: Serverless PostgreSQL powering vectorized embeddings, user profiles, conversation history, and rolling 24-hour chat usage ledgers.

---

## 🔒 Quotas, Security & Admin Access

### Rolling 24-Hour Quotas

- **Guest Users**: 5 chats per rolling 24-hour window, enforced atomically across guest UUID, local device hash, machine hash, and client IP address.
- **Google Users**: 25 chats per rolling 24-hour window, keyed by user account, with persistent cross-device conversation history.
- **Unmetered Refusals**: Queries over 60 words, containing code, or outside scope (news, tutorials, code generation) are refused instantly without consuming user quota.

### Administrator Privileges

- Document uploads (PDF and Markdown) are strictly restricted to administrators (`is_admin = TRUE`).
- To promote an account to admin, authenticate once with Google, then run the SQL statement directly in the Neon SQL Editor:
    ```sql
    UPDATE users SET is_admin = TRUE WHERE email = 'your-email@example.com';
    ```

### Shared Database Architecture

Local development and production share a single Neon database (`apps/backend/.env.local`). This ensures local testing mirrors production quotas and user chat histories. Schema migrations are consolidated into a single idempotent file (`db/schema.sql`) applied manually in the Neon SQL Editor.

---

## 🌐 Connecting External MCP Clients

NexusAgent exposes a public, read-only Streamable HTTP MCP server at `/mcp` (`https://nexusagent-oss.onrender.com/mcp` in production, or `http://localhost:8000/mcp` for local use):

- **Claude (claude.ai / Desktop)**: `Settings` → `Connectors` → `Add custom connector` → paste `https://nexusagent-oss.onrender.com/mcp`.
- **ChatGPT**: `Settings` → `Apps & Connectors` → `Advanced` → `Developer mode` → `Create connector` → paste `https://nexusagent-oss.onrender.com/mcp` (Authentication: None).
- **Cursor / Claude Code**: Add the HTTP transport entry to `mcpServers` (or use `http://localhost:8000/mcp` locally):
    ```json
    {
        "mcpServers": {
            "nexusagent": {
                "type": "http",
                "url": "https://nexusagent-oss.onrender.com/mcp"
            }
        }
    }
    ```

---

## 🧱 Monorepo Architecture

```
nexusagent/
├── apps/
│   ├── frontend/         # Next.js 16 + React 19 + TypeScript + shadcn/ui + Tailwind v4 + Zustand
│   └── backend/          # FastAPI + Python 3.14 + LangGraph + LlamaIndex + FastMCP + Neon Postgres 18
├── packages/
│   └── contracts/        # Shared TypeScript interfaces & OpenAPI wire schemas
├── db/
│   └── schema.sql        # Single source of truth database schema (applied by hand)
├── .agents/
│   ├── rules/            # Agent identity, working guide, coding standard
│   └── specs/
│       ├── architecture.md   # System architecture, request flows, limits, and security
│       ├── design.md         # UI layout, tokens, accessibility
│       ├── AGENTs.md         # AI Agent context, system master, coding invariants
│       └── features.md       # Task board and feature status
└── knowledge_base/
    └── benchmarks/       # Pre-seeded benchmark corpus (BenchLM, CursorBench, OpenRouter, AA)
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js**: `v24.x LTS`
- **pnpm**: `>=10` (`pnpm@12.9.1` pinned)
- **Python**: `3.14.x` with `uv` package manager

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/Avinaba-Mazumdar/nexusagent.git
cd nexusagent

# Install frontend dependencies
pnpm install

# Install backend dependencies
cd apps/backend && uv sync && cd ../..
```

### 2. Configure Environment

Copy example environment files:

```bash
cp apps/backend/.env.example apps/backend/.env.local
cp apps/frontend/.env.example apps/frontend/.env.local
```

Backend configuration (`apps/backend/.env.local`):

- `ENVIRONMENT`: default is `production`. Set `ENVIRONMENT=development` for local work.
- `JWT_SECRET_KEY`: required outside development/test (≥ 32 characters).
- `GOOGLE_CLIENT_ID`: required for Google OAuth.
- `NEON_DATABASE_URL`: database connection string. Paste your production Neon URL here (shared with local dev).
- `GEMINI_API_KEY`: required. Generates answers and vector embeddings (`gemini-embedding-001`).
- `PUBLIC_SITE_HOST`: public hostname (default: `nexusagent.avinaba.com`).

Frontend configuration (`apps/frontend/.env.local`):

- `NEXT_PUBLIC_API_URL`: API URL (`http://localhost:8000` in dev).
- `NEXT_PUBLIC_SITE_HOST`: public hostname shown in legal pages and headers.
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`: Google OAuth client ID matching backend.

### 3. Run Development Servers

```bash
pnpm dev:fe   # frontend (http://localhost:3000)
pnpm dev:be   # backend (http://localhost:8000)
```

Interactive API docs are available at `http://localhost:8000/docs` in development.

---

## 🧪 Testing & Verification

- **Backend checks**:
    ```bash
    cd apps/backend
    uv run ruff check .
    uv run ruff format --check .
    uv run pytest -q
    ```
    _To run database-backed tests against local PostgreSQL:_
    ```bash
    docker run -d --name nexus-pg -p 5432:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=nexus_test pgvector/pgvector:pg18
    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/nexus_test uv run pytest -q
    ```
- **Frontend checks**:
    ```bash
    pnpm --filter @nexusagent/frontend typecheck
    pnpm lint
    pnpm format:check
    pnpm --filter @nexusagent/frontend test
    pnpm --filter @nexusagent/frontend build
    ```
- **Contracts generation**:
    ```bash
    pnpm contracts:generate
    ```

---

## 📄 License

MIT License (see [LICENSE](LICENSE)). Copyright (c) 2026 Avinaba Mazumdar.

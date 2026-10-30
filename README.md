# NexusAgent

> **Autonomous Technical Research & Systems Design Intelligence Engine**

NexusAgent is an enterprise-grade autonomous systems analyst that evaluates distributed systems RFCs, cross-references infrastructure whitepapers, reports whether its answer is grounded in retrieved sources, and synthesizes structured verdicts with dynamic Mermaid architecture diagrams.

---

## ⚡ Key Capabilities

- **Agent pipeline**: planner → retriever → grounding check → synthesizer on **LangGraph**, streaming the model's answer token by token with `[S1]`-style source citations.
- **Three-panel UI** built with **Next.js 16**, **React 19**, **shadcn/ui** primitives and **Tailwind CSS v4**: workspace sidebar, chat canvas, observability panel.
- **Hybrid RAG Pipeline**: Combines dense vector search with sparse keyword search (**Neon PostgreSQL 18 `pgvector`** + **`tsvector` BM25**) fused via Reciprocal Rank Fusion (RRF), with a built-in header-aware markdown parser.
- **Model Context Protocol server**: HTTP gateway, SSE transport and stdio (`python -m app.mcp.server`) exposing the `hybrid_rag_search` tool to external agents such as Claude Desktop and Cursor. There is no MCP client.
- **Security posture** (see [architecture.md](.agents/specs/architecture.md) §7): untrusted-content delimiters, canary token, read-only tools, no code execution, per-user quotas, revocable sessions, nonce-based CSP, and an append-only tool audit log (30-day retention).
- **Free guest access**: one-click guest pass with a per-user hourly quota on Neon PostgreSQL 18.

---

## 🧱 Monorepo Architecture

```
nexusagent/
├── apps/
│   ├── frontend/         # Next.js 16 + React 19 + TypeScript 7 + shadcn/ui + Tailwind v4 + Zustand + Mermaid.js
│   └── backend/          # FastAPI 0.141 + Python 3.14 + LangGraph 1.2 + Neon Postgres 18 + MCP server
├── packages/
│   └── contracts/        # Shared TypeScript interfaces & wire schemas
├── .agents/
│   ├── context/          # Shared agent context and decision log
│   ├── rules/            # Agent identity, working guide, coding standard
│   ├── skills/           # Agent skills
│   ├── specs/
│   │   ├── architecture.md   # How the system works today: flows, limits, security
│   │   ├── design.md         # UI layout, tokens, accessibility
│   │   ├── AGENTs.md         # AI Agent context, system master, coding invariants
│   │   ├── features.md       # Phase board (what is done, partial, removed)
│   │   ├── aim.md            # Project aim
│   │   └── versions.md       # Versions
│   └── logs.md           # Agent work log
└── knowledge_base/
    └── benchmarks/       # Pre-seeded corpus (BenchLM, CursorBench, OpenRouter metrics, AA)
```

---

## 🚀 Quick Start

### Prerequisites

- **Node.js**: `v24.x LTS`
- **pnpm**: `^10.x`
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
- `GOOGLE_CLIENT_ID`: required for Google OAuth. Production refuses to start without `JWT_SECRET_KEY` (≥ 32 chars) and `GOOGLE_CLIENT_ID`.
- `NEON_DATABASE_URL`: the startup migration creates the schema automatically.
- `GEMINI_API_KEY`: required. The agent synthesizes answers with Gemini and embeds queries and uploaded documents with `gemini-embedding-001`. Without it, chat answers and document uploads return an error.
- `GEMINI_MODELS`: chat model IDs in preference order. The default lists every Gemini free-tier text model (`gemini-3.8-flash` first). When a model returns 429 the next one answers, and the exhausted model is skipped until its quota resets (the advised retry delay for per-minute limits, midnight Pacific for daily limits).
- `EMBEDDING_MODEL`: the single embedding model (default `gemini-embedding-001`). Changing it requires re-running `scripts/seed_kb.py` and re-uploading your documents.

Frontend configuration (`apps/frontend/.env.local`):

- `NEXT_PUBLIC_API_URL`: API URL (`http://localhost:8000` in dev). **Required** for production builds; it is compiled into the client bundle.
- `NEXT_PUBLIC_SITE_HOST`: public hostname shown in the footer and legal pages.
- `NEXT_PUBLIC_GOOGLE_CLIENT_ID`: Google OAuth client ID matching backend.
- `NEXT_PUBLIC_CONTACT_EMAIL`: Maintainer contact address for legal pages and privacy inquiries.
- `NEXT_PUBLIC_CAL_URL`: Calendar booking URL for consultation requests.

### 3. Run Development Servers

```bash
pnpm dev:fe   # frontend
pnpm dev:be   # backend (needs ENVIRONMENT=development in apps/backend/.env.local)
```

- **Frontend**: `http://localhost:3000`
- **Backend API & MCP server**: `http://localhost:8000`
- **Interactive API docs** (development only): `http://localhost:8000/docs`

Then embed the knowledge base once: `uv run --project apps/backend python scripts/seed_kb.py`.

---

## 📚 Master Documentation Index

- 📐 **[System Architecture](.agents/specs/architecture.md)**: How the system works today: request flows, limits, and OWASP security controls (the schema lives in `migrations/`).
- 🎨 **[UI/UX Design System](.agents/specs/design.md)**: 4-zone command center specifications, theme tokens, and component guidelines.
- 🤖 **[AI Agent Context & Rules](.agents/specs/AGENTs.md)**: Architectural invariants, definition of done, and verification gates.
- 📋 **[Active Task Board](.agents/specs/features.md)**: Phased implementation roadmap and progress tracking.

---

## 🚢 Deployment

Run the API as a single process (`uvicorn app.main:app --workers 1`). MCP SSE sessions and guest abuse counters are kept in process memory. In production the API refuses to start if the database is unreachable, and hides `/docs`.

The API rejects request bodies over 1 MB + 16 KB on `/api/documents/upload` and over 64 KB elsewhere (`MAX_UPLOAD_REQUEST_BYTES`, `MAX_JSON_REQUEST_BYTES`) before parsing or authentication. Also cap bodies at the reverse proxy (for example Cloudflare, or nginx `client_max_body_size 2m`).

---

## 🛠️ Maintenance

Run `uv run python scripts/prune_guests.py` daily (cron, Render Cron Job, or a scheduled CI job). It deletes guests inactive for 24 h (`--ttl`) and audit rows older than 30 days (`--audit-days`).

### Database Permissions

`tool_audit_logs` is append-only: a database trigger rejects `UPDATE` and `DELETE` except the retention job's deletes. For defence in depth you can also revoke those privileges from the application role and grant them to the role that runs `prune_guests.py`.

---

## 🧪 Testing

- **Backend tests**: `cd apps/backend && uv run pytest -q`
    - `@pytest.mark.db` tests run only when `TEST_DATABASE_URL` points to a disposable database. They create and delete data. Never point test runs at a production database.
- **Frontend tests**: `cd apps/frontend && pnpm test`
- **Lint & format** (Vite+: oxlint and oxfmt, configured in `vite.config.ts`): `pnpm lint`, `pnpm format:check`
- **Backend lint & format**: `cd apps/backend && uv run ruff check . && uv run ruff format --check .`

---

## 📄 License

MIT License (see [LICENSE](LICENSE)). Copyright (c) 2026 Avinaba Mazumdar. Designed and engineered for high-impact technical analysis.

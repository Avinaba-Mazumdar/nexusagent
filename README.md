# NexusAgent

> **Autonomous Technical Research & Systems Design Intelligence Engine**

NexusAgent is an enterprise-grade autonomous systems analyst that evaluates distributed systems RFCs, cross-references infrastructure whitepapers, self-reflects on consensus trade-offs, and synthesizes structured verdicts with dynamic Mermaid architecture diagrams.

---

## ⚡ Key Capabilities

- **Autonomous Agent DAG**: Multi-step Plan-and-Execute workflow with a self-reflection critic loop powered by **LangGraph 1.2**.
- **Modern 4-Zone UI**: High-contrast command center built with **Next.js 16**, **React 19**, **shadcn/ui**, and **Tailwind CSS v4** (Header, Left Workspace Panel, Center Canvas Active Chat, Right Live Observability Inspector).
- **Hybrid RAG Pipeline**: Combines dense vector search with sparse keyword search (**Neon PostgreSQL 18 `pgvector`** + **`tsvector` BM25**) fused via Reciprocal Rank Fusion (RRF), powered by **LlamaIndex** hierarchical parsing.
- **Model Context Protocol (MCP v2)**: Compliant MCP v2 server (`/api/mcp/sse` + `/api/mcp/messages` + CLI stdio) and client for seamless interoperability with Claude Desktop, Cursor, and Antigravity.
- **OWASP Top 10 for Agentic AI**: Hardened perimeter with prompt injection delimiters, no untrusted code execution, canary token tracking, Human-in-the-Loop (HITL) gates, and immutable audit logs.
- **Free-Tier Guest Access**: 1-Click Guest Pass with token-bucket rate limiting on a unified Neon PostgreSQL 18 data tier.

---

## 🧱 Monorepo Architecture

```
nexusagent-oss/
├── apps/
│   ├── frontend/         # Next.js 16 + React 19 + TypeScript 7 + shadcn/ui + Tailwind v4 + Zustand + Mermaid.js
│   └── backend/          # FastAPI 0.141 + Python 3.14 + LangGraph 1.2 + LlamaIndex + Neon Postgres 18 + MCP v2
├── packages/
│   └── contracts/        # Shared TypeScript interfaces & wire schemas
├── target/
│   ├── ARCHITECTURE.md   # System topology, Neon Postgres 18 DDL, pgvector HNSW, OWASP specs
│   ├── DESIGN.md         # 4-zone UI layout, cyber obsidian tokens, component guide
│   ├── AGENTs.md         # AI Agent context, system master, coding invariants
│   └── TODOs.md          # Active MVP0 phased task board
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
git clone https://github.com/your-org/nexusagent-oss.git
cd nexusagent-oss

# Install frontend dependencies
pnpm install

# Install backend dependencies
cd apps/backend && uv sync && cd ../..
```

### 2. Configure Environment

The API reads `apps/backend/.env.local`. Set:

- `ENVIRONMENT`: default is `production`. Set `ENVIRONMENT=development` for local work.
- `JWT_SECRET_KEY`: required outside development/test (≥ 32 characters).
- `GOOGLE_CLIENT_ID`: required for Google OAuth. Production refuses to start without `JWT_SECRET_KEY` (≥ 32 chars) and `GOOGLE_CLIENT_ID`.
- `NEON_DATABASE_URL`: the startup migration creates the schema automatically.
- `GEMINI_API_KEY`: required. The agent synthesizes answers with Gemini and embeds queries and uploaded documents with `gemini-embedding-001`. Without it, chat answers and document uploads return an error.
- `NEXT_PUBLIC_API_URL`: must be set at build time in production for the frontend (otherwise API calls are blocked by Content-Security-Policy).

`scripts/seed_kb.py` reads the same two variables from `apps/backend/.env` (or the process environment).

### 3. Run Development Servers

```bash
pnpm dev
```

- **Frontend Command Center**: `http://localhost:3000`
- **Backend API & MCP Server**: `http://localhost:8000`
- **Interactive API Docs**: `http://localhost:8000/docs`

---

## 📚 Master Documentation Index

- 📐 **[System Architecture](target/ARCHITECTURE.md)**: Deep technical spec, topology, database DDL, and OWASP security matrix.
- 🎨 **[UI/UX Design System](target/DESIGN.md)**: 4-zone command center specifications, theme tokens, and component guidelines.
- 🤖 **[AI Agent Context & Rules](target/AGENTs.md)**: Architectural invariants, definition of done, and verification gates.
- 📋 **[Active Task Board](target/TODOs.md)**: Phased implementation roadmap and progress tracking.

---

## 🛠️ Maintenance

Prune inactive guests daily with `uv run python scripts/prune_guests.py --ttl 24` (cron, Render Cron Job, or a scheduled CI job).

---

## 🧪 Testing

- **Backend tests**: `cd apps/backend && uv run pytest -q`
  - `@pytest.mark.db` tests run only when `TEST_DATABASE_URL` points to a disposable database. They create and delete data. Never point test runs at a production database.
- **Frontend tests**: `cd apps/frontend && pnpm test`

---

## 📄 License

MIT License. Designed and engineered for high-impact technical analysis.

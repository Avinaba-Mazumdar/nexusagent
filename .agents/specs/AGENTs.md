# NexusAgent — AI Agent Context & System Master

This document is the primary context entrypoint for the **NexusAgent** codebase. It outlines the core architectural rules, engineering philosophy, tech stack constraints, OWASP security requirements, and links directly to all technical specification documents.

You are a **Staff-Plus Systems Architect**, a founding engineer, and a **Cybersecurity Expert**. At every prompt or review, your job is to debate and scrutinize any proposed change or implementation with the user to ensure the highest possible technical rigor. Always assume proposals contain hidden architectural trade-offs or security loopholes that must be challenged properly.

- **Security First**: Always check against the OWASP Top 10 for LLM Applications and Agentic AI. Never allow unbounded tool execution, unsandboxed code execution, or prompt leakage.
- **Architectural Rigor**: Always verify distributed systems claims against source documents. Never tolerate hallucinated consensus invariants or latency figures.
- **User Experience**: Streaming answers over SSE with interactive citation pills. No latency figure is promised; latency is measured in the browser and shown in the observability panel.
- **Performance & Scalability**: Hybrid dense/sparse RAG (pgvector + tsvector ts_rank_cd) fused via Reciprocal Rank Fusion (RRF).
- **Maintainability**: Clear separation of concerns between `apps/frontend` (Next.js 16), `apps/backend` (FastAPI), and `packages/contracts`.

**Do not mark work done that does not exist on disk.** Tasks in `.agents/specs/features.md` stay unchecked until files exist, builds succeed, and tests pass.

---

## 0. Current Status (as of September 2026)

- **These `.agents/specs/` documents are the single source of truth** for what to build and maintain.
- **Target Audience**: Developers and technical leaders comparing frontier LLMs.
- **Showcase Objective**: 1-click zero-friction demo readiness with pre-seeded benchmark documents (Artificial Analysis, BenchLM, CursorBench, OpenRouter), live SSE streaming, token and tool telemetry, and a public MCP server with connection instructions.
- **Honesty Rule**: Do not describe an agent as "100% immune to prompt injection", "zero-hallucination", or "infinitely scalable". The real controls are untrusted-content delimiters, secret scrubbing, read-only tools, and a grounding check that reports whether retrieval found sources. Name them as what they are; do not present heuristics as reflection or reasoning.
- **No Simulated Telemetry Rule**: Without `GEMINI_API_KEY` the server answers with an explicit error (there is no offline simulator). Nodes must never fabricate model names, token counts, latency figures, or streamed prose that no model produced. `token` events are the model's real chunks; the only non-model text sent as a token is the fixed out-of-scope refusal. Latency figures in the UI are measured in the browser.

---

## 1. Project Overview & Mission

**NexusAgent** is an open-source LLM benchmark assistant that evaluates frontier AI models against benchmark data (Artificial Analysis, BenchLM, CursorBench, and OpenRouter metrics).

- **Questions are classified by a router**: smalltalk and live queries (e.g. weather) use Gemini with Google Search grounding; benchmark questions use a bounded agent loop (`preload` initial RAG retrieval → `agent` model ⟷ `tools` node executing `hybrid_rag_search` and `web_search`) with citation validation.
- **Interoperability**: A public, read-only Model Context Protocol (MCP) server at `/mcp` (Streamable HTTP, stdio) with tools `search` and `fetch`.

---

## 2. Master Documentation Index & Conflict Rules

Always refer to the following documents in `.agents/specs/` for authoritative specifications:

- 📐 **[System Architecture (architecture.md)](./architecture.md)**: How the system works today: Next.js 16 + FastAPI request flows, hybrid retrieval (pgvector HNSW + tsvector), quotas, and OWASP security tables. The schema itself lives in `db/schema.sql`.
- 🎨 **[UI/UX Design System (design.md)](./design.md)**: Enterprise theme tokens in `globals.css`, three themes (Light, Dark, Black), elevated cards, shadcn/ui primitives, Tailwind CSS v4 `@theme` tokens, 4-zone command center.
- 📋 **[Active MVP Task Board (features.md)](./features.md)**: Phased task board covering all implementation milestones with automated tests and verification gates.

**Conflict Resolution Rules:**

1. **architecture.md wins on security, backend protocols, database schemas, and OWASP rules.**
2. **design.md wins on UI layout, component hierarchy, colors, typography, and styling tokens.**
3. **features.md wins on exact file paths and task status.**
   _If two documents disagree, update the documents in the same commit—never implement an unresolved contradiction._

---

## 3. Core Architectural & Coding Invariants (Do Not Break)

When writing code or proposing changes for NexusAgent, you MUST strictly follow these invariants:

1. **Monorepo Directory Invariants**:
    - `apps/frontend`: Next.js 16 App Router (`^16.0.0`) + React 19 + TypeScript + shadcn/ui + Tailwind CSS v4 + Zustand + Lucide React. Three themes: Light, Dark, Black. _Never reintroduce Nuxt or ad-hoc CSS frameworks._
    - `apps/backend`: FastAPI (`>=0.115`) + Python 3.14 + LangGraph (`>=1.2.12`) + LangChain Google GenAI (`TEXT_MODELS`: every free-tier Gemini text model, then hosted Gemma 4, routed by `app/agent/model_router.py` when one hits its quota) + the official `mcp` Python SDK (`MCPServer`) + Neon PostgreSQL 18 (`asyncpg`) + `pgvector`. Versions are authoritative in `pyproject.toml` / `package.json`.
    - `packages/contracts`: Shared TypeScript schemas and JSON-RPC 2.0 wire definitions.
2. **Neon PostgreSQL 18 Data Tier & Python Backend Auth Guarantee**:
    - Single Unified Data Tier: Neon Serverless PostgreSQL 18 with `pgvector` (HNSW indexing), full-text `tsvector` (`ts_rank_cd`) search, connection pooling, and FastAPI-managed authentication (Guest JWTs + Google sign-in) is used across local development and production. Locally, no separate database is maintained.
3. **Agentic Orchestration & LangGraph DAG**:
    - The agent execution loop runs on a LangGraph `StateGraph`: `router`, then `chat` or `agent`; `agent` and `tools` form a loop capped at `MAX_TOOL_ROUNDS`.
    - The `grounding` check reports `grounded | weak | none` from the retrieved chunks. It is not an LLM reflection step and must not be described as one.
    - Citations are labelled `S1..Sn` in the prompt; answers cite `[S1]`; the citation list contains exactly the chunks the model saw.
4. **Model Context Protocol (MCP) Compliance**:
    - One Streamable HTTP endpoint at `/mcp` plus stdio (`python -m app.mcp.server`). Tools: `search`, `fetch`. Public, read-only, rate-limited to 60 requests per minute per IP, every call audited.
    - Tool arguments are validated by Pydantic models, and the advertised JSON schema is generated from the same model.
5. **OWASP Security Requirements**:
    - See the OWASP tables in `architecture.md` section 6.
    - A rolling 24-hour quota in `chat_usage` meters agent runs and `/api/rag/search`. Guests are also counted per device, machine and IP. Uploads are admin-only and not metered. MCP is rate-limited per IP. Refusals are free (router refusals up to 10 per user per hour).

---

## 4. Anti-Shortcut Protocol & Strict Definition of Done (DoD)

To maintain production-grade quality, the AI Agent and developers MUST adhere to the following rules:

### Prohibited Anti-Patterns:

1. **No Phantom Implementations**: Never leave empty stubs, mock implementations in production paths, or `// TODO: implement later` comments.
2. **No Inline Styling Hacks**: Every frontend component must use shadcn/ui primitives and Tailwind CSS v4 `@theme` tokens. No arbitrary hardcoded pixel widths or arbitrary hex colors.
3. **No Untrusted Code Execution**: Never run user- or model-supplied code via `exec()`, `eval()` or a subprocess on the API host. AST validation is not isolation (see ASI05).
4. **No Direct External Tool Calling Without MCP**: Tools must be registered through the Model Context Protocol or internal LangGraph tool registry.
5. **No Premature Task Checking**: Never flip `[ ]` to `[x]` in `.agents/specs/features.md` until code exists, builds cleanly, and tests pass.

### Mandatory 4-Step Verification Gate Before Marking Tasks `[x]`:

1. **Verify Complete File Generation**: Ensure all required components, routes, schemas, and tests exist on disk.
2. **Verify All UI/UX States**: Loading skeletons, streaming token renderers, empty document vault states, and error toasts.
3. **Run Build & Validation**: `pnpm build` in `apps/frontend` and `pytest` / `uv run ruff check` in `apps/backend`.
4. **Document Verification**: Provide concrete proof of execution in walkthrough notes.

---

## 5. Quick Domain Vocabulary

- **LangGraph**: State-machine framework used here for a bounded agent loop: `router -> refuse | chat | preload -> agent <-> tools`.
- **Hybrid RAG**: Retrieval fusing dense vector cosine similarity (`pgvector`) with sparse lexical search (`tsvector`, ranked with `ts_rank_cd`).
- **Reciprocal Rank Fusion (RRF)**: Rank-based mathematical fusion combining vector search and lexical search results.
- **MCP (Model Context Protocol)**: Anthropic/OpenAI open standard enabling agents to call tools and access resources via JSON-RPC 2.0.
- **HITL (Human-in-the-Loop)**: Interactive authorization gate requiring human confirmation before executing high-impact tools.

# NexusAgent: Full Codebase Audit Report

- **Date:** 2026-10-29
- **Commit audited:** `a4e303d` (branch `master`, clean tree)
- **Scope:** every tracked file: `apps/backend`, `apps/frontend`, `packages/contracts`, `migrations`, `scripts`, `knowledge_base`, `target/*.md`, root config, `.agents/rules`.
- **Lenses:** security (OWASP Top 10 for Agentic AI, web), logic and correctness, UI/UX and accessibility, YAGNI / KISS / DRY / SOLID, dead and redundant code.
- **No code was changed during this audit.**

---

## 0. How to use this report

This report has two readers:

1. **Verifier:** re-check each finding against the code. Mark each one `CONFIRMED`, `REJECTED` (with reason) or `MODIFIED` (with the corrected fix).
2. **Fixer:** apply confirmed findings **one ID per commit**, in the order given in §8.

Rules for the fixer:

- Every finding has **Where**, **Problem**, **Fix** and **Verify**. Do the steps in **Fix**, then run **Verify** and the standard gates below. Do not mark anything done until the gates pass.
- **Never edit an existing file in `migrations/`.** Applied migrations are immutable. Add a new file named `YYYYMMDDHHMMSS_description.sql` with a timestamp later than `20261101000200`.
- When a fix deletes code, also delete or update the tests that only covered that code.
- Add a regression test for every `SEC-*` and `LOG-*` fix.
- Line numbers refer to commit `a4e303d`. They shift after earlier fixes, so search for the quoted symbol rather than trusting the number.
- Older test names mention IDs such as `audit S-01` and `L-05`. Those come from a previous report that is no longer in the repo. The IDs in this report are new (`SEC-`, `LOG-`, `UX-`, `CLN-`, `DOC-`, `TST-`) and unrelated to them.

Standard gates (run after every commit):

```bash
cd apps/backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
cd apps/frontend && pnpm test && pnpm typecheck && pnpm lint
```

Severity legend:

| Severity   | Meaning                                                                |
| ---------- | ---------------------------------------------------------------------- |
| **High**   | Exploitable now, costs money, corrupts data, or breaks a core feature. |
| **Medium** | Real defect or risk with a narrower trigger or impact.                 |
| **Low**    | Hygiene, minor UX, or small risk.                                      |

---

## 1. Executive summary

The codebase is tidy in places that matter. SQL is parameterised, document and conversation tenancy checks are correct, React escapes model output, and Mermaid SVG is sanitised. The serious problems sit in four areas:

1. **Cost controls can be bypassed.** MCP tool calls skip the quota entirely (SEC-01). Quota buckets are keyed by `(user_id, IP)`, so changing IP resets a user's quota (SEC-02). One upload token can trigger about 75 paid embedding calls and block the event loop (SEC-03).
2. **Retrieval correctness.** The embedding service silently falls back across _different embedding models_ into the same vector index (LOG-04). Lexical search ANDs every query word, so it rarely matches (LOG-08). Citation line numbers are often wrong (LOG-07).
3. **The product overstates what it does.** The token stream is replayed after the full LLM call finishes, so the displayed "first token" metric is false (LOG-01). The "critic" is a constant formula shown to users as a grounding score with "re-planning" (LOG-06). The docs and task board mark features as done that do not exist (DOC-01, DOC-02). The privacy policy makes claims the code contradicts (SEC-12). The project's own `AGENTs.md` forbids this ("Honesty Rule", "No Simulated Telemetry Rule", "Do not mark work done that does not exist on disk").
4. **Readability and accessibility.** Answer text is 12px and much of the UI is 10–11px, against a design spec of 14px body text and a WCAG AAA claim (UX-01). Dark-mode primary buttons fail AA contrast at 3.68:1 (UX-02).

Top 10 to fix first: **SEC-01, SEC-02, SEC-03, LOG-04, LOG-01, LOG-02, LOG-03, SEC-04, LOG-09, UX-01.**

### Finding index

| ID            | Sev    | Title                                                                                           |
| ------------- | ------ | ----------------------------------------------------------------------------------------------- |
| SEC-01        | High   | MCP `tools/call` bypasses quota (denial of wallet)                                              |
| SEC-02        | High   | Quota bucket keyed by `(user_id, client_ip)`: IP rotation resets quota                          |
| SEC-03        | High   | Upload cost amplification and event-loop blocking                                               |
| SEC-04        | Medium | JWT in `localStorage` + CSP `'unsafe-inline'`; no revocation; endless refresh                   |
| SEC-05        | Medium | Upload validation: extension OR client MIME, latin-1 accepts binary, long filename → 500        |
| SEC-06        | Medium | MCP arguments are not schema-validated; unbounded input stored in audit log                     |
| SEC-07        | Medium | Prompt-injection detection on the user query does nothing                                       |
| SEC-08        | Medium | Google identity keyed on email, not `sub`; uses the `tokeninfo` endpoint                        |
| SEC-09        | Low    | Unbounded in-memory sliding-window counters (memory growth)                                     |
| SEC-10        | Low    | MCP results returned to external agents without untrusted-content wrapping                      |
| SEC-11        | Low    | Production exposes `/docs`, `/openapi.json`, and DB version/extensions on `/api/health`         |
| SEC-12        | Medium | Privacy policy and Terms contradict the code (retention, data use, "cryptographic isolation")   |
| SEC-13        | Low    | Audit log "immutable" only by convention; raw prompts retained forever                          |
| SEC-14        | Low    | CORS `allow_credentials=True` with no cookies; no throttling on auth/read endpoints             |
| LOG-01        | High   | Fake streaming: full LLM call, then replayed in 3-word chunks; TTFT metric is false             |
| LOG-02        | Medium | Conversation title is overwritten on every turn                                                 |
| LOG-03        | Medium | `done` is sent before persistence; client refresh races; disconnect cancels the save            |
| LOG-04        | High   | Embedding fallback mixes vector spaces of different models                                      |
| LOG-05        | Medium | Citations: no format instruction; 5 cited but 3 used; fake pills; filename-substring matching   |
| LOG-06        | Medium | "Critic" is a constant heuristic presented as reflection/re-planning                            |
| LOG-07        | Medium | Chunk line numbers are wrong (first-occurrence search, scrub shifts)                            |
| LOG-08        | Medium | Lexical search uses `plainto_tsquery` (AND); sequential; no degraded mode                       |
| LOG-09        | Medium | Quota consumed before validation; never refunded on cancel/disconnect                           |
| LOG-10        | Medium | stdio MCP server never connects to the DB; crashes on non-object JSON                           |
| LOG-11        | Low    | History window magic numbers; guests silently get no multi-turn context                         |
| LOG-12        | Low    | Scope classifier is easy to bypass and runs 3 times per request                                 |
| LOG-13        | Medium | No way to delete a document, but the 409 error says "Delete a document first"                   |
| LOG-14        | Medium | Starter prompts ask about models that are not in the knowledge base                             |
| LOG-15        | Low    | `seed_kb.py` rotates document UUIDs each run; hash differs from upload path                     |
| LOG-16        | Low    | Account switch within 8 s skips loading the new user's conversations                            |
| LOG-17        | Low    | Audit `duration_ms=0` hard-coded; `conversation_id` never recorded                              |
| LOG-18        | Low    | `save_message` and the user+assistant pair are not transactional                                |
| LOG-19        | Medium | DB outage turns every authenticated request into an unhandled 500                               |
| UX-01         | High   | Body text 12px, UI text 10–11px (spec: 14px body; AAA claimed)                                  |
| UX-02         | Medium | Contrast: dark primary button 3.68:1 (fails AA); several tokens below the claimed 7:1           |
| UX-03         | Low    | Skip link styled but never rendered                                                             |
| UX-04         | Medium | Quota exhaustion opens a "Hire Me" sales modal instead of saying when quota resets              |
| UX-05         | Medium | A citation cannot be opened; click only highlights a filename (and leaves the answer on mobile) |
| UX-06         | Medium | Hand-rolled Markdown parser (no italics, nested lists, etc.)                                    |
| UX-07         | Low    | Floating "New Chat" button overlaps the thread                                                  |
| UX-08         | Low    | Internal jargon in end-user UI ("Executing DAG [PLANNER]", "RPC 200 OK", "MCP v2")              |
| UX-09         | Low    | MCP Inspector tells users to supply a Bearer token they cannot obtain                           |
| UX-10         | Low    | Inconsistent fetch layers: uploads/docs bypass `apiClient` (no 401 handling)                    |
| UX-11         | Low    | Reloaded conversations lose citation pills                                                      |
| UX-12         | Low    | Composer auto-grow relies on `field-sizing` (no Firefox / older Safari)                         |
| CLN-01…CLN-12 | –      | Dead/redundant code and files to delete (§5)                                                    |
| DOC-01…DOC-05 | –      | Documentation and spec drift (§6)                                                               |
| TST-01…TST-05 | –      | Test-suite defects (§7)                                                                         |

---

## 2. Security findings

### SEC-01 · High · MCP `tools/call` bypasses quota (denial of wallet)

- **Where:** `apps/backend/app/routes/mcp.py:48-84` (`POST /api/mcp/v1`) and `:145-205` (`POST /api/mcp/messages`); `apps/backend/app/mcp/dispatch.py:41-51`; `apps/backend/app/mcp/registry.py:140-233`.
- **Problem:** Every other paid path (`/agent/stream`, `/rag/search`, `/documents/upload`) calls `default_rate_limiter.check_and_consume`. The MCP routes do not. `hybrid_rag_search` calls the Gemini embedding API once per call (`hybrid_search.py:178`).
- **Impact:** Any guest (free, one click) can loop `tools/call` and spend the Gemini budget without limit. This breaks ASI-07.
- **Fix:**
    1. Pass the authenticated `User` and the client IP into `dispatch_mcp_method` (replace the `user_id` parameter with `user: User | None, client_ip: str | None`).
    2. In the `tools/call` branch, before `call_tool`, call `await default_rate_limiter.check_and_consume(user.id, client_ip, is_guest=user.is_guest)` when `user` is set. Convert the 429 `HTTPException` into a JSON-RPC error (`code=-32000`, `message="Quota exhausted. It replenishes hourly."`) instead of letting it escape.
    3. The stdio server (`mcp/server.py`) is a local, trusted process. Keep it unmetered and document that.
- **Verify:** New test: a guest makes 6 `tools/call` requests to `/api/mcp/v1`. The 6th returns a JSON-RPC error and the embedding service mock is called at most 5 times.

### SEC-02 · High · Quota bucket keyed by `(user_id, client_ip)`: IP rotation resets quota

- **Where:** `migrations/20260901000000_core_schema.sql:28-36` (`CONSTRAINT unique_user_ip UNIQUE (user_id, client_ip)`); `apps/backend/app/db/neon.py:190-258`; `apps/backend/app/core/rate_limiter.py:63-149`.
- **Problem:** Each new IP gets a fresh full bucket for the same user. A Google user (25/h) has no IP limiter at all. Guests are bounded per IP (15/h), but rotating IPs (mobile network, VPN, proxy pool) bypasses both limits. Quota reads also do two round trips (`get_or_create_rate_limit` then `decrement_rate_limit`) where one would do.
- **Fix:**
    1. New migration: delete duplicate rows keeping the lowest `tokens_remaining` per `user_id`; `ALTER TABLE rate_limit_buckets DROP CONSTRAINT unique_user_ip;` then `ADD CONSTRAINT rate_limit_buckets_user_id_key UNIQUE (user_id);`. Drop `client_ip` from the table (it is informational only).
    2. Replace `get_or_create_rate_limit` + `decrement_rate_limit` with one atomic statement keyed only by `user_id`:
        ```sql
        INSERT INTO rate_limit_buckets (user_id, tokens_remaining, bucket_capacity, last_replenished_at)
        VALUES ($1, $2 - 1, $2, NOW())
        ON CONFLICT (user_id) DO UPDATE SET
          tokens_remaining = CASE WHEN rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour'
                                  THEN rate_limit_buckets.bucket_capacity - 1
                                  ELSE rate_limit_buckets.tokens_remaining - 1 END,
          last_replenished_at = CASE WHEN rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour'
                                     THEN NOW() ELSE rate_limit_buckets.last_replenished_at END
        WHERE rate_limit_buckets.tokens_remaining > 0
           OR rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour'
        RETURNING tokens_remaining;
        ```
        `NULL` result → 429.
    3. Update `get_quota` and `refund` to key by `user_id` only. Remove the `client_ip` parameter from those signatures.
    4. Keep `guest_ip_llm_limiter` as a second, per-IP guard for guests.
- **Verify:** Test: consume a guest's 5 tokens from IP A, then call from IP B. Expect 429.

### SEC-03 · High · Upload cost amplification and event-loop blocking

- **Where:** `apps/backend/app/routes/documents.py:104-222`; `apps/backend/app/rag/parser.py:103-192`; `apps/backend/app/rag/embeddings.py:31-84`.
- **Problem:** One upload costs one quota token. A 5 MB file at 800-char chunks with 100 overlap gives about 7,500 chunks, which is about 75 sequential `batchEmbedContents` calls (10 s timeout each). `parse_markdown` is synchronous CPU work inside an `async def` route, so it blocks every other request on the worker while it runs. `README.md:109` says to run a single worker, so one upload can stall the whole API.
- **Fix:**
    1. Lower `MAX_FILE_BYTES` to 1 MB (`documents.py:33` and `page.tsx:20`; see CLN-11 for sharing the constant).
    2. Add `MAX_CHUNKS_PER_DOCUMENT = 400` in `config.py`. After parsing, if `len(chunks)` is over the cap, return 413 with a clear message.
    3. Run parsing off the loop: `chunks = await asyncio.to_thread(default_markdown_parser.parse_markdown, ...)`.
    4. Charge quota by size: `cost = max(1, ceil(len(chunks) / 100))`. Add `check_and_consume(..., cost=n)` support to the limiter (decrement by `n`, fail if fewer than `n` remain).
    5. Allow one concurrent upload per user: keep an `asyncio.Lock` per `user_id` in a bounded dict, and return 409 "Upload already in progress" if it is held.
- **Verify:** Test with a generated 1.5 MB file → 413. Test that a file producing 401 chunks → 413. Test that two parallel uploads by the same user → the second gets 409.

### SEC-04 · Medium · Token in `localStorage` + CSP `'unsafe-inline'`; no revocation; endless refresh

- **Where:** `apps/frontend/lib/auth-store.ts:133-136,167-171`; `apps/frontend/next.config.ts:17` (`script-src 'self' 'unsafe-inline'`); `apps/frontend/app/layout.tsx:56-60` (inline theme script); `apps/backend/app/routes/auth.py:105-135`; `apps/backend/app/core/auth.py:38-50`.
- **Problem:**
    - Any XSS can read the 24 h bearer token from `localStorage`. `'unsafe-inline'` removes CSP's protection against injected inline scripts.
    - Logout only clears the browser, so a stolen token stays valid for 24 h.
    - `/auth/refresh` reissues a fresh 24 h token from any valid token with no maximum session age, so a stolen token can be renewed indefinitely.
    - Guest tokens are refreshed with `ACCESS_TOKEN_EXPIRE_MINUTES`, not `GUEST_TOKEN_EXPIRE_MINUTES`.
- **Fix (KISS, no cookie migration needed):**
    1. Add a new migration with `ALTER TABLE users ADD COLUMN token_version INT NOT NULL DEFAULT 0;`. Put `"tv": user.token_version` and `"auth_time"` (first-login epoch) in every token. In `get_current_user`, reject the token when `payload["tv"] != user.token_version`.
    2. Add `POST /api/auth/logout`, which increments `token_version`. Call it from `useAuthStore.logout` before clearing storage (fire-and-forget).
    3. In `/auth/refresh`, keep `auth_time` from the old token. Reject with 401 if `now - auth_time > 7 days`.
    4. Remove `'unsafe-inline'` from `script-src` in production. Next 16 supports per-request nonces through `proxy.ts`/middleware; give the theme script in `layout.tsx` that nonce. Alternatively remove the inline script and set the `dark` class from a blocking external `/theme-init.js` served from `public/`.
    5. Add `iss` and `aud` claims (e.g. `nexusagent-api`) and validate them in `decode_access_token`.
- **Verify:** Test: logout, then reuse the old token → 401. Test: refresh a token whose `auth_time` is 8 days old → 401. In a production build, the response CSP header contains no `'unsafe-inline'` in `script-src`.

### SEC-05 · Medium · Upload validation gaps

- **Where:** `apps/backend/app/routes/documents.py:123-161`.
- **Problem:**
    - `if ext not in ALLOWED_EXTENSIONS and file.content_type not in ALLOWED_MIME_TYPES` accepts a file when _either_ check passes, and `content_type` is chosen by the client. Any binary file sent as `text/plain` is accepted.
    - The `latin-1` fallback never raises, so binary content is stored as garbage text, and the `except UnicodeDecodeError` branch at `:157` is dead.
    - `filename` is unbounded, but `documents.filename` is `VARCHAR(255)`, so a long name causes an asyncpg error and a 500.
    - `mime_type` is persisted from the client header.
- **Fix:**
    1. Require the extension to be in the allowed set (use `and`-logic: reject if `ext not in ALLOWED_EXTENSIONS`). Ignore the client MIME type and store `text/markdown` or `text/plain` derived from the extension.
    2. Decode strictly as UTF-8 (accept and strip a BOM). On failure return 415. Reject content containing `\x00`.
    3. Sanitise the filename: `os.path.basename`, strip control characters, truncate to 200 characters, and fall back to `uploaded_document.md` if empty.
- **Verify:** Tests: a `.png` sent with `content_type=text/plain` → 415; a file containing NUL bytes → 415; a 300-character filename → 200 with a truncated filename.

### SEC-06 · Medium · MCP arguments are not schema-validated

- **Where:** `apps/backend/app/mcp/registry.py:191-198`; `apps/backend/app/mcp/dispatch.py:42-50`; `apps/backend/app/core/audit_log.py:40-81`.
- **Problem:**
    - `AGENTs.md §3.4` requires Pydantic-validated tool arguments. `int(arguments.get("limit", 5))` raises `ValueError` on `"abc"`, which surfaces as a generic internal error.
    - If `arguments` is not a dict (e.g. a list), `.get` raises `AttributeError`.
    - `query` has no length limit (`/rag/search` caps it at 1000).
    - The raw `arguments` dict, of any size, is written to `tool_audit_logs.input_args` (JSONB) and to the in-memory ring.
- **Fix:**
    1. Define `class HybridRagSearchArgs(BaseModel): query: str = Field(min_length=1, max_length=1000); limit: int = Field(5, ge=1, le=20)`, with `model_config = ConfigDict(extra="forbid")`.
    2. Generate `ToolDefinition.inputSchema` from `HybridRagSearchArgs.model_json_schema()` so the schema and the validation cannot drift.
    3. In `call_tool`, validate with `model_validate(arguments)`. On `ValidationError` return a JSON-RPC `INVALID_PARAMS` error (-32602) with the field errors.
    4. Store only the validated, bounded args in the audit log.
- **Verify:** Tests: `{"limit":"abc"}` → -32602; `arguments=[]` → -32602; a 5,000-character query → -32602.

### SEC-07 · Medium · Prompt-injection detection on the user query does nothing

- **Where:** `apps/backend/app/agent/graph.py:177-183`; `apps/backend/app/agent/state.py:72-74`; `apps/backend/app/routes/agent.py:193-213`.
- **Problem:**
    - `planner_node` sets `injection_detected`/`injection_reason`, but nothing reads them. The query is still sent to the LLM, and the flag is not included in any SSE event. The TODO board claims retrieved-chunk injections "surface an observability warning" (`target/TODOs.md:122`); they do not.
    - The regex list also drops legitimate retrieved chunks that merely _mention_ "system prompt" or "jailbreak". For a security-architecture knowledge base this is a silent false positive.
- **Fix (pick one, then document it in `ARCHITECTURE.md §10.1`):**
    - **Option A (recommended, KISS):** treat regexes as telemetry only. Remove the user-query scan from `planner_node` and the dead state fields. Keep the chunk scan, but instead of dropping a chunk, keep it wrapped and add `injectionWarnings: [{filename, reason}]` to the `tool_result` and `done` SSE payloads. Show a small warning in the observability panel.
    - **Option B:** block. When the user query matches, short-circuit like `out_of_scope` with a fixed refusal and do not consume quota.
- **Verify:** Test: a retrieved chunk containing "ignore previous instructions" produces a non-empty `injectionWarnings` in `done`.

### SEC-08 · Medium · Google identity keyed on email; `tokeninfo` endpoint

- **Where:** `apps/backend/app/core/auth.py:215-267`; `apps/backend/app/db/neon.py:109-140`.
- **Problem:** Accounts are upserted `ON CONFLICT (email)`, and the verified `sub` is returned and then discarded. Emails can change or be recycled (for example, Workspace accounts deleted and recreated), so a new person with the same address inherits the old account's history. Google recommends verifying ID tokens locally against its JWKS rather than calling `tokeninfo` on every login, which is an extra network dependency and was designed as a debugging endpoint.
- **Fix:**
    1. New migration: `ALTER TABLE users ADD COLUMN google_sub VARCHAR(255) UNIQUE;`.
    2. Upsert on `google_sub`. On first login, if a row exists with the same email and `google_sub IS NULL`, attach the `sub` to it (one-time backfill).
    3. Verify with `google-auth` (`google.oauth2.id_token.verify_oauth2_token(token, requests.Request(), GOOGLE_CLIENT_ID)`) in a thread, or with PyJWT plus a cached `PyJWKClient("https://www.googleapis.com/oauth2/v3/certs")`. Keep the `iss`, `aud` and `email_verified` checks.
- **Verify:** Test: two logins with the same email but different `sub` produce two distinct user rows.

### SEC-09 · Low · Unbounded in-memory sliding-window counters

- **Where:** `apps/backend/app/core/rate_limiter.py:31-55`.
- **Problem:** `_events` adds a key for every IP it sees and never removes it. Each key holds a list of datetimes. Traffic from many IPs grows memory without bound.
- **Fix:** When `len(self._events) > 50_000`, drop keys whose newest event is older than `window`. Also drop a key when its `recent` list becomes empty.
- **Verify:** Unit test: insert 60,000 keys with timestamps two hours old, then call `hit` once; the dict shrinks below 50,000.

### SEC-10 · Low · MCP results returned without untrusted-content handling

- **Where:** `apps/backend/app/mcp/registry.py:218-233`.
- **Problem:** Chunks go to external agents (Claude Desktop, Cursor) as raw text, without `sanitize_retrieved_chunks` or `wrap_untrusted_context`. Only seeded documents are searched today, so the risk is low. It becomes real if user uploads are ever exposed through MCP.
- **Fix:** Run `sanitize_retrieved_chunks(results)` and return the wrapped contexts (`<untrusted_document_context …>`) in the tool's text content.
- **Verify:** Test: the tool output contains `<untrusted_document_context`.

### SEC-11 · Low · Production exposes API docs and DB fingerprint

- **Where:** `apps/backend/app/main.py:44-46`; `apps/backend/app/routes/health.py:35-47`.
- **Problem:** `/docs`, `/redoc` and `/openapi.json` are public in production. The public `/api/health` returns the exact PostgreSQL version, installed extensions and the environment name.
- **Fix:**
    1. Set `docs_url`, `redoc_url` and `openapi_url` to `None` unless `settings.ENVIRONMENT in ("development", "test")`.
    2. Have `/api/health` return only `{"status", "database": {"connected"}}`. Move version and extension details behind development mode.
- **Verify:** With `ENVIRONMENT=production`, `/docs` returns 404 and `/api/health` has no `engine` or `extensions` keys. Update `tests/test_main.py` to match.

### SEC-12 · Medium · Privacy policy and Terms contradict the code

- **Where:** `apps/frontend/app/privacy/page.tsx`, `apps/frontend/app/terms/page.tsx`.
- **Problem:** Statements that do not match the code:
    - "client-side cryptographic isolation". There is none.
    - "transient execution traces are automatically pruned after 24 hours" and "logs … without long-term server-side archival". In fact `tool_audit_logs` stores every query text (`input_args`) indefinitely. Guest pruning only sets `user_id` to NULL, and the text remains.
    - "an isolated user partition". Isolation is an application-level `WHERE` clause; there is no RLS or separate schema.
    - It does not say that IP addresses are also stored for Google users, or that a hashed device ID is stored for guests.
    - It does not say whether Gemini API inputs may be used by Google. On the Gemini API free tier, Google may use prompts to improve its products. The policy must name the tier in use.
    - Cloudflare edge rate limiting is not configured anywhere in this repo.
    - Terms §3 mentions "read-only database queries" as an agent tool, which no longer exists.
- **Fix:** Rewrite both pages to describe what the code actually does, using the bullets above. Add an `updated` date. If the deployment uses the Gemini free tier, say so explicitly, or switch to a paid tier. This is a legal-accuracy fix; keep the wording plain.
- **Verify:** The verifier re-reads both pages against `audit_log.py`, `neon.py` and `auth.py`.

### SEC-13 · Low · Audit log "immutable" only by convention; raw prompts kept forever

- **Where:** `apps/backend/app/core/audit_log.py`; `migrations/20260901000000_core_schema.sql:98-109`; `README.md:117-123`.
- **Problem:** Nothing prevents `UPDATE` or `DELETE` on `tool_audit_logs`; the README asks the operator to `REVOKE` by hand. Full user prompts are stored with no retention limit.
- **Fix:**
    1. New migration: a `BEFORE UPDATE OR DELETE ON tool_audit_logs` trigger that raises an exception, except for a retention function run by the prune script.
    2. Store `query_sha256` and `query_len` instead of the raw query in `input_args` for `hybrid_rag_search`. Alternatively, keep the raw query and add `DELETE FROM tool_audit_logs WHERE executed_at < NOW() - INTERVAL '30 days'` to `scripts/prune_guests.py`.
    3. Choose one option and state it in the privacy policy (SEC-12).
- **Verify:** A db-marked test: `UPDATE tool_audit_logs …` raises.

### SEC-14 · Low · CORS credentials and missing throttles

- **Where:** `apps/backend/app/main.py:51-64`; `apps/backend/app/routes/auth.py`; `apps/backend/app/routes/chat.py`.
- **Problem:**
    - `allow_credentials=True` is unnecessary: auth uses an `Authorization` header and no cookies are used.
    - `/auth/google` (outbound call to Google), `/auth/refresh`, `/chat/history?q=` (an unindexed `ILIKE` over all message content) and `/documents` have no throttling.
- **Fix:**
    1. Set `allow_credentials=False`.
    2. Add a per-IP `SlidingWindowCounter` for `/auth/google` (e.g. 20/h) and `/auth/refresh` (e.g. 60/h).
    3. Cap `q` at 200 characters in `/chat/history`.
- **Verify:** Test: the 21st `/auth/google` call in an hour from one IP → 429.

---

## 3. Logic and correctness findings

### LOG-01 · High · Fake streaming; TTFT metric is false

- **Where:** `apps/backend/app/agent/graph.py:446` (`await llm_chain.ainvoke(messages)`); `apps/backend/app/routes/agent.py:163-177`; `apps/frontend/hooks/useAgentStream.ts:192-199`; `apps/frontend/components/observability-panel.tsx:69`.
- **Problem:**
    - The synthesizer waits for the _complete_ LLM response. The route then splits it on spaces and emits 3-word `token` events with `sleep(0.01)`.
    - The UI's "First token" tile therefore measures the full model latency plus replay, which contradicts the project's "No Simulated Telemetry Rule" and the "sub-600ms TTFT" goal.
    - `done` repeats the whole response, doubling the payload.
- **Fix:**
    1. Split the synthesizer into "build messages" (pure function: `build_synthesis_messages(state) -> list[BaseMessage]`) and "generate".
    2. Use `astream_events(..., version="v2")` on the compiled graph, or call `llm_chain.astream(messages)` inside the synthesizer node and push each `AIMessageChunk.content` to an `asyncio.Queue` passed through `RunnableConfig["configurable"]`. The route forwards each real chunk as a `token` event.
    3. Delete the word-splitting loop and the `sleep`.
    4. Keep `done` but drop `response` from it (the client already has the text). Keep the canary check: accumulate the text and, if the canary appears, emit an `error`/`redact` event telling the client to replace the text.
    5. The canary check now runs after tokens have been shown. Document that the canary detects leaks; it does not prevent display. Alternatively, buffer and scan a sliding window of the last `len(canary)` characters before forwarding each chunk.
- **Verify:** Mock the LLM so `astream` yields 3 chunks with 200 ms gaps. The test receives the first `token` event in under 300 ms, and the total number of `token` events is 3.

### LOG-02 · Medium · Conversation title overwritten on every turn

- **Where:** `apps/backend/app/db/neon.py:515-533` (`ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title`); called from `apps/backend/app/routes/agent.py:223-224` with the _current_ query as the title.
- **Problem:** Every follow-up renames the conversation to the latest question. The sidebar list then appears to reshuffle titles.
- **Fix:** Change the conflict clause to `ON CONFLICT (id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP WHERE agent_conversations.user_id = EXCLUDED.user_id`, leaving the title untouched. Keep `RETURNING`.
- **Verify:** Test: two turns with different queries in one session; the title equals the first query.

### LOG-03 · Medium · `done` sent before persistence; disconnect cancels the save

- **Where:** `apps/backend/app/routes/agent.py:192-242,258-268`; `apps/frontend/app/page.tsx:348` (`void loadConversations(true)` right after `done`).
- **Problem:**
    1. The client refetches `/chat/history` as soon as it gets `done`, but the server writes the conversation _after_ emitting `done`. The fresh list can miss the new conversation and overwrite the optimistic entry, so the chat vanishes from the sidebar until the next refresh.
    2. If the client disconnects after `done` (tab closed, Stop pressed), the generator's `finally` cancels `pipeline_task` and the turn is never saved.
- **Fix:**
    1. Move persistence _before_ the `done` event and include `conversationId` in `done`.
    2. Run persistence in a shielded task (`await asyncio.shield(persist())`) so a disconnect cannot cancel it.
    3. In `page.tsx`, drop the immediate `loadConversations(true)`. The optimistic update plus `conversationId` from `done` is enough. Optionally refetch after 1 s.
- **Verify:** Test: read the SSE stream until `done`, then immediately `GET /chat/history`; the conversation is present.

### LOG-04 · High · Embedding fallback mixes vector spaces

- **Where:** `apps/backend/app/rag/embeddings.py:11,24,50,69`.
- **Problem:** `GEMINI_EMBED_MODELS = ["gemini-embedding-001", "gemini-embedding-2", "text-embedding-004"]`. If the first model returns 404, the next one is used and becomes `active_model` for the process. Vectors from different models live in unrelated spaces, so cosine similarity between them is meaningless, and the documents table does not record which model produced each vector. A fallback silently corrupts dense retrieval for every document embedded before or after the switch. The mutable `active_model` is also shared process state.
- **Fix:**
    1. Use a single pinned model: `EMBEDDING_MODEL = "gemini-embedding-001"` in settings. Remove the fallback list and `active_model`.
    2. On failure, raise. Callers already handle errors (upload → 503; search → see LOG-08).
    3. New migration: `ALTER TABLE document_chunks ADD COLUMN embedding_model VARCHAR(64);`, filled on insert. Dense search filters `WHERE c.embedding_model = $model`.
    4. Send `taskType`: `RETRIEVAL_DOCUMENT` for chunks and `RETRIEVAL_QUERY` for queries (`get_embeddings(texts, task_type=...)`). This is supported by `gemini-embedding-001` and improves retrieval quality.
    5. Re-run `scripts/seed_kb.py` after the migration.
- **Verify:** Unit test: a 404 from the model → `RuntimeError`, and no second model is tried. Test that the request payload contains `taskType`.

### LOG-05 · Medium · Citation pipeline is inconsistent

- **Where:** `apps/backend/app/agent/graph.py:258-272,377,408-425`; `apps/frontend/components/canvas/MarkdownRenderer.tsx:122-129,166-203,524-531`; `apps/frontend/components/workspace-sidebar.tsx:161-163`.
- **Problem:**
    1. The system prompt never tells the model how to cite. Inline pills appear only if the model happens to write `[file.md (Lines X-Y)]`.
    2. The retriever builds citations for 5 chunks, but the synthesizer sends only the top 3 to the model. The "Grounding Citations" tray lists sources the model never saw.
    3. `renderCitations` turns any `[name.md]` into a pill, even when the filename is not in `citations`. A hallucinated source is then rendered as a verified citation ("Retrieved from a knowledge base chunk").
    4. `citationMap` is keyed by filename, so several chunks from one file collapse to the last one, and the pill shows the wrong preview and lines.
    5. The sidebar highlights a document by filename _substring_ (`"a.md"` matches `"data.md"`) instead of by `documentId`.
- **Fix:**
    1. Give each context block a short stable label, e.g. `[S1]`…`[S3]`, in the wrapper attribute (`wrap_untrusted_context(..., label="S1")`). Add to the system prompt: "Cite sources inline as [S1], [S2] … using only the labels provided. Never invent labels." Send `citations` as `{label, chunkId, documentId, filename, startLine, endLine, headerPath, preview}` and include **only the chunks passed to the model**.
    2. In `MarkdownRenderer`, match `/\[S(\d+)\]/g` against a map from label to citation. Render unknown labels as plain text. Remove the filename regex and `CITABLE_EXTENSION`.
    3. Pass `documentId` through `onCitationClick` and compare `doc.id === selectedCitationDocId` in the sidebar.
- **Verify:** Frontend test: content `"See [S2] and [S9]"` with one citation labelled S2 renders exactly one pill. Backend test: `len(done.citations) == number of chunks in the prompt`.

### LOG-06 · Medium · "Critic" is a constant heuristic shown as reflection

- **Where:** `apps/backend/app/agent/graph.py:307-339`; `apps/backend/app/agent/state.py:63-69`; `apps/frontend/components/observability-panel.tsx:71,153-168`; `apps/frontend/hooks/useAgentStream.ts:188`.
- **Problem:**
    - `score` can only be 0.35, 0.80 or 0.95. Because `citations == chunks`, `citation_bonus` is always applied whenever chunks exist.
    - The UI shows "Critic Soundness: 95% (Grounded)" or "(Re-planning)". The log line says "REPLAN", and a tile is labelled "Critic loops". No re-planning or loop exists (`needs_replan` is always `False`; the graph is a straight line).
    - `TODOs.md:63` marks "reflection critic node with loop-back condition (capped at 10 iterations)" as done.
    - All of this conflicts with the Honesty Rule.
- **Fix (KISS):**
    1. Rename the node's output to what it is: `grounding = "grounded" | "weak" | "none"` based on `chunks_count` and the best `dense_score` (`>= 0.5`). Drop `reflection_score`, `needs_replan`, `iteration_count`, `max_iterations` and `_run_config`.
    2. UI: replace the percentage badge with "Grounded in N sources" or "No supporting sources found". Remove the "Critic loops" tile and the "REPLAN"/"Re-planning" strings.
    3. Update the contracts (`AgentInvokeResponse`) and the SSE `critic` payload to match.
    4. If a real critic is wanted later, implement it as an LLM call with a defined rubric. Until then, do not label this as reflection.
- **Verify:** `grep -ri "replan\|re-planning\|critic loops" apps/` returns nothing.

### LOG-07 · Medium · Chunk line numbers are wrong

- **Where:** `apps/backend/app/rag/parser.py:18-35,114,149,173`.
- **Problem:** `compute_line_positions` finds the _first occurrence_ of the chunk's first line anywhere in the document. Repeated lines (`---`, ` ``` `, table headers, overlap chunks) map to an earlier location. Line numbers are also computed on the _scrubbed_ text: secret redaction collapses multi-line private keys, so every later line number shifts away from the original file.
- **Fix:**
    1. Track a running character cursor: for each sub-chunk, search with `full_text.find(sub_text_first_line, cursor)` and advance the cursor to the match position. Overlapping chunks restart from the previous chunk's start.
    2. Do the redaction per chunk _after_ positions are computed on the original text (scrub `sub_text`, not the whole document). Alternatively, replace a redacted block with the same number of newlines.
- **Verify:** Test: a document where `---` appears on lines 3 and 40; the chunk starting at line 40 reports `startLine == 40`.

### LOG-08 · Medium · Lexical search rarely matches; sequential; no degraded mode

- **Where:** `apps/backend/app/db/neon.py:483,504`; `apps/backend/app/rag/hybrid_search.py:177-194`.
- **Problem:**
    - `plainto_tsquery` ANDs every non-stop-word, so "Which models have the lowest input token cost per 1M on OpenRouter?" needs all terms in one 800-character chunk. The sparse side of RRF then contributes almost nothing.
    - Dense and sparse queries run sequentially, though the docstring says "parallel".
    - If the embedding call fails, the whole search raises, even though lexical search could still answer.
- **Fix:**
    1. Use `websearch_to_tsquery('english', $1)`, or build an OR query: `to_tsquery('english', string_agg(lexeme, ' | '))` from `ts_debug` / `tsvector_to_array(to_tsvector('english', $1))`. The OR form gives the best recall for RRF.
    2. Run the embedding call and the lexical query concurrently with `asyncio.gather` (dense must wait for the embedding, so gather `embed+dense` with `sparse`).
    3. If the embedding fails, log a warning and return sparse-only RRF results. Add `degraded: true` to the result so the UI can say so.
- **Verify:** db test: the sample query above returns at least one sparse hit from `openrouter_metrics.md`. Unit test: embedding raises → results come back with `dense_rank is None`.

### LOG-09 · Medium · Quota consumed before validation; not refunded on cancel

- **Where:** `apps/backend/app/routes/agent.py:284-306`; `apps/backend/app/routes/documents.py:118-179`; `apps/frontend/app/page.tsx:198`.
- **Problem:**
    - Agent: an invalid or inaccessible `documentId` returns 400/404 _after_ a token was consumed.
    - Upload: 415, 409, 413, empty-file and 503 responses, and the dedup early return, all happen after consumption.
    - Client Stop or disconnect raises `CancelledError` (a `BaseException`), which skips the `except Exception` refund path.
    - The frontend decrements quota locally after every upload, even for a dedup, instead of using the server's count.
- **Fix:**
    1. Reorder both routes: parse, validate, check access and dedup first, then `check_and_consume` as the last step before the paid work.
    2. In `run_pipeline`, add `except asyncio.CancelledError:` → refund only if the synthesizer had not started its LLM call (track a `llm_started` flag), then re-raise.
    3. Return `quotaRemaining` in the upload response and use it in `page.tsx` instead of `quotaRemaining - 1`.
- **Verify:** Tests: an inaccessible `documentId` → 404 and quota unchanged; a duplicate upload → quota unchanged.

### LOG-10 · Medium · stdio MCP server never connects to the DB

- **Where:** `apps/backend/app/mcp/server.py:28-79`.
- **Problem:**
    - `main()` never calls `neon_db.connect()`, so `hybrid_rag_search` always returns "Knowledge base unavailable" over stdio. This is the transport that Claude Desktop and Cursor use.
    - `handle_jsonrpc_request` calls `req_dict.get` on whatever was parsed, so a JSON array (batch) or scalar raises `AttributeError` and kills the read loop.
    - Notifications are checked twice (`:40` and `:70`).
- **Fix:**
    1. In `main()`: `await neon_db.connect()` before the loop and `await neon_db.disconnect()` in a `finally`.
    2. If `not isinstance(req_data, dict)`, respond `INVALID_REQUEST` with `id=None` and continue.
    3. Keep one notification check.
- **Verify:** Test: `handle_jsonrpc_request([1,2])` returns an INVALID_REQUEST error dict without raising.

### LOG-11 · Low · History window magic numbers; guests lose context silently

- **Where:** `apps/backend/app/routes/agent.py:310-318` (`[-2 * 6:]`); `apps/backend/app/agent/state.py:50`; `apps/backend/app/agent/graph.py:433`.
- **Problem:**
    - The route fetches _all_ messages, keeps the last 12, and the synthesizer then keeps the last 6, so only 3 turns survive. Both numbers are hard-coded in two places.
    - Guests always start fresh (`sessionId` is ignored for guests), but the UI looks like a continuous chat and follow-up questions quietly lose context.
- **Fix:**
    1. Add `settings.CHAT_HISTORY_MESSAGES = 6`. Fetch with `LIMIT` in SQL (newest N, then reverse) and remove `max_history_turns` from the state.
    2. Either keep the last N turns for guests in memory, keyed by guest `session_id` with a TTL (simple dict, max 1,000 sessions), or show an inline note in the UI for guests: "Guest chats don't remember earlier questions. Sign in with Google to keep context."
- **Verify:** Test: the conversation history query uses `LIMIT`; a guest follow-up either receives history or the UI note renders.

### LOG-12 · Low · Scope classifier easy to bypass; computed 3 times

- **Where:** `apps/backend/app/agent/graph.py:54-162,185,399,491`; `apps/backend/app/routes/agent.py:284`.
- **Problem:**
    - The keyword list includes generic words ("model", "token", "pipeline", "queue", "eval", "metrics", "diagram"), so "write a poem about a model" counts as architectural and costs a live LLM call. The guardrail is a cost gate, not a scope boundary.
    - `classify_query_intent` runs in the route, the planner, the router and the synthesizer (DRY).
- **Fix:**
    1. Classify once in the planner and store `state.intent`. `route_after_planner` and the synthesizer read `state.intent`. The route keeps its own call only to decide quota, or better, always consumes quota except for refusals detected by the planner (then refund).
    2. Remove the most generic single words ("model", "token", "pipeline", "queue", "eval", "metrics", "diagram", "vector", "partition") or require two keyword hits for single generic words.
- **Verify:** Update `test_guardrails_domain.py` with "write a poem about a model" → `out_of_scope`.

### LOG-13 · Medium · No document deletion

- **Where:** `apps/backend/app/routes/documents.py:132-137`; `apps/frontend/components/workspace-sidebar.tsx:159-192`.
- **Problem:** After 20 uploads the API returns 409 "Delete a document first", but no delete endpoint or UI exists. The privacy policy also promises users can remove stored documents.
- **Fix:**
    1. Add `DELETE /api/documents/{id}`: 404 unless `doc.user_id == current_user.id and not doc.is_seeded`; `DELETE FROM documents WHERE id=$1 AND user_id=$2` (chunks cascade). Write an audit entry.
    2. Add a trash button for non-seeded documents in the sidebar, using the same two-step confirm pattern as `SidebarChatHistory`.
- **Verify:** Tests: owner delete → 200 and chunks gone; deleting someone else's doc → 404; deleting a seeded doc → 404.

### LOG-14 · Medium · Starter prompts ask about models not in the knowledge base

- **Where:** `apps/frontend/components/chat-canvas.tsx:126-131`; `apps/frontend/components/mcp/McpInspector.tsx:22`.
- **Problem:** The suggested prompts ask about "Claude Sonnet 3.7 vs GPT-4o" and "Gemini 2.5 Flash". `grep -i "sonnet 3.7\|gpt-4o\|gemini 2.5 flash" knowledge_base/` returns nothing. The first thing a demo user clicks produces an ungrounded answer. ("Sonnet 3.7" is also not the model's real name; it is "Claude 3.7 Sonnet".)
- **Fix:** Replace the four prompts and the MCP default query with questions answerable from the four KB files, using model names that appear in them (e.g. "Compare Claude Opus 5 and its peers on SWE-Bench Verified in CursorBench"). Add a frontend test that pins the list so changes are deliberate.
- **Verify:** For each prompt, run `/api/rag/search` (db test) and assert at least one result whose `filename` matches the intended file.

### LOG-15 · Low · `seed_kb.py` rotates IDs; hash differs from upload

- **Where:** `scripts/seed_kb.py:62-64,116`.
- **Problem:** Each run deletes all seeded documents and inserts new UUIDs, which invalidates every stored citation `documentId`. The seed hashes decoded text while upload hashes raw bytes (`documents.py:163`), so identical files get different hashes.
- **Fix:** Derive a stable ID with `uuid5(NAMESPACE_URL, f"kb:{doc_path.name}")`. Upsert documents (`ON CONFLICT (id) DO UPDATE`) and replace that document's chunks. Hash `doc_path.read_bytes()`.
- **Verify:** Run twice; document IDs are unchanged.

### LOG-16 · Low · Account switch within 8 s skips the conversation fetch

- **Where:** `apps/frontend/hooks/useChatHistory.ts:41-42,91-127`.
- **Problem:** `lastFetchConversationsRef` is not reset when `user.id` changes. User B signing in within 8 s of user A's fetch gets no list.
- **Fix:** In the existing `[user?.id]` effect, also reset `lastFetchConversationsRef.current = 0` and `setConversations([])`.
- **Verify:** Hook test: switch users and assert that `apiClient` was called for the second user.

### LOG-17 · Low · Fabricated audit timing; missing conversation link

- **Where:** `apps/backend/app/agent/graph.py:291-298` (`duration_ms=0`); `apps/backend/app/routes/documents.py:209-216` (`duration_ms=0`).
- **Problem:** Audit rows claim 0 ms, which is false telemetry. `conversation_id` is never set, so audit rows cannot be joined to chats.
- **Fix:** Time the search or upload with `time.perf_counter()`. Pass `conversation_id` when the session is a persisted conversation (Google users).
- **Verify:** Test: the audit entry has `duration_ms > 0` when the search is mocked with a 5 ms sleep.

### LOG-18 · Low · Message saves are not transactional

- **Where:** `apps/backend/app/db/neon.py:630-661`; `apps/backend/app/routes/agent.py:227-238`.
- **Problem:** The insert and the `updated_at` update are separate statements. The user message and the assistant message are saved in separate calls, so a failure can leave a question with no answer.
- **Fix:** Add `save_turn(conversation_id, user_content, assistant_content, plan_trace, reflection)` that runs both inserts and the `updated_at` update inside `async with conn.transaction():`. Delete `save_message`.
- **Verify:** db test: force the second insert to fail (e.g. invalid role); no rows remain.

### LOG-19 · Medium · DB outage → unhandled 500 everywhere

- **Where:** `apps/backend/app/db/neon.py:21-25` (`RuntimeError`); `apps/backend/app/core/auth.py:121`; `apps/backend/app/main.py:26-36`.
- **Problem:** If `connect()` fails at startup, the app still boots. Every authenticated request then raises `RuntimeError` from `get_pool()`, which becomes a 500 with a stack trace in the logs. Because auth needs the DB, the in-memory fallbacks in the rate limiter and audit logger can never be reached by an authenticated request (see CLN-02).
- **Fix:**
    1. Define `class DatabaseUnavailable(RuntimeError)` and raise it from `get_pool()`.
    2. Register `@app.exception_handler(DatabaseUnavailable)` returning 503 `{"detail": "Service temporarily unavailable"}` with `Retry-After: 30`.
    3. In production, fail fast at startup: if `ENVIRONMENT == "production"` and `connect()` returns `False`, raise.
- **Verify:** Test with `neon_db.pool = None` and a valid token: `/api/auth/me` → 503.

---

## 4. UI/UX and accessibility findings

### UX-01 · High · Text is too small to read comfortably

- **Where:** `MarkdownRenderer.tsx` (every block is `text-xs`, code `text-[11px]`), `chat-canvas.tsx`, `workspace-sidebar.tsx`, `observability-panel.tsx`, `SidebarChatHistory.tsx`, `McpInspector.tsx` (many `text-[10px]`/`text-[11px]`); spec `target/DESIGN.md:72-77` (`body-md: 14px`).
- **Problem:** Long technical answers render at 12px with 12px tables and 11px code. Sidebars use 10–11px. The design spec says 14px body and claims WCAG AAA.
- **Fix:**
    1. Answer body: `text-sm` (14px) with `leading-relaxed`; headings h2 `text-base`, h3 `text-sm`; code and tables `text-[13px]` (the spec's code size).
    2. User message bubble: `text-sm`.
    3. Raise every `text-[10px]` to at least `text-xs` (12px). Keep 11px only for timestamps and badges.
    4. Add `--text-body: 0.875rem` etc. to `@theme` in `globals.css` and use the tokens, instead of arbitrary values (this also satisfies AGENTs.md anti-pattern #2).
- **Verify:** `grep -rn "text-\[10px\]" apps/frontend/components apps/frontend/app` returns 0. Visual check at 1280px and 375px widths.

### UX-02 · Medium · Contrast below the stated targets

- **Where:** `apps/frontend/styles/globals.css`.
- **Problem (measured):**

    | Pair                                                  | Ratio      | Status                       |
    | ----------------------------------------------------- | ---------- | ---------------------------- |
    | Dark mode button: white on `--primary #3b82f6`        | **3.68:1** | Fails AA (needs 4.5)         |
    | `--warning #b45309` on `--warning-bg #fffbeb`         | 4.84:1     | Passes AA, fails claimed AAA |
    | `--success #15803d` on `--success-bg #ecfdf5`         | 4.76:1     | Passes AA, fails claimed AAA |
    | `--destructive #dc2626` on white                      | 4.83:1     | Passes AA, fails claimed AAA |
    | `--muted-foreground #475569` on `--secondary #f1f5f9` | 6.92:1     | Fails claimed AAA            |
    | Dark citation `#60a5fa` on `#1e293b`                  | 5.75:1     | Passes AA                    |

- **Fix:**
    1. Dark `--primary`: use `#2563eb` (white text about 5.2:1), and keep `#3b82f6` only for non-text accents.
    2. Decide on a target. **AA is the realistic one**; change `DESIGN.md §6` to "WCAG 2.2 AA" unless you darken `--warning` to `#92400e`, `--success` to `#166534` and `--destructive` to `#b91c1c` for 7:1.
- **Verify:** Re-run the contrast script on every foreground/background token pair; all text pairs are ≥ 4.5:1 (or ≥ 7:1 if AAA is kept).

### UX-03 · Low · Skip link never rendered

- **Where:** `apps/frontend/styles/globals.css:198-213`; `DESIGN.md:225-226`.
- **Problem:** `.skip-link` is styled, but no element uses it, and there is no `#main-canvas` target.
- **Fix:** Add `<a href="#main-canvas" className="skip-link">Skip to chat</a>` as the first child of `<body>` in `layout.tsx`, and `id="main-canvas"` on the `<main>` in `chat-canvas.tsx`.
- **Verify:** Tab once from page load; the skip link is visible and moves focus to the chat.

### UX-04 · Medium · Quota exhaustion opens a sales modal

- **Where:** `apps/frontend/app/page.tsx:396-399,411-414`; `apps/frontend/components/chat-canvas.tsx:86-107`; `apps/frontend/components/app-header.tsx:94-106` (`hidden sm:flex`).
- **Problem:** When quota hits 0, pressing Send opens "Hire Me" instead of saying when queries come back. The server knows `last_replenished_at` but does not expose it. On mobile the quota badge is hidden, so the user cannot see they are out until the modal appears.
- **Fix:**
    1. Backend: add `resetsAt` (ISO) to `QuotaStatus` and to the 429 body (`last_replenished_at + 1h`).
    2. Frontend: on Send with 0 quota, show an inline notice above the composer, "You've used all 5 queries. More at 14:32.", and disable Send. Keep a secondary "Need more?" link to the Hire Me modal.
    3. Show the quota badge on mobile, compact (`3/5`).
- **Verify:** Page test: quota 0 → notice with a time is visible; the modal does not open automatically.

### UX-05 · Medium · Citations cannot be opened

- **Where:** `apps/frontend/app/page.tsx:260-266`; `apps/frontend/components/canvas/CitationPill.tsx:38-43,88`; unused endpoint `GET /api/documents/{id}/chunks` (`documents.py:81-101`).
- **Problem:** Clicking a citation only highlights a filename in a collapsed list. On mobile it switches the tab away from the answer. Users cannot read the source passage. The design spec promises "jump to exact line ranges".
- **Fix:** On click, open a side `Dialog` (existing primitive) that fetches `/api/documents/{documentId}/chunks`, shows the cited chunk (scrolled into view, highlighted) with its header path and line range, and keeps the answer in place. Remove the mobile tab switch.
- **Verify:** Page test: click a pill → the dialog shows the preview text of that chunk.

### UX-06 · Medium · Hand-rolled Markdown parser (KISS)

- **Where:** `apps/frontend/components/canvas/MarkdownRenderer.tsx` (534 lines).
- **Problem:** The custom line parser has no italics, no nested lists, no ordered-list continuation across blank lines, no inline links without a scheme, and fragile table detection. It re-parses the whole document on every token. LLM output uses all of these features.
- **Fix:** Replace the parser with `react-markdown` + `remark-gfm`. Do not use `rehype-raw`, so raw HTML stays escaped. Keep custom `components` overrides for `code` (Mermaid and `CodeBlock`), `table` (`TableBlock`), `blockquote` (callouts), `a` (http/https only, `rel="noopener noreferrer"`), and a text transformer for `[S1]` citation labels (LOG-05). This deletes about 350 lines.
- **Verify:** Existing `MarkdownRenderer.test.tsx` cases still pass, plus new ones for `*italic*` and nested lists.

### UX-07 · Low · Floating "New Chat" button overlaps content

- **Where:** `apps/frontend/components/chat-canvas.tsx:69-82`.
- **Problem:** The button is `absolute top-4 right-4 z-20` over the scrolling thread, so it covers the top-right of messages and tables.
- **Fix:** Put it in a slim sticky toolbar row above the thread (`sticky top-0` with a `bg-background/90` backdrop), or in the header next to the theme toggle.
- **Verify:** Visual check with a wide table at the top of the thread.

### UX-08 · Low · Internal jargon in end-user UI

- **Where:** `chat-canvas.tsx:179` ("Executing DAG [PLANNER]..."), `McpInspector.tsx:119,221` ("MCP v2", "RPC 200 OK"), `observability-panel.tsx:157` ("Critic Soundness"), `sign-in-dialog.tsx:94` ("5 live LLM quota gift").
- **Problem:** "MCP v2" is not a protocol name (the implementation speaks MCP `2024-11-05`). "RPC 200 OK" mixes HTTP and JSON-RPC. Loading text exposes node names.
- **Fix:** Use plain status text: "Searching sources…", "Writing answer…" (map from `currentNode`); "MCP (2024-11-05)"; "Success"/"Error"; "You get 5 free questions per hour." Keep raw node names only in the observability panel.
- **Verify:** `grep -rn "MCP v2\|RPC 200 OK\|quota gift" apps/frontend` returns 0.

### UX-09 · Low · MCP Inspector asks for a token users cannot get

- **Where:** `apps/frontend/components/mcp/McpInspector.tsx:239-257`.
- **Problem:** It tells external-client users to add `Authorization: Bearer`, but there is no UI to copy a token. It also renders for signed-out users, and Invoke then fails with an HTTP 401.
- **Fix:** If `!authToken`, show "Sign in to try MCP tools" with the sign-in button. For signed-in users, add a "Copy access token (expires in 24 h)" button next to the endpoint, with a warning not to share it. Alternatively, if external MCP use is not a goal, remove the external-client tip (YAGNI).
- **Verify:** Component test for the signed-out state.

### UX-10 · Low · Two fetch layers (DRY)

- **Where:** `apps/frontend/app/page.tsx:139-158,174-203`; `apps/frontend/components/mcp/McpInspector.tsx:79-110`; `apps/frontend/hooks/useAgentStream.ts:104-113`.
- **Problem:** Document list, upload, MCP calls and the stream use raw `fetch` with hand-built headers. A 401 there does not log the user out, error messages differ, and the token is passed around as a prop.
- **Fix:** Use `apiClient` for the docs list, upload and MCP (it already handles `FormData`). For the stream, read the token through the same getter and call the registered unauthorized callback on 401. Remove the `token`/`authToken`/`apiBase` props from `WorkspaceSidebar`, `McpInspector` and `StreamParams`.
- **Verify:** Tests: a 401 from upload triggers logout.

### UX-11 · Low · Reloaded conversations lose citations

- **Where:** `apps/backend/app/routes/agent.py:228-238`; `apps/frontend/hooks/useChatHistory.ts:137-153`.
- **Problem:** Citations are not persisted, so an old answer re-renders without pills and without the citation tray.
- **Fix:** Save `citations` (wire form) inside `reflection_summary` (or a new `citations JSONB` column in a new migration) and map them back in `handleSelectConversation`.
- **Verify:** Reload a conversation; the citation tray renders.

### UX-12 · Low · Composer auto-grow not cross-browser

- **Where:** `apps/frontend/components/composer.tsx:34` (`[field-sizing:content]`).
- **Problem:** `field-sizing` is not supported in Firefox or older Safari, so the textarea stays one row there.
- **Fix:** Add a fallback: in `onChange`, set `el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 160) + 'px'`.
- **Verify:** Manual check in Firefox.

---

## 5. Cleanup: dead, unused and redundant code (YAGNI / DRY / KISS)

Delete these in the order listed. Every item was checked with `grep` across `apps/`, `scripts/` and `packages/`; "used only by tests" means the tests must be updated or deleted too.

### CLN-01 · Unused DB methods (`apps/backend/app/db/neon.py`)

| Symbol                                                        | Status                                          | Action                                                                                                  |
| ------------------------------------------------------------- | ----------------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| `execute_migration` (`:59-63`)                                | unused                                          | delete                                                                                                  |
| `fetchrow` (`:71-75`)                                         | unused                                          | delete                                                                                                  |
| `create_document` (`:319-340`)                                | tests only                                      | delete; tests use `create_document_with_chunks`                                                         |
| `insert_document_chunks` (`:342-365`)                         | tests only                                      | delete; same as above                                                                                   |
| `get_document_by_hash` no-`user_id` branch (`:385-389`)       | unreachable                                     | make `user_id` required, delete branch                                                                  |
| `get_conversation` + `get_conversation_messages` (`:535-628`) | duplicate of `get_conversation_with_messages`   | `agent.py:315-318` switches to `get_conversation_with_messages` (with `LIMIT`, see LOG-11); delete both |
| `get_seeded_documents` (`:260-266`)                           | duplicate of `list_all_documents(user_id=None)` | `/chat/documents` uses `list_all_documents`; delete                                                     |
| `save_message`                                                | replaced by `save_turn` (LOG-18)                | delete                                                                                                  |

### CLN-02 · In-memory fallbacks that authenticated requests can never reach (KISS)

- **Where:** `apps/backend/app/core/rate_limiter.py:22-28,63-94,139-149,173-174,190-193`; `apps/backend/app/core/audit_log.py:20-21,53-54,94-102,151`.
- **Why:** Every route that uses them first runs `get_current_user`, which needs the DB (LOG-19). The fallbacks only make sense if the DB fails _between_ the auth lookup and the quota call, and in that case a per-process bucket silently resets on restart. The audit ring also keeps every user's queries in process memory.
- **Action:** Delete `MemoryBucket`, `_memory_buckets` and `_get_memory_bucket`, and the DB-error fallback branches (raise `DatabaseUnavailable` instead). Delete the audit `_memory_audit_logs` ring and `get_recent_audit_logs`; on write failure, log at error level (already done). Update `reset_for_test` and the tests (`test_security_hitl.py::test_audit_logs_per_user_isolation_in_memory`, `test_token_bucket_rate_limiter_depletion`) to use the DB or mocks.

### CLN-03 · Backwards-compatibility aliases for removed HITL

- **Where:** `apps/backend/app/core/audit_log.py:155-157` (`HitlCoordinator`, `default_hitl_coordinator`).
- **Action:** Delete. No references remain.

### CLN-04 · MCP "tool poisoning" and "rug-pull" checks against our own constants

- **Where:** `apps/backend/app/core/security_guardrails.py:189-274`; `apps/backend/app/mcp/registry.py:14,49-52,72-107,156-162`; tests `test_security_hitl.py::test_mcp_tool_poisoning_detection`, `::test_mcp_registry_blocks_tampered_rug_pull`.
- **Why:** These checks are meant for tool definitions received _from third-party MCP servers_. NexusAgent has no MCP client. `PINNED_TOOL_HASHES` is computed at import time from the same `TOOLS` constant it is later compared against, so it can never fail at runtime. This is security theatre, and it adds a `schemaHash` field that is not part of the MCP spec.
- **Action:** Delete `MCP_POISONING_PATTERNS`, `scan_mcp_tool_metadata`, `compute_mcp_tool_hash`, `PINNED_TOOL_HASHES`, `validate_tool_integrity` and the `schemaHash` field, plus their tests. Note in `ARCHITECTURE.md §10.8` that these controls apply when an MCP client is built.

### CLN-05 · Unused agent state and recursion config

- **Where:** `apps/backend/app/agent/state.py:50,63-69,73-74` (`max_history_turns`, `reflection_score`, `reflection_feedback`, `needs_replan`, `iteration_count`, `max_iterations`, `injection_*`); `apps/backend/app/agent/graph.py:535-538` (`_run_config`, "cyclical reflection" comment on a graph with no cycles).
- **Action:** Remove together with LOG-06, SEC-07 and LOG-11. The graph uses LangGraph's default recursion limit.

### CLN-06 · Unused schema columns and settings

- `users.hashed_password` and `User.hashed_password`: password auth was removed (`TODOs.md:33`). New migration `ALTER TABLE users DROP COLUMN hashed_password;` and drop the field and the `INSERT`/`RETURNING` lists in `neon.py`.
- `documents.storage_path`: written only by the seed script, never read. Drop the column (new migration), the `Document`/wire fields and the contract field.
- `Settings.DATABASE_URL` (`config.py:41`): a duplicate of `NEON_DATABASE_URL`. Keep one (`DATABASE_URL` is the more conventional name) and update `.env.example`, `conftest.py` and the scripts.
- `GUEST_TOKEN_EXPIRE_MINUTES` versus `ACCESS_TOKEN_EXPIRE_MINUTES`: both default to 24 h. Keep both only if they differ (see SEC-04); otherwise keep one.
- `GEMINI_MODELS` fallback inside `_get_llm_chain` (`graph.py:344-346`) repeats the setting's default. Delete the `getattr` and fallback.

### CLN-07 · Endpoints with no consumer (YAGNI)

| Endpoint                         | Consumer                                                  | Action                                                                                                                                                                                                             |
| -------------------------------- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `GET /api/chat/documents`        | used for signed-out users only                            | Keep **one** document list: make `GET /api/documents` work without auth (seeded only) via `get_current_user_optional`; delete `/chat/documents`; drop the snake/camel `normalizeDoc` fallbacks in `page.tsx:23-30` |
| `POST /api/chat/history`         | tests only (conversations are created by `/agent/stream`) | delete route and its test step                                                                                                                                                                                     |
| `GET /api/mcp/sse?once=true`     | test hook in a production route                           | delete `once`; test the endpoint event with a streaming client that closes after the first event                                                                                                                   |
| `GET /api/documents/{id}/chunks` | none today                                                | **keep** and use it for UX-05; delete only if UX-05 is rejected                                                                                                                                                    |
| `POST /api/rag/search`           | none in UI (MCP covers it)                                | optional: keep as public API; it is metered                                                                                                                                                                        |

### CLN-08 · Frontend dead code

- `components/ui/input.tsx`: never imported. Delete.
- `CardFooter`, `DialogFooter`, `DialogClose`, `PopoverAnchor` exports: unused. They are standard shadcn exports; deleting them is optional (low value).
- `HireMeModal` `trigger` prop and `DialogTrigger` branch (`hire-me-modal.tsx:10,22`): unused. Delete.
- `ObservabilityPanel` `isOpen` prop (`observability-panel.tsx:34`): never read. Delete. Also remove the dead `lg:w-80` class (the panel is hidden below `xl`).
- `LogEntry.meta`: never set by any caller. Delete.
- `McpToolOption` type export and `MCP_TOOLS` array with a single item (`McpInspector.tsx:10-24`): inline the one tool.
- `ChatItem.citations?: any[]` → `Citation[]`; `scrollContainerRef as any`, `fileInputRef as any`: fix the types.
- `auth-store.ts:73-74,193-194`: leftover removal of `nexusagent_byok_*` keys from the removed BYOK feature. Delete after one release.
- Duplicate comment line `MermaidViewer.tsx:9-10`. Delete one.
- `packages/contracts/src/documents.ts` is never imported. Either use it (`WorkspaceDoc` → `DocumentMetadata`, upload response typing) or delete it. Recommended: use it.
- `apiClient` `params` option: unused outside its test. Keep (cheap) or delete (YAGNI); low priority.
- One `TooltipProvider` per `CitationPill`: move a single provider to `layout.tsx` or `page.tsx`.

### CLN-09 · Self-testing tests

- **Where:** `apps/backend/tests/test_hybrid_search.py:20-65` (`generate_deterministic_embedding`, `test_embedding_generation_dimension_and_norm`, `test_embedding_determinism`).
- **Why:** They test a helper defined inside the test file, not product code.
- **Action:** Delete the helper and both tests. If the helper is used to build fixtures in db tests, keep it as a fixture without its own tests.

### CLN-10 · Repo-level clutter

- `package.json:8-17`: duplicate script aliases (`dev:fe`/`dev:frontend`, `dev:be`/`dev:backend`, `test:fe`/`test:frontend`, `test:be`/`test:backend`). Keep one set.
- `.gitignore:57-61`: `.freebuff`, `apps/frontend/AGENTS.md` and `apps/frontend/CLAUDE.md` are personal tool artefacts. Move them to `.git/info/exclude`.
- `.agents/rules/adhd.md`, `caveman.md`, `ponytail.md`: AI assistant output-style rules, not product files. `ponytail.md` forbids third-party UI libraries ("native `<dialog>` … strictly forbidden from installing third-party tools"), which contradicts `DESIGN.md`/`AGENTs.md` (shadcn/ui + Radix are mandated). Delete the folder, or move it to the user's global agent config. If kept, remove the contradiction.

### CLN-11 · Duplicated constants across the stack (DRY)

- Quota numbers `5`/`25` are hard-coded in `auth-store.ts:53-54,88,100,164-165,203-204`, `sign-in-dialog.tsx:51,94`, `terms/page.tsx` and `models.py:33-34,123-124`. The server already returns `bucketCapacity`. Use it, and default to `null` ("—") until known.
- Upload limit `5 MB` appears in `page.tsx:20`, `workspace-sidebar.tsx:219` and `documents.py:33`. Expose `maxUploadBytes` from a small `GET /api/config` (or put it in the 413 body) and read it once.
- `"http://localhost:8000"` appears in `api-client.ts:1` and `McpInspector.tsx:31`. Use `API_BASE` only. In production builds, fail the build if `NEXT_PUBLIC_API_URL` is missing (check in `next.config.ts`).
- The domain `nexusagent.avinaba.com` is hard-coded in `workspace-sidebar.tsx:315`, the legal pages and `config.py:23`. Move it to `NEXT_PUBLIC_SITE_HOST`.

### CLN-12 · Contracts duplicated by hand (DRY)

- **Where:** `packages/contracts/src/*.ts` versus the Pydantic wire models in `apps/backend/app/db/models.py:78-151`, `routes/rag.py`, `routes/agent.py` (dict literals), and `routes/chat.py` (dict literals).
- **Problem:** The two sides already drift. `AgentInvokeResponse.createdAt` is never sent. `/chat/documents` returns snake_case. SSE payloads are untyped dicts.
- **Action:** Give every route a Pydantic `response_model` (including SSE event payload models), then generate TS types from `/openapi.json` with `openapi-typescript` into `packages/contracts/src/generated.ts`. Re-export the needed names and delete the hand-written duplicates. Add a CI check that regenerating produces no diff.

---

## 6. Documentation and spec drift

`AGENTs.md` says the `target/` docs are the source of truth and forbids marking unbuilt work as done. Today they describe a different system.

### DOC-01 · `TODOs.md` marks non-existent work as done

| Line   | Claim (checked `[x]`)                                       | Reality                                            |
| ------ | ----------------------------------------------------------- | -------------------------------------------------- |
| 63     | Critic "with loop-back condition (capped at 10 iterations)" | Straight-line graph, no loop (LOG-06)              |
| 70     | Streams `tool_call` events                                  | Never emitted                                      |
| 77     | "Markdown renderer with code syntax highlighting"           | No highlighting                                    |
| 79     | "Citation Pills with line jump"                             | Click only highlights a filename (UX-05)           |
| 111    | "unresolved approvals fail closed on timeout"               | HITL was removed                                   |
| 118    | BYOK `validate_byok_key`                                    | BYOK removed in `dd0f7c5`; function does not exist |
| 122    | Injection "surfaces an observability warning"               | Not surfaced (SEC-07)                              |
| 15–132 | Phases 3, 10, 11, 12, 13 headed `[Completed]`               | Each has unchecked items                           |

**Fix:** Uncheck or delete the false items, change phase headers to `[Partial]` where items remain open, and add a "Removed" note where a feature was intentionally dropped (as already done for Phase 6).

### DOC-02 · `AGENTs.md` invariants that the code does not follow

- `§3.1`: "FastMCP (`fastmcp ^2.0`)", "gemini-3.8-flash with cascading fallbacks", "llama-index-core ^0.12.0", "FastAPI ^0.141.1". The code uses a hand-rolled JSON-RPC server, `gemini-2.5-flash`/`-lite`, `llama-index-core>=0.14.25` and `fastapi>=0.115.0`.
- `§0` and `ASI-07`: "Deterministic Simulator mode must be available at all times". It was deleted (`TODOs.md:102,130`).
- `ASI-06`: HITL is required for mutating tools. HITL was removed; this is acceptable only because all tools are read-only, so say that.
- `ASI-05`: references `report.md S-01`, which does not exist in the repo (this report replaces it; update the reference to "previous audit, removed sandbox").
- `§1`: "Dual MCP server and client". There is no client.

**Fix:** Edit `AGENTs.md` to describe the code as it is. For each removed capability, write "Not implemented" and the condition for adding it.

### DOC-03 · `ARCHITECTURE.md` describes FastMCP and other absent parts

- `:134,543-549`: "FastMCP Sub-Application mounted via `app.mount('/api/mcp', mcp_app)`" and "`fastmcp run app/routes/mcp.py`". Neither exists.
- Re-check the DDL in `§6.2` against `migrations/` and replace it with a pointer to the migration files (DRY: one schema source).
- Update `§10` (OWASP) after SEC-01…SEC-13 land.

### DOC-04 · `README.md` and `DESIGN.md` drift

- README `:14`: "MCP v2 server … and client" (no client; protocol `2024-11-05`). `:15`: "append-only tool audit logging" (convention only, SEC-13). `:31`: "cyber obsidian tokens" (the theme is light enterprise). `:89-93`: `pnpm dev` starts only the frontend; the backend needs `pnpm dev:be`.
- `DESIGN.md §2.1` token block uses `--color-primary: #0a66c2`, while the front matter and `globals.css` use `#004ea1`. `§3` describes an icon rail, a topology map, TCP throughput charts and a service-mesh table that do not exist. The app is a 3-column chat. `§6` claims AAA (UX-02).
- **Fix:** Rewrite `DESIGN.md §2.1` to quote `globals.css` exactly (or link to it), and replace `§3` with the real layout (header, workspace sidebar, chat canvas, observability panel, mobile tab bar).

### DOC-05 · Knowledge-base data provenance

- **Where:** `knowledge_base/benchmarks/*.md`.
- **Problem:** The files attribute figures to real third parties (Artificial Analysis, BenchLM, CursorBench, OpenRouter) with "Last Updated: September 2026", but give no per-table source URL or retrieval date and no trace of how the figures were collected (`TODOs.md:131` says live scraping was removed). If any figure is estimated or hand-entered, presenting it as the named source's data breaks the Honesty Rule.
- **Fix:** For each table, add `Source URL` and `Retrieved: YYYY-MM-DD`. Mark any unverified or estimated values with an explicit "(estimate)". The verifier should spot-check five rows per file against the public source.

---

## 7. Test-suite findings

### TST-01 · `test_migrations.py` reconnects the shared pool

- **Where:** `apps/backend/tests/test_migrations.py:17-24`.
- **Problem:** It calls `neon_db.connect()` while the session fixture already holds a pool (the first pool leaks), then `disconnect()`s, which sets `neon_db.pool = None` for every later db test in the session.
- **Fix:** Remove the `connect()`/`disconnect()` calls and rely on the session fixture.

### TST-02 · Tests depend on a live LLM

- **Where:** `test_agent_dag.py:49-52`, `test_agent_stream.py:50`.
- **Problem:** They assert `"## Architectural Analysis"` and a Mermaid block in a real Gemini answer, so the results are non-deterministic and cost money.
- **Fix:** Mock `_get_llm_chain` to return a fixed response in these tests, and keep a separate opt-in `@pytest.mark.live_llm` smoke test.

### TST-03 · Weak or wrong assertions

- `test_main.py:58-68` sends the CORS preflight to `/health` (no such route) instead of `/api/health`.
- `test_security_hitl.py:400-426` ends with `assert call_res is not None`, which proves nothing (deleted with CLN-04 anyway).

### TST-04 · No CI

- **Problem:** No `.github/workflows` exist, but `AGENTs.md §4` requires build, lint and test gates.
- **Fix:** Add one workflow with two jobs:
    - Backend: `uv sync`, `ruff check`, `ruff format --check`, `pytest -q`. db tests are skipped without `TEST_DATABASE_URL`; optionally use a Neon branch secret.
    - Frontend: `pnpm install --frozen-lockfile`, `pnpm --filter @nexusagent/frontend typecheck lint test build`.

### TST-05 · Missing regression tests

Each `SEC-*`/`LOG-*` item above names its test. Also add:

- an SSE parser test with `\r\n` line endings and multi-line `data:` fields. `useAgentStream.ts:145-151` keeps only the last `data:` line; fix by joining them with `\n` as the SSE spec requires;
- a test that `MarkdownRenderer` never renders raw HTML from content.

---

## 8. Recommended fix order

Each batch can ship on its own. Within a batch, follow the listed order.

1. **Stop the money leaks:** SEC-01 → SEC-02 → SEC-03 → LOG-09.
2. **Data correctness (before re-seeding):** LOG-04 → LOG-07 → LOG-15, then run `scripts/seed_kb.py` once → LOG-08.
3. **Remove dead weight (shrinks later diffs):** CLN-01 → CLN-02 + LOG-19 → CLN-03 → CLN-04 → CLN-06 → CLN-07 → CLN-08 → CLN-09 → CLN-10.
4. **Agent honesty and chat correctness:** LOG-06 + CLN-05 → SEC-07 → LOG-01 → LOG-02 → LOG-03 → LOG-18 → LOG-05 → LOG-11 → LOG-12 → LOG-17.
5. **Auth and remaining security:** SEC-04 → SEC-05 → SEC-06 → SEC-08 → SEC-09 → SEC-10 → SEC-11 → SEC-13 → SEC-14.
6. **Features users hit:** LOG-13 → LOG-14 → LOG-10 → LOG-16.
7. **UI/UX:** UX-01 → UX-02 → UX-03 → UX-04 → UX-05 → UX-06 → UX-07 … UX-12.
8. **Contracts and tests:** CLN-11 → CLN-12 → TST-01 … TST-05.
9. **Docs last, so they describe the final code:** SEC-12 → DOC-01 … DOC-05.

---

## 9. Verified as correct (do not re-flag)

These were checked and are fine. The verifier should not spend time on them unless a fix touches them.

- **SQL injection:** every query is parameterised. The f-strings in `search_chunks_dense`/`search_chunks_lexical` only build `$n` placeholder indices from fixed strings.
- **Tenancy:** `require_document_access` checks owner-or-seeded. Dense and lexical search filter `is_seeded OR user_id = $n`. Every conversation query filters `user_id`. `create_conversation`'s conflict clause cannot hijack another user's conversation ID (the `WHERE` returns no row).
- **JWT:** the algorithm is pinned (`algorithms=[HS256]`), the secret must be at least 32 characters outside dev/test, and `DEBUG` is refused in production. Role and guest status are read from the DB, not from token claims.
- **XSS in model output:** `MarkdownRenderer` never uses `dangerouslySetInnerHTML`. Links are limited to `http(s)`. Mermaid uses `securityLevel: 'strict'` plus DOMPurify on the SVG.
- **SSE framing:** payloads are `json.dumps` single lines, so newline injection into the event stream is not possible.
- **Client IP:** `X-Forwarded-For` is ignored unless `TRUST_PROXY_HEADERS=true`.
- **Gemini key:** sent in the `x-goog-api-key` header, not in the URL.
- **Migrations:** applied once each under a Postgres advisory lock, tracked in `schema_migrations`.
- **Delete confirmation** for chats, **Escape and focus trap** in the expanded Mermaid view, and the `aria-live` status region are implemented correctly.

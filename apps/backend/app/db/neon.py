import json
import logging
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings
from app.db.models import Document, DocumentChunk, RateLimitBucket, User

logger = logging.getLogger("nexusagent.db.neon")


_TS_TERM = re.compile(r"[A-Za-z0-9]{2,}")
MAX_TS_TERMS = 20


def build_or_tsquery(text: str) -> str:
    """Turn free text into a safe ``a | b | c`` tsquery (alphanumeric terms only)."""
    terms = list(dict.fromkeys(t.lower() for t in _TS_TERM.findall(text)))[:MAX_TS_TERMS]
    return " | ".join(terms)


class DatabaseUnavailable(RuntimeError):
    """Raised when a request needs the database but the pool is not connected."""


class DocumentLimitReached(RuntimeError):
    """The user already stores ``MAX_DOCUMENTS_PER_USER`` documents."""


class NeonDatabase:
    def __init__(self, dsn: str | None = None):
        self.dsn = dsn or settings.NEON_DATABASE_URL
        self.pool: asyncpg.Pool | None = None
        # pgvector >= 0.8 can keep scanning the HNSW index until enough rows pass the WHERE filter.
        self.hnsw_iterative_scan = False

    def get_pool(self) -> asyncpg.Pool:
        """Return the active connection pool or raise an error if not connected."""
        if self.pool is None:
            raise DatabaseUnavailable("Neon database connection pool is not initialized.")
        return self.pool

    async def connect(self) -> bool:
        """Establish connection pool to Neon PostgreSQL 18."""
        if not self.dsn:
            logger.warning("No Neon database URL provided; connection skipped.")
            return False

        try:

            async def init_connection(conn: asyncpg.Connection):
                await register_vector(conn)

            self.pool = await asyncpg.create_pool(
                self.dsn,
                min_size=1,
                max_size=10,
                statement_cache_size=0,
                init=init_connection,
            )
            logger.info("Successfully connected to Neon PostgreSQL 18 connection pool.")
            await self._detect_pgvector_features()
            return True
        except (asyncpg.PostgresError, OSError, ConnectionError) as e:
            logger.error(f"Failed to connect to Neon PostgreSQL: {e}")
            self.pool = None
            return False

    async def _detect_pgvector_features(self) -> None:
        try:
            version = await self.get_pool().fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
            )
            parts = tuple(int(p) for p in str(version).split(".")[:2])
            self.hnsw_iterative_scan = parts >= (0, 8)
        except (asyncpg.PostgresError, ValueError, TypeError) as e:
            logger.warning(f"Could not detect the pgvector version ({e}); using plain HNSW scans.")
            self.hnsw_iterative_scan = False

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Closed Neon PostgreSQL connection pool.")

    async def fetch(self, query: str, *args: Any) -> list[asyncpg.Record]:
        """Execute query and fetch all records."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            return await conn.fetch(query, *args)

    async def create_user(self, user: User) -> User:
        """Insert a new user record."""
        pool = self.get_pool()
        query = """
            INSERT INTO users (id, email, name, avatar_url, is_guest, client_ip, device_id, created_at, last_seen_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            RETURNING *;
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                user.id,
                user.email,
                user.name,
                user.avatar_url,
                user.is_guest,
                user.client_ip,
                user.device_id,
                user.created_at,
                user.last_seen_at,
            )
            return User(**dict(row))

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """Fetch user by primary UUID key."""
        pool = self.get_pool()
        query = "SELECT * FROM users WHERE id = $1;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, user_id)
            return User(**dict(row)) if row else None

    async def upsert_google_user(
        self,
        google_sub: str,
        email: str,
        name: str,
        avatar_url: str | None = None,
        client_ip: str | None = None,
    ) -> User:
        """
        Find or create the account for a verified Google identity, keyed on the stable ``sub``.

        An account that predates ``sub`` tracking is adopted by email once. If a *different* Google
        account later presents an email that another row still holds, that row loses the email
        (it keeps its own data) so the newcomer never inherits someone else's history.
        """
        pool = self.get_pool()
        email = email.lower().strip()
        now = datetime.now(UTC)
        async with pool.acquire() as conn, conn.transaction():
            existing = await conn.fetchrow(
                "SELECT id FROM users WHERE google_sub = $1;", google_sub
            )
            if existing is None:
                existing = await conn.fetchrow(
                    "SELECT id FROM users WHERE email = $1 AND google_sub IS NULL AND is_guest = FALSE;",
                    email,
                )
            user_id = existing["id"] if existing else uuid4()
            await conn.execute(
                "UPDATE users SET email = NULL WHERE email = $1 AND id <> $2;", email, user_id
            )
            row = await conn.fetchrow(
                """
                INSERT INTO users (id, email, name, avatar_url, is_guest, client_ip, google_sub, created_at, last_seen_at)
                VALUES ($1, $2, $3, $4, FALSE, $5, $6, $7, $7)
                ON CONFLICT (id) DO UPDATE
                SET email = EXCLUDED.email,
                    name = EXCLUDED.name,
                    avatar_url = COALESCE(EXCLUDED.avatar_url, users.avatar_url),
                    is_guest = FALSE,
                    client_ip = COALESCE(EXCLUDED.client_ip, users.client_ip),
                    google_sub = EXCLUDED.google_sub,
                    last_seen_at = EXCLUDED.last_seen_at
                RETURNING *;
                """,
                user_id,
                email,
                name.strip(),
                avatar_url,
                client_ip,
                google_sub,
                now,
            )
            return User(**dict(row))

    async def bump_token_version(self, user_id: UUID) -> None:
        """Invalidate every token issued to the user (used by logout)."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE users SET token_version = token_version + 1 WHERE id = $1;", user_id
            )

    async def get_guest_by_device_id(self, device_id: str) -> User | None:
        """Fetch active guest user by unique persistent client device ID."""
        pool = self.get_pool()
        query = "SELECT * FROM users WHERE device_id = $1 AND is_guest = TRUE ORDER BY last_seen_at DESC LIMIT 1;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, device_id)
            return User(**dict(row)) if row else None

    async def update_user_last_seen(
        self, user_id: UUID, client_ip: str | None = None, device_id: str | None = None
    ) -> None:
        """Update last_seen_at timestamp, client IP, and device ID."""
        if not self.pool:
            return
        query = """
            UPDATE users
            SET last_seen_at = $1,
                client_ip = COALESCE($3, client_ip),
                device_id = COALESCE($4, device_id)
            WHERE id = $2;
        """
        async with self.pool.acquire() as conn:
            await conn.execute(query, datetime.now(UTC), user_id, client_ip, device_id)

    async def prune_expired_guests(self, ttl_hours: int = 24) -> int:
        """Prune ephemeral guest sessions inactive for longer than ttl_hours (Section 11 Architecture).

        Cascades via foreign keys to rate_limit_buckets, guest documents, and chunks.
        Returns the number of pruned guest user accounts.
        """
        if ttl_hours < 1:
            raise ValueError("ttl_hours must be >= 1")
        if not self.pool:
            return 0
        query = """
            DELETE FROM users
            WHERE is_guest = TRUE
              AND last_seen_at < NOW() - ($1 * INTERVAL '1 hour');
        """
        async with self.pool.acquire() as conn:
            result = await conn.execute(query, ttl_hours)
            try:
                count = int(result.split()[-1])
            except ValueError, IndexError:
                count = 0
            logger.info("Pruned %d expired guest user(s) older than %d hours.", count, ttl_hours)
            return count

    async def consume_rate_limit(
        self, user_id: UUID, default_tokens: int = 5, cost: int = 1
    ) -> int | None:
        """
        Atomically insert or replenish and consume `cost` tokens keyed only by user_id.
        Returns tokens_remaining, or None if quota exhausted.
        """
        pool = self.get_pool()
        query = """
            INSERT INTO rate_limit_buckets (user_id, tokens_remaining, bucket_capacity, last_replenished_at)
            VALUES ($1, $2 - $3, $2, NOW())
            ON CONFLICT (user_id) DO UPDATE SET
              tokens_remaining = CASE WHEN rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour'
                                      THEN rate_limit_buckets.bucket_capacity - $3
                                      ELSE rate_limit_buckets.tokens_remaining - $3 END,
              last_replenished_at = CASE WHEN rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour'
                                         THEN NOW() ELSE rate_limit_buckets.last_replenished_at END
            WHERE (rate_limit_buckets.last_replenished_at > NOW() - INTERVAL '1 hour' AND rate_limit_buckets.tokens_remaining >= $3)
               OR (rate_limit_buckets.last_replenished_at <= NOW() - INTERVAL '1 hour' AND rate_limit_buckets.bucket_capacity >= $3)
            RETURNING tokens_remaining;
        """
        async with pool.acquire() as conn:
            return await conn.fetchval(query, user_id, default_tokens, cost)

    async def prune_audit_logs(self, retention_days: int = 30) -> int:
        """Delete audit rows older than ``retention_days``. The only sanctioned way to remove audit rows."""
        if retention_days < 1:
            raise ValueError("retention_days must be >= 1")
        if not self.pool:
            return 0
        async with self.pool.acquire() as conn, conn.transaction():
            # Transaction-local switch that the append-only trigger honours for DELETE.
            await conn.execute("SELECT set_config('nexusagent.audit_retention', 'on', true);")
            result = await conn.execute(
                "DELETE FROM tool_audit_logs WHERE executed_at < NOW() - ($1 * INTERVAL '1 day');",
                retention_days,
            )
        try:
            count = int(result.split()[-1])
        except ValueError, IndexError:
            count = 0
        logger.info("Pruned %d audit row(s) older than %d days.", count, retention_days)
        return count

    async def get_or_create_rate_limit(
        self, user_id: UUID, default_tokens: int = 5
    ) -> RateLimitBucket:
        """
        Current bucket state without consuming. Read-only apart from creating the row: an expired
        bucket is reported as full (the next ``consume_rate_limit`` performs the actual refill).
        """
        pool = self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO rate_limit_buckets (user_id, tokens_remaining, bucket_capacity) "
                "VALUES ($1, $2, $2) ON CONFLICT (user_id) DO NOTHING;",
                user_id,
                default_tokens,
            )
            row = await conn.fetchrow(
                """
                SELECT id, user_id, bucket_capacity,
                       CASE WHEN last_replenished_at <= NOW() - INTERVAL '1 hour'
                            THEN bucket_capacity ELSE tokens_remaining END AS tokens_remaining,
                       CASE WHEN last_replenished_at <= NOW() - INTERVAL '1 hour'
                            THEN NOW() ELSE last_replenished_at END AS last_replenished_at
                FROM rate_limit_buckets
                WHERE user_id = $1;
                """,
                user_id,
            )
            return RateLimitBucket(**dict(row))

    async def refund_rate_limit(self, user_id: UUID, amount: int = 1) -> None:
        """Return ``amount`` tokens (capped at capacity) after a failed run."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            await conn.execute(
                "UPDATE rate_limit_buckets "
                "SET tokens_remaining = LEAST(tokens_remaining + $2, bucket_capacity) "
                "WHERE user_id = $1;",
                user_id,
                amount,
            )

    async def count_user_documents(self, user_id: UUID) -> int:
        """Count the number of documents owned by a user."""
        pool = self.get_pool()
        query = "SELECT COUNT(*) FROM documents WHERE user_id = $1;"
        async with pool.acquire() as conn:
            val = await conn.fetchval(query, user_id)
            return int(val or 0)

    async def create_document_with_chunks(
        self, document: Document, chunks: list[DocumentChunk]
    ) -> Document:
        """
        Insert a document and its chunks transactionally.

        For user uploads the per-user document limit is enforced here under an advisory lock, so
        concurrent uploads cannot exceed it. If the user already stores the same file (unique
        ``(user_id, sha256_hash)`` index) the existing document is returned instead.
        """
        pool = self.get_pool()
        doc_query = """
            INSERT INTO documents (id, user_id, filename, mime_type, sha256_hash, total_chunks, is_seeded, uploaded_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            RETURNING id, user_id, filename, mime_type, sha256_hash, total_chunks, is_seeded, uploaded_at;
        """
        chunk_query = """
            INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding, embedding_model, metadata, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8);
        """
        records = [
            (
                c.id,
                c.document_id,
                c.chunk_index,
                c.content,
                c.embedding,
                settings.EMBEDDING_MODEL if c.embedding is not None else None,
                json.dumps(c.metadata),
                c.created_at,
            )
            for c in chunks
        ]
        try:
            async with pool.acquire() as conn, conn.transaction():
                if document.user_id is not None:
                    await conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext($1::text));", str(document.user_id)
                    )
                    stored = await conn.fetchval(
                        "SELECT COUNT(*) FROM documents WHERE user_id = $1;", document.user_id
                    )
                    if stored >= settings.MAX_DOCUMENTS_PER_USER:
                        raise DocumentLimitReached
                row = await conn.fetchrow(
                    doc_query,
                    document.id,
                    document.user_id,
                    document.filename,
                    document.mime_type,
                    document.sha256_hash,
                    document.total_chunks,
                    document.is_seeded,
                    document.uploaded_at,
                )
                if records:
                    await conn.executemany(chunk_query, records)
                return Document(**dict(row))
        except asyncpg.UniqueViolationError:
            if document.user_id is not None:
                existing = await self.get_document_by_hash(document.sha256_hash, document.user_id)
                if existing:
                    return existing
            raise

    async def delete_user_document(self, user_id: UUID, document_id: UUID) -> bool:
        """Delete a document the user uploaded (chunks cascade). Seeded documents are never deletable."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "DELETE FROM documents WHERE id = $1 AND user_id = $2 AND is_seeded = FALSE RETURNING id;",
                document_id,
                user_id,
            )
            return row is not None

    async def get_document_by_id(self, document_id: UUID) -> Document | None:
        """Fetch document by primary UUID."""
        pool = self.get_pool()
        query = "SELECT * FROM documents WHERE id = $1;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, document_id)
            return Document(**dict(row)) if row else None

    async def get_document_by_hash(self, sha256_hash: str, user_id: UUID) -> Document | None:
        """Fetch a user's document by SHA-256 hash (per-user deduplication)."""
        pool = self.get_pool()
        query = "SELECT * FROM documents WHERE sha256_hash = $1 AND user_id = $2 LIMIT 1;"
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, sha256_hash, user_id)
            return Document(**dict(row)) if row else None

    @staticmethod
    def _chunk_from_row(row: asyncpg.Record) -> DocumentChunk:
        data = dict(row)
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])
        return DocumentChunk(**data)

    async def get_document_chunks(
        self, document_id: UUID, limit: int | None = None
    ) -> list[DocumentChunk]:
        """Fetch a document's chunks ordered by chunk_index (without their embeddings)."""
        pool = self.get_pool()
        query = """
            SELECT id, document_id, chunk_index, content, metadata, created_at
            FROM document_chunks
            WHERE document_id = $1
            ORDER BY chunk_index ASC
        """
        params: list[Any] = [document_id]
        if limit is not None:
            query += " LIMIT $2"
            params.append(limit)
        async with pool.acquire() as conn:
            rows = await conn.fetch(query + ";", *params)
            return [self._chunk_from_row(r) for r in rows]

    async def get_document_chunk(self, document_id: UUID, chunk_id: UUID) -> DocumentChunk | None:
        """Fetch one chunk of a document (without its embedding)."""
        pool = self.get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, document_id, chunk_index, content, metadata, created_at "
                "FROM document_chunks WHERE document_id = $1 AND id = $2;",
                document_id,
                chunk_id,
            )
            return self._chunk_from_row(row) if row else None

    async def list_all_documents(self, user_id: UUID | None = None) -> list[Document]:
        """List documents visible to the user (all seeded documents + user's uploaded documents)."""
        pool = self.get_pool()
        if user_id:
            query = """
                SELECT * FROM documents
                WHERE is_seeded = TRUE OR user_id = $1
                ORDER BY uploaded_at DESC;
            """
            async with pool.acquire() as conn:
                rows = await conn.fetch(query, user_id)
                return [Document(**dict(r)) for r in rows]
        else:
            query = "SELECT * FROM documents WHERE is_seeded = TRUE ORDER BY uploaded_at DESC;"
            async with pool.acquire() as conn:
                rows = await conn.fetch(query)
                return [Document(**dict(r)) for r in rows]

    async def search_chunks_dense(
        self,
        query_embedding: list[float],
        user_id: UUID | None = None,
        document_id: UUID | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Dense cosine similarity search on document_chunks using pgvector HNSW index."""
        pool = self.get_pool()
        conditions = ["c.embedding IS NOT NULL", "c.embedding_model = $2"]
        params: list[Any] = [query_embedding, settings.EMBEDDING_MODEL]
        idx = 3

        if document_id:
            conditions.append(f"c.document_id = ${idx}")
            params.append(document_id)
            idx += 1
        if user_id:
            conditions.append(f"(d.is_seeded = TRUE OR d.user_id = ${idx})")
            params.append(user_id)
            idx += 1
        else:
            conditions.append("d.is_seeded = TRUE")

        params.append(limit)
        limit_param = f"${idx}"

        where_clause = " AND ".join(conditions)
        query = f"""
            SELECT c.id, c.document_id, c.chunk_index, c.content, c.metadata, d.filename,
                   1 - (c.embedding <=> $1::vector) AS similarity
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_clause}
            ORDER BY c.embedding <=> $1::vector ASC
            LIMIT {limit_param};
        """
        async with pool.acquire() as conn, conn.transaction():
            # The WHERE filter runs after the HNSW scan, so a small ef_search can return too few rows.
            if self.hnsw_iterative_scan:
                await conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
                await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
            else:
                await conn.execute("SET LOCAL hnsw.ef_search = 200")
            rows = await conn.fetch(query, *params)
            return [dict(r) for r in rows]

    async def search_chunks_lexical(
        self,
        query: str,
        user_id: UUID | None = None,
        document_id: UUID | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Lexical full-text search (OR of query terms) using the tsvector GIN index."""
        ts_query = build_or_tsquery(query)
        if not ts_query:
            return []
        pool = self.get_pool()
        conditions = ["c.search_vector @@ to_tsquery('english', $1)"]
        params: list[Any] = [ts_query]
        idx = 2

        if document_id:
            conditions.append(f"c.document_id = ${idx}")
            params.append(document_id)
            idx += 1
        if user_id:
            conditions.append(f"(d.is_seeded = TRUE OR d.user_id = ${idx})")
            params.append(user_id)
            idx += 1
        else:
            conditions.append("d.is_seeded = TRUE")

        params.append(limit)
        limit_param = f"${idx}"

        where_clause = " AND ".join(conditions)
        query_sql = f"""
            SELECT c.id, c.document_id, c.chunk_index, c.content, c.metadata, d.filename,
                   ts_rank_cd(c.search_vector, to_tsquery('english', $1)) AS rank_score
            FROM document_chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE {where_clause}
            ORDER BY rank_score DESC
            LIMIT {limit_param};
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch(query_sql, *params)
            return [dict(r) for r in rows]

    async def create_conversation(
        self,
        user_id: UUID,
        title: str = "New Architectural Inquiry",
        conversation_id: UUID | None = None,
    ) -> dict:
        """Create a new conversation record."""
        pool = self.get_pool()
        cid = conversation_id or uuid4()
        query = """
            INSERT INTO agent_conversations (id, user_id, title, created_at)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE SET updated_at = CURRENT_TIMESTAMP
            WHERE agent_conversations.user_id = EXCLUDED.user_id
            RETURNING id, user_id, title, created_at;
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, cid, user_id, title)
            return dict(row) if row else {}

    async def list_conversations(
        self,
        user_id: UUID,
        search_term: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """List conversations for a user with aggregated message counts and latest snippets."""
        pool = self.get_pool()
        query = """
            WITH user_convs AS (
                SELECT id, user_id, title, created_at, updated_at
                FROM agent_conversations c
                WHERE c.user_id = $1 AND (
                    $2::text IS NULL OR
                    c.title ILIKE $2 OR
                    EXISTS (SELECT 1 FROM messages m WHERE m.conversation_id = c.id AND m.content ILIKE $2)
                )
                ORDER BY c.updated_at DESC
                LIMIT $3
            ),
            msg_stats AS (
                SELECT conversation_id,
                        COUNT(*) AS message_count,
                        (ARRAY_AGG(content ORDER BY created_at DESC))[1] AS last_snippet
                FROM messages
                WHERE conversation_id IN (SELECT id FROM user_convs)
                GROUP BY conversation_id
            )
            SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                    COALESCE(s.message_count, 0) AS message_count,
                    s.last_snippet
            FROM user_convs c
            LEFT JOIN msg_stats s ON c.id = s.conversation_id
            ORDER BY c.updated_at DESC;
        """
        search_pattern = f"%{search_term}%" if search_term else None
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, user_id, search_pattern, limit)
            return [dict(r) for r in rows]

    async def get_conversation_with_messages(
        self,
        user_id: UUID,
        conversation_id: UUID,
    ) -> tuple[dict | None, list[dict]]:
        """Fetch conversation metadata and ordered messages in a single connection checkout."""
        pool = self.get_pool()
        query_conv = """
            SELECT id, user_id, title, created_at
            FROM agent_conversations
            WHERE id = $1 AND user_id = $2;
        """
        query_msgs = """
            SELECT id, conversation_id, role, content, plan_trace, reflection_summary, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at ASC;
        """
        async with pool.acquire() as conn:
            conv_row = await conn.fetchrow(query_conv, conversation_id, user_id)
            if not conv_row:
                return None, []
            msg_rows = await conn.fetch(query_msgs, conversation_id)
            return dict(conv_row), [dict(r) for r in msg_rows]

    async def get_conversation_history(
        self, user_id: UUID, conversation_id: UUID, limit: int
    ) -> list[dict] | None:
        """Last ``limit`` messages (oldest first) of an owned conversation; None if not owned."""
        pool = self.get_pool()
        query = """
            SELECT role, content FROM (
                SELECT m.role, m.content, m.created_at
                FROM messages m
                JOIN agent_conversations c ON m.conversation_id = c.id
                WHERE c.id = $1 AND c.user_id = $2
                ORDER BY m.created_at DESC
                LIMIT $3
            ) recent
            ORDER BY created_at ASC;
        """
        async with pool.acquire() as conn:
            owned = await conn.fetchval(
                "SELECT 1 FROM agent_conversations WHERE id = $1 AND user_id = $2;",
                conversation_id,
                user_id,
            )
            if not owned:
                return None
            rows = await conn.fetch(query, conversation_id, user_id, limit)
            return [dict(r) for r in rows]

    async def save_turn(
        self,
        conversation_id: UUID,
        user_content: str,
        assistant_content: str,
        plan_trace: Any = None,
        reflection_summary: Any = None,
    ) -> None:
        """Persist a user question and its answer atomically and bump ``updated_at``."""
        pool = self.get_pool()
        insert = """
            INSERT INTO messages (id, conversation_id, role, content, plan_trace, reflection_summary, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7);
        """
        now = datetime.now(UTC)
        async with pool.acquire() as conn, conn.transaction():
            await conn.execute(
                insert, uuid4(), conversation_id, "user", user_content, None, None, now
            )
            await conn.execute(
                insert,
                uuid4(),
                conversation_id,
                "assistant",
                assistant_content,
                json.dumps(plan_trace) if plan_trace is not None else None,
                json.dumps(reflection_summary) if reflection_summary is not None else None,
                now + timedelta(milliseconds=1),
            )
            await conn.execute(
                "UPDATE agent_conversations SET updated_at = CURRENT_TIMESTAMP WHERE id = $1;",
                conversation_id,
            )

    async def delete_conversation(self, user_id: UUID, conversation_id: UUID) -> bool:
        """Delete conversation and cascade messages for verified owner."""
        pool = self.get_pool()
        query = """
            DELETE FROM agent_conversations
            WHERE id = $1 AND user_id = $2
            RETURNING id;
        """
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, conversation_id, user_id)
            return bool(row)


neon_db = NeonDatabase()


async def get_db() -> NeonDatabase:
    """FastAPI dependency for accessing database singleton."""
    return neon_db

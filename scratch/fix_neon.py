import sys

p = sys.argv[1]
raw = open(p, encoding="utf-8", newline="").read()
crlf = chr(13) in raw
s = raw.replace(chr(13) + chr(10), chr(10))


def r(a, b, n=1):
    global s
    assert s.count(a) == n, (a, s.count(a))
    s = s.replace(a, b)


r("from typing import Any\n", "from typing import ClassVar, cast\n")
r(
    "from app.db.models import Document, DocumentChunk, User\n",
    "from app.db.models import Document, DocumentChunk, User\nfrom app.db.records import (\n    col_int,\n    col_opt_datetime,\n    col_str,\n    record_dict,\n    require_row,\n)\n",
)
r(
    "    terms = list(dict.fromkeys(t.lower() for t in _TS_TERM.findall(text)))[:MAX_TS_TERMS]",
    "    found: list[str] = _TS_TERM.findall(text)\n    terms = list(dict.fromkeys(t.lower() for t in found))[:MAX_TS_TERMS]",
)
r("        self.dsn = dsn or settings.NEON_DATABASE_URL", "        self.dsn: str = dsn or settings.NEON_DATABASE_URL")
r("        self.hnsw_iterative_scan = False\n\n    def get_pool", "        self.hnsw_iterative_scan: bool = False\n\n    def get_pool")
r('            await conn.execute("CREATE EXTENSION', '            _ = await conn.execute("CREATE EXTENSION')
r(
    """            version = await self.get_pool().fetchval(
                "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
            )""",
    """            version = cast(
                object,
                await self.get_pool().fetchval(
                    "SELECT extversion FROM pg_extension WHERE extname = 'vector';"
                ),
            )""",
)
r("    async def fetch(self, query: str, *args: Any)", "    async def fetch(self, query: str, *args: object)")
r(
    "            return User(**dict(row))\n\n    async def get_user_by_id",
    '            return User.model_validate(record_dict(require_row(row, "INSERT users")))\n\n    async def get_user_by_id',
)
r(
    "            return User(**dict(row))\n\n    async def bump",
    '            return User.model_validate(record_dict(require_row(row, "UPSERT users")))\n\n    async def bump',
)
r("            return User(**dict(row)) if row else None", "            return User.model_validate(record_dict(row)) if row else None", 2)
r('            user_id = existing["id"] if existing else uuid4()', '            user_id = cast(UUID, existing["id"]) if existing else uuid4()')
r(
    """            await conn.execute(
                "UPDATE users SET email = NULL""",
    """            _ = await conn.execute(
                "UPDATE users SET email = NULL""",
)
r(
    """            await conn.execute(
                "UPDATE users SET token_version""",
    """            _ = await conn.execute(
                "UPDATE users SET token_version""",
)
r(
    '''            count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM users
                WHERE is_guest = TRUE AND client_ip = $1
                  AND created_at > NOW() - INTERVAL '1 hour';
                """,
                client_ip,
            )''',
    '''            count = cast(
                int | None,
                await conn.fetchval(
                    """
                    SELECT COUNT(*) FROM users
                    WHERE is_guest = TRUE AND client_ip = $1
                      AND created_at > NOW() - INTERVAL '1 hour';
                    """,
                    client_ip,
                ),
            )''',
)
r(
    """            await conn.execute(
                query, datetime.now(UTC), user_id""",
    """            _ = await conn.execute(
                query, datetime.now(UTC), user_id""",
)
r(
    """                "UPDATE users SET last_seen_at = NOW() "
                "WHERE id = $1 AND last_seen_at < NOW() - INTERVAL '5 minutes';",""",
    """                (
                    "UPDATE users SET last_seen_at = NOW() "
                    + "WHERE id = $1 AND last_seen_at < NOW() - INTERVAL '5 minutes';"
                ),""",
)
r("    USAGE_LOCK_KEY = 815_000_002", "    USAGE_LOCK_KEY: ClassVar[int] = 815_000_002")
r('    USAGE_COUNTS_SQL = """', '    USAGE_COUNTS_SQL: ClassVar[str] = """')
r(
    """    def _usage_counts(row: Any) -> UsageCounts:
        return UsageCounts(
            user=row["user_used"],
            user_oldest=row["user_oldest"],
            network=row["network_used"],
            network_oldest=row["network_oldest"],
            guests=row["guests_used"],
            guests_oldest=row["guests_oldest"],
            total=row["total_used"],
            total_oldest=row["total_oldest"],
        )""",
    """    def _usage_counts(row: asyncpg.Record | None) -> UsageCounts:
        row = require_row(row, "usage counts")
        return UsageCounts(
            user=col_int(row, "user_used"),
            user_oldest=col_opt_datetime(row, "user_oldest"),
            network=col_int(row, "network_used"),
            network_oldest=col_opt_datetime(row, "network_oldest"),
            guests=col_int(row, "guests_used"),
            guests_oldest=col_opt_datetime(row, "guests_oldest"),
            total=col_int(row, "total_used"),
            total_oldest=col_opt_datetime(row, "total_oldest"),
        )""",
)
r('            await conn.execute("SELECT pg_advisory_xact_lock', '            _ = await conn.execute("SELECT pg_advisory_xact_lock')
r(
    """            usage_id = await conn.fetchval(
                "INSERT INTO chat_usage (user_id, device_hash, client_ip) "
                "VALUES ($1, $2, $3) RETURNING id;",
                user_id,
                device_hash,
                client_ip,
            )""",
    """            usage_id = cast(
                UUID,
                await conn.fetchval(
                    "INSERT INTO chat_usage (user_id, device_hash, client_ip) "
                    + "VALUES ($1, $2, $3) RETURNING id;",
                    user_id,
                    device_hash,
                    client_ip,
                ),
            )""",
)
r('            await conn.execute("DELETE FROM chat_usage WHERE id', '            _ = await conn.execute("DELETE FROM chat_usage WHERE id')
r('            await conn.execute("SELECT set_config(', '            _ = await conn.execute("SELECT set_config(')
r(
    '''        await self.get_pool().execute(
            """
            INSERT INTO model_cooldowns''',
    '''        _ = await self.get_pool().execute(
            """
            INSERT INTO model_cooldowns''',
)
r(
    "    def _chunk_records(chunks: list[DocumentChunk]) -> list[tuple]:",
    "    def _chunk_records(chunks: list[DocumentChunk]) -> list[tuple[object, ...]]:",
)
r(
    """            await conn.execute(
                "DELETE FROM documents WHERE is_seeded""",
    """            _ = await conn.execute(
                "DELETE FROM documents WHERE is_seeded""",
)
r(
    """                await conn.execute(
                    doc_query,""",
    """                _ = await conn.execute(
                    doc_query,""",
)
r(
    """                await conn.execute(
                    "DELETE FROM document_chunks""",
    """                _ = await conn.execute(
                    "DELETE FROM document_chunks""",
)
r(
    "                return Document(**dict(row))",
    '                return Document.model_validate(record_dict(require_row(row, "INSERT documents")))',
)
r("            return Document(**dict(row)) if row else None", "            return Document.model_validate(record_dict(row)) if row else None", 2)
r(
    """        data = dict(row)
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])
        return DocumentChunk(**data)""",
    """        data = record_dict(row)
        metadata = data.get("metadata")
        if isinstance(metadata, str):
            data["metadata"] = cast(object, json.loads(metadata))
        return DocumentChunk.model_validate(data)""",
)
r("        params: list[Any] = [document_id]", "        params: list[object] = [document_id]")
r(
    """                "SELECT id, document_id, chunk_index, content, metadata, created_at "
                "FROM document_chunks WHERE document_id = $1 AND id = $2;",""",
    """                (
                    "SELECT id, document_id, chunk_index, content, metadata, created_at "
                    + "FROM document_chunks WHERE document_id = $1 AND id = $2;"
                ),""",
)
r("            return [Document(**dict(r)) for r in rows]", "            return [Document.model_validate(record_dict(r)) for r in rows]")
r('    ) -> list[dict]:\n        """Dense', '    ) -> list[dict[str, object]]:\n        """Dense')
r("        params: list[Any] = [query_embedding, settings.EMBEDDING_MODEL]", "        params: list[object] = [query_embedding, settings.EMBEDDING_MODEL]")
r(
    """                await conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
                await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
            else:
                await conn.execute("SET LOCAL hnsw.ef_search = 200")""",
    """                _ = await conn.execute("SET LOCAL hnsw.iterative_scan = 'relaxed_order'")
                _ = await conn.execute("SET LOCAL hnsw.max_scan_tuples = 20000")
            else:
                _ = await conn.execute("SET LOCAL hnsw.ef_search = 200")""",
)
r(
    """            rows = await conn.fetch(query, conversation_id, user_id, limit)
            return [dict(r) for r in rows]""",
    """            rows = await conn.fetch(query, conversation_id, user_id, limit)
            return [{"role": col_str(r, "role"), "content": col_str(r, "content")} for r in rows]""",
)
r("            return [dict(r) for r in rows]", "            return [record_dict(r) for r in rows]", 3)
r('    ) -> list[dict]:\n        """Lexical', '    ) -> list[dict[str, object]]:\n        """Lexical')
r("        params: list[Any] = [ts_query]", "        params: list[object] = [ts_query]")
r('    ) -> dict:\n        """Create a new conversation record."""', '    ) -> dict[str, object]:\n        """Create a new conversation record."""')
r("            return dict(row) if row else {}", "            return record_dict(row) if row else {}")
r('    ) -> list[dict]:\n        """List conversations', '    ) -> list[dict[str, object]]:\n        """List conversations')
r("    ) -> tuple[dict | None, list[dict]]:", "    ) -> tuple[dict[str, object] | None, list[dict[str, object]]]:")
r("            return dict(conv_row), [dict(r) for r in msg_rows]", "            return record_dict(conv_row), [record_dict(r) for r in msg_rows]")
r('    ) -> list[dict] | None:\n        """Last', '    ) -> list[dict[str, str]] | None:\n        """Last')
r(
    """            owned = await conn.fetchval(
                "SELECT 1 FROM agent_conversations WHERE id = $1 AND user_id = $2;",
                conversation_id,
                user_id,
            )""",
    """            owned = cast(
                int | None,
                await conn.fetchval(
                    "SELECT 1 FROM agent_conversations WHERE id = $1 AND user_id = $2;",
                    conversation_id,
                    user_id,
                ),
            )""",
)
r(
    "        plan_trace: Any = None,\n        reflection_summary: Any = None,",
    "        plan_trace: object = None,\n        reflection_summary: object = None,",
)
r(
    """            await conn.execute(
                insert, uuid4()""",
    """            _ = await conn.execute(
                insert, uuid4()""",
)
r(
    """            await conn.execute(
                insert,
                uuid4(),""",
    """            _ = await conn.execute(
                insert,
                uuid4(),""",
)
r(
    """            await conn.execute(
                "UPDATE agent_conversations""",
    """            _ = await conn.execute(
                "UPDATE agent_conversations""",
)
open(p, "w", encoding="utf-8", newline="").write(s.replace(chr(10), chr(13) + chr(10)) if crlf else s)
print("ok")

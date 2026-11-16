"""Tool audit logger: append-only rows in Postgres ``tool_audit_logs``."""

import json
import logging
from uuid import UUID, uuid4

from asyncpg import Record

from app.db.neon import NeonDatabase, neon_db
from app.db.records import col_opt_datetime, record_dict

logger = logging.getLogger("nexusagent.core.audit")

INSERT_QUERY = """
    INSERT INTO tool_audit_logs (
        id, conversation_id, user_id, tool_name, mcp_server,
        input_args, output_summary, duration_ms
    ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8);
"""

SELECT_COLUMNS = """
    id, conversation_id, user_id, tool_name, mcp_server,
    input_args, output_summary, duration_ms, executed_at
"""


def _row_to_entry(r: Record) -> dict[str, object]:
    row = record_dict(r)
    user_id = row["user_id"]
    conversation_id = row["conversation_id"]
    executed_at = col_opt_datetime(r, "executed_at")
    return {
        "id": str(row["id"]),
        "tool_name": row["tool_name"],
        "mcp_server": row["mcp_server"],
        "input_args": row["input_args"],
        "output_summary": row["output_summary"],
        "duration_ms": row["duration_ms"],
        "user_id": str(user_id) if user_id else None,
        "conversation_id": str(conversation_id) if conversation_id else None,
        "executed_at": executed_at.isoformat() if executed_at else None,
    }


class ToolAuditLogger:
    """Writes and reads tool audit rows. Audit failures never break the request."""

    def __init__(self, db: NeonDatabase | None = None):
        self.db: NeonDatabase = db or neon_db

    async def log_tool_audit(
        self,
        tool_name: str,
        input_args: dict[str, object],
        output_summary: dict[str, object] | None,
        duration_ms: int,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        mcp_server: str = "nexusagent-internal",
    ) -> UUID | None:
        """Insert one audit row (retrying once). Returns the record id, or None if not stored."""
        if not self.db.pool:
            logger.error("Audit record for %s dropped: database not connected", tool_name)
            return None

        record_id = uuid4()
        for attempt in (1, 2):
            try:
                async with self.db.pool.acquire() as conn:
                    _ = await conn.execute(
                        INSERT_QUERY,
                        record_id,
                        conversation_id,
                        user_id,
                        tool_name,
                        mcp_server,
                        json.dumps(input_args, default=str),
                        json.dumps(output_summary or {}, default=str),
                        duration_ms,
                    )
                return record_id
            except Exception as exc:  # noqa: BLE001
                level = logging.WARNING if attempt == 1 else logging.ERROR
                logger.log(level, "tool_audit_logs write failed (attempt %d): %s", attempt, exc)
        return None

    async def fetch_audit_logs_from_db(
        self, user_id: UUID | None = None, limit: int = 50
    ) -> list[dict[str, object]]:
        """Read persisted audit rows from ``tool_audit_logs`` (newest first)."""
        if user_id is not None:
            query = (
                f"SELECT {SELECT_COLUMNS} FROM tool_audit_logs "
                + "WHERE user_id = $1 ORDER BY executed_at DESC LIMIT $2;"
            )
            rows = await self.db.fetch(query, user_id, limit)
        else:
            query = (
                f"SELECT {SELECT_COLUMNS} FROM tool_audit_logs ORDER BY executed_at DESC LIMIT $1;"
            )
            rows = await self.db.fetch(query, limit)
        return [_row_to_entry(r) for r in rows]


default_audit_logger = ToolAuditLogger()

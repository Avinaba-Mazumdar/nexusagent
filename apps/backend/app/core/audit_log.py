"""Immutable tool audit logger: Postgres tool_audit_logs with an in-memory ring-buffer fallback."""

import json
import logging
from collections import deque
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.db.neon import NeonDatabase, neon_db

logger = logging.getLogger("nexusagent.core.audit")


class ToolAuditLogger:
    """Manages immutable tool audit logs."""

    def __init__(self, db: NeonDatabase | None = None):
        self.db = db or neon_db
        # Thread-safe in-memory ring-buffer for audit logs (capped at 500)
        self._memory_audit_logs: deque[dict[str, Any]] = deque(maxlen=500)

    async def log_tool_audit(
        self,
        tool_name: str,
        input_args: dict[str, Any],
        output_summary: dict[str, Any] | None,
        duration_ms: int,
        hitl_approved: bool = True,
        user_id: UUID | None = None,
        conversation_id: UUID | None = None,
        mcp_server: str = "nexusagent-internal",
    ) -> dict[str, Any]:
        """
        Record immutable audit entry in Postgres and local memory ring-buffer.
        """
        record_id = uuid4()
        now = datetime.now(UTC)

        entry = {
            "id": str(record_id),
            "tool_name": tool_name,
            "mcp_server": mcp_server,
            "input_args": input_args,
            "output_summary": output_summary or {},
            "duration_ms": duration_ms,
            "hitl_approved": hitl_approved,
            "user_id": str(user_id) if user_id else None,
            "conversation_id": str(conversation_id) if conversation_id else None,
            "executed_at": now.isoformat(),
        }

        # 1. Store in memory ring-buffer
        self._memory_audit_logs.appendleft(entry)

        # 2. Persist to Neon Postgres if connected. Audit rows are security-relevant:
        # retry once before degrading to the in-memory ring so a transient Neon hiccup
        # does not silently drop them.
        if self.db and self.db.pool:
            query = """
                INSERT INTO tool_audit_logs (
                    id, conversation_id, user_id, tool_name, mcp_server,
                    input_args, output_summary, duration_ms, hitl_approved, executed_at
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8, $9, $10);
            """
            for attempt in (1, 2):
                try:
                    async with self.db.pool.acquire() as conn:
                        await conn.execute(
                            query,
                            record_id,
                            conversation_id,
                            user_id,
                            tool_name,
                            mcp_server,
                            json.dumps(input_args, default=str),
                            json.dumps(output_summary or {}, default=str),
                            duration_ms,
                            hitl_approved,
                            now,
                        )
                    break
                except Exception as exc:  # noqa: BLE001
                    if attempt == 1:
                        logger.error(f"tool_audit_logs write failed, retrying once: {exc}")
                    else:
                        logger.error(
                            f"Audit record {record_id} kept in memory ring only "
                            f"(Neon write failed twice): {exc}"
                        )

        return entry

    def get_recent_audit_logs(
        self, user_id: UUID | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """Retrieve recent tool audit logs from memory ring-buffer, optionally filtered by user."""
        if user_id is not None:
            uid_str = str(user_id)
            entries = [e for e in self._memory_audit_logs if e.get("user_id") == uid_str]
            return entries[:limit]
        return list(self._memory_audit_logs)[:limit]

    async def fetch_audit_logs_from_db(
        self, user_id: UUID | None = None, limit: int = 50
    ) -> list[dict[str, Any]]:
        """
        Read persisted audit rows from Neon ``tool_audit_logs`` (newest first).
        Falls back to the in-memory ring when the database is unavailable.
        """
        if self.db and self.db.pool:
            try:
                if user_id is not None:
                    query = """
                        SELECT id, conversation_id, user_id, tool_name, mcp_server,
                               input_args, output_summary, duration_ms, hitl_approved, executed_at
                        FROM tool_audit_logs
                        WHERE user_id = $1
                        ORDER BY executed_at DESC
                        LIMIT $2;
                    """
                    rows = await self.db.fetch(query, user_id, limit)
                else:
                    query = """
                        SELECT id, conversation_id, user_id, tool_name, mcp_server,
                               input_args, output_summary, duration_ms, hitl_approved, executed_at
                        FROM tool_audit_logs
                        ORDER BY executed_at DESC
                        LIMIT $1;
                    """
                    rows = await self.db.fetch(query, limit)
                return [
                    {
                        "id": str(r["id"]),
                        "tool_name": r["tool_name"],
                        "mcp_server": r["mcp_server"],
                        "input_args": r["input_args"],
                        "output_summary": r["output_summary"],
                        "duration_ms": r["duration_ms"],
                        "hitl_approved": r["hitl_approved"],
                        "user_id": str(r["user_id"]) if r["user_id"] else None,
                        "conversation_id": (
                            str(r["conversation_id"]) if r["conversation_id"] else None
                        ),
                        "executed_at": r["executed_at"].isoformat() if r["executed_at"] else None,
                    }
                    for r in rows
                ]
            except Exception as exc:  # noqa: BLE001
                logger.error(f"Failed to read tool_audit_logs from Neon; using memory ring: {exc}")
        return self.get_recent_audit_logs(user_id=user_id, limit=limit)


default_audit_logger = ToolAuditLogger()
# Backwards compatibility aliases
HitlCoordinator = ToolAuditLogger
default_hitl_coordinator = default_audit_logger

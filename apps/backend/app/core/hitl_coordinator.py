"""
Human-in-the-Loop (HITL) Approval Coordinator & Immutable Tool Audit Logger.
Coordinates interactive operator authorization for sensitive operations and records
unalterable audit trails into Postgres `tool_audit_logs` with memory ring-buffer fallback.
"""

import asyncio
import json
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.config import settings
from app.db.neon import NeonDatabase, neon_db

logger = logging.getLogger("nexusagent.core.hitl")


@dataclass
class PendingApproval:
    approval_id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    risk_level: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    event: asyncio.Event = field(default_factory=asyncio.Event)
    decision: str | None = None  # "approve" | "reject"
    resolved_by: str | None = None


class HitlCoordinator:
    """Manages asynchronous human approval requests and immutable audit logs."""

    def __init__(self, db: NeonDatabase | None = None):
        self.db = db or neon_db
        self._pending_approvals: dict[str, PendingApproval] = {}
        self._notifiers: dict[str, Callable[[dict[str, Any]], Awaitable[None]]] = {}
        # Thread-safe in-memory ring-buffer for audit logs (capped at 500)
        self._memory_audit_logs: deque[dict[str, Any]] = deque(maxlen=500)

    def is_approval_required(self, tool_name: str, arguments: dict[str, Any]) -> tuple[bool, str]:
        """
        Evaluate security policy for tool execution.
        Returns (requires_approval, risk_level).
        """
        # Database SQL queries with schema inspection require approval
        if tool_name == "mcp_sql_audit":
            query = arguments.get("query", "").lower()
            if "pg_" in query or "information_schema" in query:
                return True, "high"

        return False, "low"

    async def request_approval(
        self,
        session_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        risk_level: str = "medium",
        timeout_seconds: float = settings.HITL_APPROVAL_TIMEOUT_SECONDS,
    ) -> tuple[bool, str]:
        """
        Suspend execution until an operator approves/rejects the action or timeout occurs.
        Returns (is_approved, approval_id).
        """
        approval_id = f"hitl-{uuid4().hex[:8]}"
        pending = PendingApproval(
            approval_id=approval_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=arguments,
            risk_level=risk_level,
        )
        self._pending_approvals[approval_id] = pending

        logger.info(
            f"HITL approval required: id={approval_id} tool={tool_name} session={session_id} risk={risk_level}"
        )

        notifier = self._notifiers.get(session_id)
        if notifier:
            try:
                await notifier(
                    {
                        "approvalId": approval_id,
                        "sessionId": session_id,
                        "tool": tool_name,
                        "arguments": arguments,
                        "riskLevel": risk_level,
                        "timeoutSeconds": int(timeout_seconds),
                    }
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Error invoking approval notifier: {e}")

        try:
            await asyncio.wait_for(pending.event.wait(), timeout=timeout_seconds)
            is_approved = pending.decision == "approve"
            logger.info(f"HITL approval resolved: id={approval_id} decision={pending.decision}")
            return is_approved, approval_id
        except TimeoutError:
            logger.warning(f"HITL approval timed out after {timeout_seconds}s for id={approval_id}")
            pending.decision = "reject"
            return False, approval_id
        finally:
            self._pending_approvals.pop(approval_id, None)

    def register_notifier(
        self, session_id: str, callback: Callable[[dict[str, Any]], Awaitable[None]]
    ) -> None:
        """Register a notification callback for a session."""
        self._notifiers[session_id] = callback

    def unregister_notifier(self, session_id: str) -> None:
        """Unregister a notification callback for a session."""
        self._notifiers.pop(session_id, None)

    def resolve_approval(
        self,
        approval_id: str,
        decision: str,
        resolved_by: str = "operator",
        session_id: str | None = None,
    ) -> bool:
        """
        Resolve a pending approval with 'approve' or 'reject'.

        When ``session_id`` is provided it must match the approval's owning
        session; this prevents cross-session approval tampering.
        """
        pending = self._pending_approvals.get(approval_id)
        if not pending:
            logger.warning(f"Approval ID '{approval_id}' not found or already completed.")
            return False
        if session_id is not None and pending.session_id != session_id:
            logger.warning(
                f"Approval '{approval_id}' session mismatch: expected "
                f"{pending.session_id}, got {session_id}."
            )
            return False

        pending.decision = "approve" if decision.lower() == "approve" else "reject"
        pending.resolved_by = resolved_by
        pending.event.set()
        return True

    def get_pending_approvals(self) -> list[dict[str, Any]]:
        """List currently pending approvals."""
        return [
            {
                "approvalId": p.approval_id,
                "sessionId": p.session_id,
                "tool": p.tool_name,
                "arguments": p.arguments,
                "riskLevel": p.risk_level,
                "createdAt": p.created_at.isoformat(),
            }
            for p in self._pending_approvals.values()
        ]

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

    def get_recent_audit_logs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retrieve recent tool audit logs from memory ring-buffer."""
        return list(self._memory_audit_logs)[:limit]

    async def fetch_audit_logs_from_db(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Read persisted audit rows from Neon ``tool_audit_logs`` (newest first).
        Falls back to the in-memory ring when the database is unavailable.
        """
        if self.db and self.db.pool:
            try:
                rows = await self.db.fetch(
                    """
                    SELECT id, conversation_id, user_id, tool_name, mcp_server,
                           input_args, output_summary, duration_ms, hitl_approved, executed_at
                    FROM tool_audit_logs
                    ORDER BY executed_at DESC
                    LIMIT $1;
                    """,
                    limit,
                )
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
        return self.get_recent_audit_logs(limit=limit)


default_hitl_coordinator = HitlCoordinator()

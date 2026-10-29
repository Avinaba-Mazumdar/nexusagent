"""
Token-Bucket Rate Limiter.
Enforces hourly token limits per user (bucket state lives in Neon PostgreSQL):
- Guest users: 5 requests / hour
- Authenticated registered users: 25 requests / hour
Guests are additionally capped per IP by in-process sliding-window counters.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.db.neon import NeonDatabase, neon_db

logger = logging.getLogger("nexusagent.core.rate_limiter")

MAX_TRACKED_KEYS = 50_000


class SlidingWindowCounter:
    """Per-key event counter over a rolling window (per process, bounded memory)."""

    def __init__(self, limit: int, window: timedelta = timedelta(hours=1)):
        self.limit = limit
        self.window = window
        self._events: dict[str, list[datetime]] = {}

    def _prune_stale_keys(self, now: datetime) -> None:
        self._events = {
            key: events
            for key, events in self._events.items()
            if events and now - events[-1] < self.window
        }

    def hit(self, key: str) -> bool:
        """Record an event; return False (and record nothing) when the key is over its limit."""
        now = datetime.now(UTC)
        recent = [t for t in self._events.get(key, []) if now - t < self.window]
        allowed = len(recent) < self.limit
        if allowed:
            recent.append(now)
        self._events[key] = recent
        if len(self._events) > MAX_TRACKED_KEYS:
            self._prune_stale_keys(now)
        return allowed

    def reset_for_test(self) -> None:
        self._events.clear()


guest_signup_limiter = SlidingWindowCounter(limit=settings.GUEST_SIGNUPS_PER_IP_PER_HOUR)
guest_ip_llm_limiter = SlidingWindowCounter(limit=settings.GUEST_IP_QUOTA_PER_HOUR)


def _quota_exhausted() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Free-tier quota limit reached. It replenishes hourly.",
        headers={"Retry-After": "3600"},
    )


class TokenBucketLimiter:
    """Async token-bucket rate limiter backed by the ``rate_limit_buckets`` table."""

    def __init__(self, db: NeonDatabase):
        self.db = db

    @staticmethod
    def _capacity(is_guest: bool) -> int:
        return settings.GUEST_QUOTA_DEFAULT if is_guest else settings.USER_QUOTA_DEFAULT

    async def check_and_consume(
        self,
        user_id: UUID,
        client_ip: str,
        is_guest: bool = True,
        cost: int = 1,
    ) -> int:
        """
        Check and consume tokens (default: 1).
        Returns tokens_remaining after decrement.
        Raises HTTPException(429) if quota is depleted or insufficient.
        """
        if is_guest and not guest_ip_llm_limiter.hit(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many guest requests from this network. Try again later.",
                headers={"Retry-After": "3600"},
            )

        remaining = await self.db.consume_rate_limit(
            user_id, default_tokens=self._capacity(is_guest), cost=cost
        )
        if remaining is None:
            raise _quota_exhausted()
        return remaining

    async def get_quota(self, user_id: UUID, is_guest: bool = True) -> int:
        """Fetch current quota without consuming."""
        row = await self.db.get_or_create_rate_limit(
            user_id, default_tokens=self._capacity(is_guest)
        )
        return row.tokens_remaining

    async def refund(self, user_id: UUID, is_guest: bool = True) -> None:
        """Refund 1 token (capped at capacity) after a failed run. Best effort."""
        try:
            await self.db.refund_rate_limit(user_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Database rate limit refund failed: {e}")

    def reset_for_test(self) -> None:
        """Clear in-process counters for test isolation."""
        guest_signup_limiter.reset_for_test()
        guest_ip_llm_limiter.reset_for_test()


default_rate_limiter = TokenBucketLimiter(db=neon_db)

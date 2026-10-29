"""
Token-Bucket Rate Limiter.
Enforces hourly token limits per user/IP:
- Guest users: 5 requests / hour
- Authenticated registered users: 25 requests / hour
Operates on Neon PostgreSQL with resilient in-memory fallback when offline.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.db.neon import NeonDatabase, neon_db

logger = logging.getLogger("nexusagent.core.rate_limiter")


@dataclass
class MemoryBucket:
    user_id: str
    client_ip: str
    tokens_remaining: int
    bucket_capacity: int
    last_replenished_at: datetime


class SlidingWindowCounter:
    """Per-key event counter over a rolling window (per process)."""

    def __init__(self, limit: int, window: timedelta = timedelta(hours=1)):
        self.limit = limit
        self.window = window
        self._events: dict[str, list[datetime]] = {}

    def hit(self, key: str) -> bool:
        """Record an event; return False (and record nothing) when the key is over its limit."""
        now = datetime.now(UTC)
        recent = [t for t in self._events.get(key, []) if now - t < self.window]
        if len(recent) >= self.limit:
            self._events[key] = recent
            return False
        recent.append(now)
        self._events[key] = recent
        return True

    def reset_for_test(self) -> None:
        self._events.clear()


guest_signup_limiter = SlidingWindowCounter(limit=settings.GUEST_SIGNUPS_PER_IP_PER_HOUR)
guest_ip_llm_limiter = SlidingWindowCounter(limit=settings.GUEST_IP_QUOTA_PER_HOUR)


class TokenBucketLimiter:
    """Thread-safe / async token-bucket rate limiter with database & memory tiers."""

    def __init__(self, db: NeonDatabase | None = None):
        self.db = db
        # In-memory store keyed by (str(user_id), client_ip)
        self._memory_buckets: dict[tuple[str, str], MemoryBucket] = {}

    def _get_memory_bucket(
        self, user_id: UUID | str, client_ip: str, default_tokens: int
    ) -> MemoryBucket:
        key = (str(user_id), client_ip)
        now = datetime.now(UTC)
        bucket = self._memory_buckets.get(key)

        if not bucket:
            bucket = MemoryBucket(
                user_id=str(user_id),
                client_ip=client_ip,
                tokens_remaining=default_tokens,
                bucket_capacity=default_tokens,
                last_replenished_at=now,
            )
            self._memory_buckets[key] = bucket
            if len(self._memory_buckets) > 10_000:
                cutoff = now - timedelta(hours=2)
                self._memory_buckets = {
                    k: v for k, v in self._memory_buckets.items() if v.last_replenished_at > cutoff
                }
            return bucket

        # Check hourly replenishment
        if (now - bucket.last_replenished_at) >= timedelta(hours=1):
            bucket.tokens_remaining = bucket.bucket_capacity
            bucket.last_replenished_at = now

        return bucket

    async def check_and_consume(
        self,
        user_id: UUID,
        client_ip: str,
        is_guest: bool = True,
    ) -> int:
        """
        Check and consume 1 token.
        Returns tokens_remaining after decrement.
        Raises HTTPException(429) if quota is depleted.
        """
        if is_guest and not guest_ip_llm_limiter.hit(client_ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many guest requests from this network. Try again later.",
                headers={"Retry-After": "3600"},
            )

        default_tokens = (
            settings.GUEST_QUOTA_DEFAULT if is_guest else settings.USER_QUOTA_DEFAULT
        )

        # 1. Try PostgreSQL if pool is available
        if self.db and self.db.pool:
            try:
                await self.db.get_or_create_rate_limit(
                    user_id, client_ip, default_tokens=default_tokens
                )
                remaining = await self.db.decrement_rate_limit(user_id, client_ip)
                if remaining is None:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail="Free-tier quota limit reached. It replenishes hourly.",
                        headers={"Retry-After": "3600"},
                    )
                return remaining
            except HTTPException:
                raise
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Database rate limit query failed, falling back to memory bucket: {e}"
                )

        # 2. Resilient In-Memory Fallback
        bucket = self._get_memory_bucket(user_id, client_ip, default_tokens)
        if bucket.tokens_remaining <= 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Free-tier quota limit reached. It replenishes hourly.",
                headers={"Retry-After": "3600"},
            )

        bucket.tokens_remaining -= 1
        return bucket.tokens_remaining

    async def get_quota(
        self,
        user_id: UUID,
        client_ip: str,
        is_guest: bool = True,
    ) -> int:
        """Fetch current quota without consuming."""
        default_tokens = (
            settings.GUEST_QUOTA_DEFAULT if is_guest else settings.USER_QUOTA_DEFAULT
        )

        if self.db and self.db.pool:
            try:
                row = await self.db.get_or_create_rate_limit(
                    user_id, client_ip, default_tokens=default_tokens
                )
                return row.tokens_remaining
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    f"Database rate limit query failed, falling back to memory bucket: {e}"
                )

        bucket = self._get_memory_bucket(user_id, client_ip, default_tokens)
        return bucket.tokens_remaining

    async def refund(
        self,
        user_id: UUID,
        client_ip: str,
        is_guest: bool = True,
    ) -> None:
        """Refund 1 token (capped at capacity) after a failed run."""
        if self.db and self.db.pool:
            try:
                await self.db.refund_rate_limit(user_id, client_ip)
                return
            except Exception as e:  # noqa: BLE001
                logger.warning(f"Database rate limit refund failed: {e}")

        key = (str(user_id), client_ip)
        bucket = self._memory_buckets.get(key)
        if bucket:
            bucket.tokens_remaining = min(bucket.bucket_capacity, bucket.tokens_remaining + 1)

    def reset_for_test(self) -> None:
        """Clear memory cache for test isolation."""
        self._memory_buckets.clear()
        guest_signup_limiter.reset_for_test()
        guest_ip_llm_limiter.reset_for_test()


default_rate_limiter = TokenBucketLimiter(db=neon_db)

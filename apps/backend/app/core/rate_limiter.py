"""
Rolling 24-hour window chat quota.
Enforces rolling 24-hour limits:
- Guest users: 5 chats / 24 hours, keyed by user_id + device_id + machine_hash + client_ip
- Google accounts: 25 chats / 24 hours, keyed by user_id only
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.db.models import User
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
google_auth_limiter = SlidingWindowCounter(limit=settings.GOOGLE_AUTH_PER_IP_PER_HOUR)
refresh_limiter = SlidingWindowCounter(limit=settings.REFRESH_PER_IP_PER_HOUR)


def enforce_ip_limit(counter: SlidingWindowCounter, client_ip: str) -> None:
    """Raise 429 when ``client_ip`` has exceeded ``counter``'s hourly allowance."""
    if not counter.hit(client_ip):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests from this network. Try again later.",
            headers={"Retry-After": "3600"},
        )


class ChatQuota:
    """Rolling 24-hour window chat quota limiter backed by the ``chat_usage`` table."""

    def __init__(self, db: NeonDatabase):
        self.db = db

    def limit_for(self, user: User) -> int:
        return settings.GUEST_QUOTA_DEFAULT if user.is_guest else settings.USER_QUOTA_DEFAULT

    def _keys(self, user: User, client_ip: str | None) -> tuple[str | None, str | None, str | None]:
        if user.is_guest:
            return (user.device_id, user.machine_hash, client_ip)
        return (None, None, None)

    async def reserve(self, user: User, client_ip: str | None = None) -> tuple[UUID, int]:
        device_hash, machine_hash, ip = self._keys(user, client_ip)
        limit = self.limit_for(user)
        usage_id, remaining, oldest = await self.db.reserve_chat(
            user_id=user.id,
            device_hash=device_hash,
            machine_hash=machine_hash,
            client_ip=ip,
            limit=limit,
        )
        if usage_id is None:
            now = datetime.now(UTC)
            resets_at = (oldest + timedelta(hours=24)) if oldest else (now + timedelta(hours=24))
            retry_after = max(1, int((resets_at - now).total_seconds()))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily chat limit reached (5 per 24 hours for guests, 25 for Google accounts).",
                headers={"Retry-After": str(retry_after)},
            )
        return usage_id, remaining

    async def status(self, user: User, client_ip: str | None = None) -> tuple[int, datetime]:
        device_hash, machine_hash, ip = self._keys(user, client_ip)
        limit = self.limit_for(user)
        used, oldest = await self.db.count_chats(
            user_id=user.id,
            device_hash=device_hash,
            machine_hash=machine_hash,
            client_ip=ip,
        )
        now = datetime.now(UTC)
        resets_at = (oldest + timedelta(hours=24)) if oldest else (now + timedelta(hours=24))
        remaining = max(0, limit - used)
        return remaining, resets_at

    async def refund(self, usage_id: UUID | None) -> None:
        """Best-effort release_chat. Log and swallow errors."""
        if not usage_id:
            return
        try:
            await self.db.release_chat(usage_id)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Database chat refund failed: {e}")

    def reset_for_test(self) -> None:
        guest_signup_limiter.reset_for_test()
        google_auth_limiter.reset_for_test()
        refresh_limiter.reset_for_test()


default_chat_quota = ChatQuota(db=neon_db)

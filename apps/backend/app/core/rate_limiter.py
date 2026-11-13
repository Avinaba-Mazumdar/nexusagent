"""
Rolling 24-hour chat quota. The buckets are described in ``app.core.quota_policy``:
- Guests: 5 per account and device cookie, 20 per client network, and a service-wide guest ceiling.
- Google accounts: 25 per account.
- Everyone: a service-wide ceiling on all chats.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException, status

from app.config import settings
from app.core.quota_policy import Bucket, QuotaDecision, QuotaLimits
from app.core.security_events import security_event
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
mcp_embedding_budget = SlidingWindowCounter(
    limit=settings.MCP_EMBEDDINGS_PER_DAY, window=timedelta(days=1)
)
google_auth_limiter = SlidingWindowCounter(limit=settings.GOOGLE_AUTH_PER_IP_PER_HOUR)
refresh_limiter = SlidingWindowCounter(limit=settings.REFRESH_PER_IP_PER_HOUR)
# A refused question is refunded, but only this many times per user per hour.
FREE_REFUSALS_PER_USER_PER_HOUR = 10
refusal_refund_limiter = SlidingWindowCounter(limit=FREE_REFUSALS_PER_USER_PER_HOUR)


def enforce_ip_limit(counter: SlidingWindowCounter, client_ip: str) -> None:
    """Raise 429 when ``client_ip`` has exceeded ``counter``'s hourly allowance."""
    if not counter.hit(client_ip):
        security_event("quota.exceeded", ip=client_ip, kind="ip")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests from this network. Try again later.",
            headers={"Retry-After": "3600"},
        )


# Names the full bucket on a 429 so the web app can tell a guest's own limit from a shared one.
QUOTA_SCOPE_HEADER = "X-Quota-Scope"

BLOCKED_DETAIL: dict[Bucket, str] = {
    "user": "Daily chat limit reached (5 per 24 hours for guests, 25 for Google accounts).",
    "network": (
        "Daily guest chat limit reached for this network. "
        "Sign in with Google to get your own quota."
    ),
    "guests": (
        "Guest chats are at today's limit for the whole service. "
        "Sign in with Google, or try again later."
    ),
    "service": "NexusAgent has reached today's chat capacity. Please try again later.",
}


def _resets_at(decision: QuotaDecision) -> datetime:
    """When the deciding bucket frees a chat: 24 hours after its oldest chat."""
    if decision.oldest is None:
        return datetime.now(UTC) + timedelta(hours=24)
    return decision.oldest + timedelta(hours=24)


class ChatQuota:
    """Rolling 24-hour window chat quota limiter backed by the ``chat_usage`` table."""

    def __init__(self, db: NeonDatabase):
        self.db = db

    def limit_for(self, user: User) -> int:
        return settings.GUEST_QUOTA_DEFAULT if user.is_guest else settings.USER_QUOTA_DEFAULT

    def limits_for(self, user: User) -> QuotaLimits:
        """Every bucket that applies to ``user``. A ceiling set to 0 is switched off."""
        service = settings.CHATS_PER_DAY or None
        if not user.is_guest:
            return QuotaLimits(per_user=settings.USER_QUOTA_DEFAULT, all_per_day=service)
        return QuotaLimits(
            per_user=settings.GUEST_QUOTA_DEFAULT,
            per_network=settings.GUEST_QUOTA_PER_NETWORK or None,
            guests_per_day=settings.GUEST_CHATS_PER_DAY or None,
            all_per_day=service,
        )

    def _keys(self, user: User, client_ip: str | None) -> tuple[str | None, str | None]:
        """Device cookie hash and client network, for guests only. The fingerprint is not a key."""
        if user.is_guest:
            return (user.device_id, client_ip)
        return (None, None)

    async def reserve(self, user: User, client_ip: str | None = None) -> tuple[UUID, int]:
        device_hash, ip = self._keys(user, client_ip)
        usage_id, decision = await self.db.reserve_chat(
            user_id=user.id,
            device_hash=device_hash,
            client_ip=ip,
            limits=self.limits_for(user),
        )
        if usage_id is None:
            raise self._blocked(decision, client_ip)
        return usage_id, decision.remaining

    async def status(self, user: User, client_ip: str | None = None) -> tuple[int, datetime]:
        device_hash, ip = self._keys(user, client_ip)
        decision = await self.db.count_chats(
            user_id=user.id,
            device_hash=device_hash,
            client_ip=ip,
            limits=self.limits_for(user),
        )
        return decision.remaining, _resets_at(decision)

    @staticmethod
    def _blocked(decision: QuotaDecision, client_ip: str | None) -> HTTPException:
        bucket: Bucket = decision.blocked_by or "user"
        if bucket in ("guests", "service"):
            # One shared key, so a burst from many clients still raises a single alert.
            security_event(
                "quota.exceeded", ip="service-wide", kind=f"chat_{bucket}", client=client_ip
            )
        else:
            security_event("quota.exceeded", ip=client_ip or "unknown", kind=f"chat_{bucket}")
        retry_after = max(1, int((_resets_at(decision) - datetime.now(UTC)).total_seconds()))
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=BLOCKED_DETAIL[bucket],
            headers={"Retry-After": str(retry_after), QUOTA_SCOPE_HEADER: bucket},
        )

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
        refusal_refund_limiter.reset_for_test()


default_chat_quota = ChatQuota(db=neon_db)

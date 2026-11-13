"""Chat quota buckets and the decision over them. Pure functions: no database, no settings.

A chat is allowed only when every bucket that applies has room:

- user: the account, plus (for guests) the HttpOnly device cookie. 5 for guests, 25 for Google.
- network: guest chats from one client network (an IPv4 address or an IPv6 /64). Shared by
  everyone behind that network, so it is larger than the per-guest bucket.
- guests: guest chats across the whole service per rolling day.
- service: all chats across the whole service per rolling day.

The browser fingerprint is not a bucket. It is client-supplied and collides across identical
devices, so counting it let one client use up other people's quota.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

Bucket = Literal["user", "network", "guests", "service"]


@dataclass(frozen=True)
class QuotaLimits:
    per_user: int
    # None means the bucket does not apply (Google accounts) or is switched off.
    per_network: int | None = None
    guests_per_day: int | None = None
    all_per_day: int | None = None


@dataclass(frozen=True)
class UsageCounts:
    """Chats in the last 24 hours, per bucket, with the oldest chat in each."""

    user: int = 0
    user_oldest: datetime | None = None
    network: int = 0
    network_oldest: datetime | None = None
    guests: int = 0
    guests_oldest: datetime | None = None
    total: int = 0
    total_oldest: datetime | None = None


@dataclass(frozen=True)
class QuotaDecision:
    remaining: int
    """Chats left in the tightest bucket."""
    blocked_by: Bucket | None
    """The first full bucket, or None when a chat is allowed."""
    oldest: datetime | None
    """Oldest chat in the deciding bucket. A chat frees up 24 hours after it."""


def decide(counts: UsageCounts, limits: QuotaLimits) -> QuotaDecision:
    """Evaluate every applicable bucket. The first full one blocks; otherwise the tightest one decides."""
    buckets: list[tuple[Bucket, int, int, datetime | None]] = [
        ("user", counts.user, limits.per_user, counts.user_oldest)
    ]
    if limits.per_network is not None:
        buckets.append(("network", counts.network, limits.per_network, counts.network_oldest))
    if limits.guests_per_day is not None:
        buckets.append(("guests", counts.guests, limits.guests_per_day, counts.guests_oldest))
    if limits.all_per_day is not None:
        buckets.append(("service", counts.total, limits.all_per_day, counts.total_oldest))

    for name, used, limit, oldest in buckets:
        if used >= limit:
            return QuotaDecision(remaining=0, blocked_by=name, oldest=oldest)

    _name, used, limit, oldest = min(buckets, key=lambda b: b[2] - b[1])
    return QuotaDecision(remaining=limit - used, blocked_by=None, oldest=oldest)


def after_reserving(decision: QuotaDecision, now: datetime) -> QuotaDecision:
    """The decision once the allowed chat is recorded: one fewer left, and a window that has started."""
    return replace(decision, remaining=decision.remaining - 1, oldest=decision.oldest or now)

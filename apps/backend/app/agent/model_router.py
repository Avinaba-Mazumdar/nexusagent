"""
Route answer generation across the configured Gemini models (``settings.GEMINI_MODELS``).

The free tier gives each model its own requests-per-minute and requests-per-day quota, so when
one model returns 429 the next one usually still has capacity. The router remembers which models
are exhausted and until when, so later requests skip them instead of paying for another 429:

- per-minute limits: cool down for the ``retryDelay`` Google returns (60 s if it sends none);
- per-day limits: cool down until the quota resets at midnight Pacific time;
- unknown or inaccessible models (404/403): skip for a day.

State is per process; the API runs as a single worker (see README).
"""

import json
import logging
import re
import time
from collections.abc import Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

logger = logging.getLogger("nexusagent.agent.model_router")

PACIFIC = ZoneInfo("America/Los_Angeles")
DEFAULT_COOLDOWN_SECONDS = 60.0
UNAVAILABLE_COOLDOWN_SECONDS = 24 * 3600.0

_RETRY_DELAY = re.compile(r"""['"]retryDelay['"]\s*:\s*['"](\d+(?:\.\d+)?)s['"]""")
_RETRY_IN = re.compile(r"retry in (\d+(?:\.\d+)?)\s*s", re.IGNORECASE)


def _error_text(exc: BaseException) -> str:
    """Flatten the exception chain, including the Google error body, into one string."""
    parts: list[str] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        parts.append(str(current))
        details = getattr(current, "details", None)
        if details:
            parts.append(json.dumps(details, default=str))
        current = current.__cause__ or current.__context__
    return "\n".join(parts)


def seconds_until_pacific_midnight(now: float) -> float:
    local = datetime.fromtimestamp(now, PACIFIC)
    midnight = (local + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(midnight.timestamp() - now, 1.0)


def rate_limit_cooldown(exc: BaseException, now: float) -> float:
    """Seconds to skip a model after a 429: until the daily reset, or the advised retry delay."""
    text = _error_text(exc)
    if "PerDay" in text:
        return seconds_until_pacific_midnight(now)
    match = _RETRY_DELAY.search(text) or _RETRY_IN.search(text)
    return float(match.group(1)) if match else DEFAULT_COOLDOWN_SECONDS


class ModelRouter:
    def __init__(self, models: list[str], clock: Callable[[], float] = time.time):
        self.models = list(models)
        self._clock = clock
        self._cooling_until: dict[str, float] = {}

    def candidates(self) -> list[str]:
        """Configured models that are not cooling down, in preference order."""
        now = self._clock()
        return [m for m in self.models if self._cooling_until.get(m, 0.0) <= now]

    def mark_rate_limited(self, model: str, exc: BaseException) -> None:
        seconds = rate_limit_cooldown(exc, self._clock())
        self._cooling_until[model] = self._clock() + seconds
        logger.warning("Gemini model %s is rate-limited; skipping it for %.0f s", model, seconds)

    def mark_unavailable(self, model: str) -> None:
        self._cooling_until[model] = self._clock() + UNAVAILABLE_COOLDOWN_SECONDS
        logger.warning("Gemini model %s is not available to this API key; skipping it", model)

    def next_available_at(self) -> float | None:
        """Unix time at which the soonest cooling model becomes usable again."""
        pending = [t for m, t in self._cooling_until.items() if m in self.models]
        return min(pending) if pending else None

    def reset(self) -> None:
        self._cooling_until.clear()

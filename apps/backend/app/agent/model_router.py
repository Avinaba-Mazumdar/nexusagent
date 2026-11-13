"""
Route answer generation across the configured Gemini and Gemma models (``settings.TEXT_MODELS``).

The free tier gives each model its own requests-per-minute and requests-per-day quota, so when
one model returns 429 the next one usually still has capacity. The router remembers which models
are exhausted and until when, so later requests skip them instead of paying for another 429:

- per-minute limits: cool down for the ``retryDelay`` Google returns (60 s if it sends none);
- per-day limits: cool down until the quota resets at midnight Pacific time;
- unknown or inaccessible models (404/403): skip for a day;
- server errors (5xx): skip for 30 s;
- timeouts: skip for 5 minutes (a hanging model would otherwise cost a full timeout every request).

Routing decisions read in-memory state only. Cooldowns are also saved to the ``model_cooldowns``
table through ``on_cooldown`` and loaded back by ``app.agent.model_health``, so they survive restarts.
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
OVERLOADED_COOLDOWN_SECONDS = 30.0
TIMEOUT_COOLDOWN_SECONDS = 300.0
# A slow first token is not a dead socket. Skip the model briefly, in this process only.
SLOW_START_COOLDOWN_SECONDS = 30.0

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


CooldownListener = Callable[[str, str, str, float, str], None]
"""``(scope, model, reason, retry_at_unix, error_text)``: called after a model is put on cooldown."""


class ModelRouter:
    def __init__(
        self,
        models: list[str],
        clock: Callable[[], float] = time.time,
        *,
        scope: str = "chat",
        on_cooldown: CooldownListener | None = None,
    ):
        self.models = list(models)
        self.scope = scope
        self.on_cooldown = on_cooldown
        self._clock = clock
        self._cooling_until: dict[str, float] = {}

    def candidates(self, prefer_lite: bool = False) -> list[str]:
        """Configured models that are not cooling down, in preference order."""
        now = self._clock()
        available = [m for m in self.models if self._cooling_until.get(m, 0.0) <= now]
        if prefer_lite:
            return sorted(available, key=lambda m: 0 if "lite" in m.lower() else 1)
        return available

    def _cool(self, model: str, seconds: float, reason: str, exc: BaseException | None) -> None:
        until = self._clock() + seconds
        self._cooling_until[model] = until
        if self.on_cooldown is not None:
            error = _error_text(exc)[:2000] if exc is not None else ""
            try:
                self.on_cooldown(self.scope, model, reason, until, error)
            except Exception:  # persistence must never break routing
                logger.exception("Could not record the cooldown for %s", model)

    def mark_rate_limited(self, model: str, exc: BaseException) -> None:
        seconds = rate_limit_cooldown(exc, self._clock())
        self._cool(model, seconds, "rate_limited", exc)
        logger.warning("Model %s is rate-limited; skipping it for %.0f s", model, seconds)

    def mark_unavailable(self, model: str, exc: BaseException | None = None) -> None:
        self._cool(model, UNAVAILABLE_COOLDOWN_SECONDS, "unavailable", exc)
        logger.warning("Model %s is not available to this API key; skipping it", model)

    def mark_overloaded(self, model: str, exc: BaseException | None = None) -> None:
        self._cool(model, OVERLOADED_COOLDOWN_SECONDS, "overloaded", exc)
        logger.warning(
            "Model %s returned a server error; skipping it for %.0f s",
            model,
            OVERLOADED_COOLDOWN_SECONDS,
        )

    def mark_timed_out(self, model: str, exc: BaseException | None = None) -> None:
        self._cool(model, TIMEOUT_COOLDOWN_SECONDS, "timed_out", exc)
        logger.warning(
            "Model %s timed out; skipping it for %.0f s",
            model,
            TIMEOUT_COOLDOWN_SECONDS,
        )

    def mark_slow(self, model: str) -> None:
        """Skip a model that missed the first-token deadline. Not written to the shared database."""
        self._cooling_until[model] = self._clock() + SLOW_START_COOLDOWN_SECONDS
        logger.warning(
            "Model %s sent nothing before the first-token deadline; skipping it for %.0f s",
            model,
            SLOW_START_COOLDOWN_SECONDS,
        )

    def load_cooldowns(self, cooling_until: dict[str, float]) -> None:
        """Merge cooldowns recorded elsewhere (the database). Never shortens a local cooldown."""
        for model, until in cooling_until.items():
            if until > self._cooling_until.get(model, 0.0):
                self._cooling_until[model] = until

    def next_available_at(self) -> float | None:
        """Unix time at which the soonest cooling model becomes usable again."""
        pending = [t for m, t in self._cooling_until.items() if m in self.models]
        return min(pending) if pending else None

    def reset(self) -> None:
        self._cooling_until.clear()

"""Structured security events. Alert when one client repeats a failure.

Log drains should alert on ``security_event=alert`` from the ``nexusagent.security`` logger.
Routine failures stay at WARNING so a single bad token does not page anyone.
"""

import logging
from datetime import UTC, datetime, timedelta

logger = logging.getLogger("nexusagent.security")

_MAX_KEYS = 10_000


class _AlertWindow:
    def __init__(self, threshold: int, window: timedelta):
        self.threshold = threshold
        self.window = window
        self._events: dict[str, list[datetime]] = {}
        self._alerted: dict[str, datetime] = {}

    def observe(self, key: str) -> bool:
        """Record one event. Return True the first time the key crosses the threshold in the window."""
        now = datetime.now(UTC)
        recent = [t for t in self._events.get(key, []) if now - t < self.window]
        recent.append(now)
        self._events[key] = recent
        if len(self._events) > _MAX_KEYS:
            self._events = {
                k: v for k, v in self._events.items() if v and now - v[-1] < self.window
            }
        if len(recent) < self.threshold:
            return False
        last = self._alerted.get(key)
        if last is not None and now - last < self.window:
            return False
        self._alerted[key] = now
        return True


# Thresholds are per client IP. One bad login is normal; a burst is the alert.
_WINDOWS = {
    "auth.failure": _AlertWindow(20, timedelta(minutes=10)),
    "quota.exceeded": _AlertWindow(8, timedelta(hours=1)),
    "injection.flagged": _AlertWindow(5, timedelta(minutes=10)),
}


def _safe(value: object) -> str:
    text = str(value).replace("\r", " ").replace("\n", " ").strip()
    return text[:120] or "-"


def security_event(event: str, **fields: object) -> None:
    """Log one security event. Repeated events from the same IP raise one ERROR alert."""
    ip = _safe(fields.get("ip", "unknown"))
    detail = " ".join(f"{key}={_safe(val)}" for key, val in fields.items())
    logger.warning("security_event=%s %s", event, detail)
    window = _WINDOWS.get(event)
    if window is not None and window.observe(ip):
        logger.error(
            "security_event=alert trigger=%s ip=%s count=%s",
            event,
            ip,
            window.threshold,
        )

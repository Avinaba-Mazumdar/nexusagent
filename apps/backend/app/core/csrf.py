"""Cross-Site Request Forgery (CSRF) protection for cookie-authenticated endpoints."""

import json

from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings
from app.core.auth import get_client_ip
from app.core.security_events import security_event

_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_BLOCKED_RESPONSE = json.dumps({"detail": "Cross-site request blocked"}).encode("utf-8")


class CsrfProtectionMiddleware:
    """Pure-ASGI CSRF middleware defending cookie-authenticated requests.

    - Acts only on mutating requests (POST, PUT, PATCH, DELETE) under /api/.
    - If Origin is present: it must match an allowed CORS origin.
    - If Origin is absent: the request must NOT carry the session cookie.
    - Otherwise returns 403 Forbidden.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in _MUTATING_METHODS
            or not scope["path"].startswith("/api/")
        ):
            await self.app(scope, receive, send)
            return

        origin: str | None = None
        cookie: str = ""
        for raw_k, raw_v in scope.get("headers", []):
            lower_k = raw_k.lower()
            if lower_k == b"origin":
                origin = raw_v.decode("latin1")
            elif lower_k == b"cookie":
                cookie = raw_v.decode("latin1")

        session_cookie_prefix = f"{settings.SESSION_COOKIE_NAME}="

        if origin is not None:
            if origin not in settings.CORS_ORIGINS:
                self._alert(scope)
                await self._reject(send)
                return
        elif session_cookie_prefix in cookie:
            self._alert(scope)
            await self._reject(send)
            return

        await self.app(scope, receive, send)

    @staticmethod
    def _alert(scope: Scope) -> None:
        security_event("auth.failure", reason="csrf", ip=get_client_ip(Request(scope)))

    @staticmethod
    async def _reject(send: Send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(_BLOCKED_RESPONSE)).encode("ascii")),
                ],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": _BLOCKED_RESPONSE,
            }
        )

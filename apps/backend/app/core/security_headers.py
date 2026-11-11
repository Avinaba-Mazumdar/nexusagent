"""Hardening headers for every API response."""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

AUTH_PATH_PREFIX = "/api/auth/"


class SecurityHeadersMiddleware:
    """Pure-ASGI middleware: ``nosniff`` and ``no-referrer`` everywhere, ``no-store`` on auth responses, optional HSTS."""

    def __init__(self, app: ASGIApp, hsts: bool = False) -> None:
        self.app = app
        self.hsts = hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        no_store = scope["path"].startswith(AUTH_PATH_PREFIX)

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["Referrer-Policy"] = "no-referrer"
                if self.hsts:
                    headers["Strict-Transport-Security"] = "max-age=31536000"
                if no_store:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)

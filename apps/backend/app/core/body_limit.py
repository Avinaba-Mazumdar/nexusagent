"""Reject oversized request bodies before FastAPI parses them (and before authentication runs)."""

import json

from starlette.status import HTTP_400_BAD_REQUEST, HTTP_413_CONTENT_TOO_LARGE
from starlette.types import ASGIApp, Message, Receive, Scope, Send

UPLOAD_PATH = "/api/documents/upload"


class _BodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Pure-ASGI middleware: the upload route gets its own limit, every other path a small one."""

    def __init__(self, app: ASGIApp, upload_limit: int, default_limit: int) -> None:
        self.app = app
        self.upload_limit = upload_limit
        self.default_limit = default_limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = self.upload_limit if scope["path"] == UPLOAD_PATH else self.default_limit

        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                size = int(declared)
            except ValueError:
                await _reject(send, HTTP_400_BAD_REQUEST, "Invalid Content-Length header")
                return
            if size < 0:
                await _reject(send, HTTP_400_BAD_REQUEST, "Invalid Content-Length header")
                return
            if size > limit:
                await _reject(send, HTTP_413_CONTENT_TOO_LARGE, "Request body too large")
                return

        received = 0
        exceeded = False
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    exceeded = True
                    raise _BodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if exceeded:
                # The framework may turn our exception into its own 400/500; the 413 below wins.
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _BodyTooLarge:
            pass
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await _reject(send, HTTP_413_CONTENT_TOO_LARGE, "Request body too large")


async def _reject(send: Send, status_code: int, detail: str) -> None:
    body = json.dumps({"detail": detail}).encode()
    await send(
        {
            "type": "http.response.start",
            "status": status_code,
            "headers": [
                (b"content-type", b"application/json"),
                (b"content-length", str(len(body)).encode()),
                (b"connection", b"close"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": body})

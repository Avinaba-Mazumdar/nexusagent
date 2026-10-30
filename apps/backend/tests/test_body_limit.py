"""R2-SEC-02: oversized bodies are rejected before multipart parsing and before authentication."""

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.formparsers import MultiPartParser

from app.main import app

UPLOAD_URL = "/api/documents/upload"
MB = 1024 * 1024


@pytest.fixture
def parse_calls(monkeypatch):
    calls: list[int] = []
    original = MultiPartParser.parse

    async def recording_parse(self):
        calls.append(1)
        return await original(self)

    monkeypatch.setattr(MultiPartParser, "parse", recording_parse)
    return calls


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def test_oversized_upload_is_rejected_before_parsing(parse_calls):
    files = {"file": ("big.md", b"a" * (3 * MB), "text/markdown")}
    async with _client() as client:
        response = await client.post(UPLOAD_URL, files=files)
    assert response.status_code == 413
    assert parse_calls == []


async def test_oversized_chunked_upload_is_rejected(parse_calls):
    head = (
        b"--x\r\n"
        b'Content-Disposition: form-data; name="file"; filename="b.md"\r\n'
        b"Content-Type: text/markdown\r\n\r\n"
    )

    async def body():
        yield head
        for _ in range(3):
            yield b"a" * MB
        yield b"\r\n--x--\r\n"

    async with _client() as client:
        response = await client.post(
            UPLOAD_URL,
            content=body(),
            headers={"content-type": "multipart/form-data; boundary=x"},
        )
    assert response.status_code == 413


async def test_oversized_json_body_is_rejected():
    async with _client() as client:
        response = await client.post("/api/agent/stream", json={"query": "a" * 100_000})
    assert response.status_code == 413


async def test_normal_upload_reaches_the_handler():
    files = {"file": ("ok.md", b"a" * 200_000, "text/markdown")}
    async with _client() as client:
        response = await client.post(UPLOAD_URL, files=files)
    # Not 413: the request got past the limiter and was stopped later by authentication.
    assert response.status_code in (401, 403)


async def test_invalid_content_length_is_a_400():
    sent: list[dict] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/agent/stream",
        "headers": [(b"content-length", b"abc")],
    }
    await app(scope, receive, send)
    assert sent[0]["status"] == 400

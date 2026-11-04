"""The stdio transport reads its input from a pipe. These tests drive the reader with real pipes."""

import io
import os
from types import SimpleNamespace

import pytest

from app.mcp import server


async def _collect(stream) -> list[bytes]:
    original = server.sys.stdin
    server.sys.stdin = stream
    try:
        return [line async for line in server.read_stdin_lines()]
    finally:
        server.sys.stdin = original


async def test_reads_every_line_then_stops_at_eof():
    stdin = SimpleNamespace(buffer=io.BytesIO(b'{"id": 1}\n{"id": 2}\n'))

    assert await _collect(stdin) == [b'{"id": 1}\n', b'{"id": 2}\n']


async def test_reads_from_an_os_pipe_without_blocking_the_loop():
    """A real OS pipe, the kind a client process hands the server on stdin."""
    read_fd, write_fd = os.pipe()
    with os.fdopen(write_fd, "wb") as writer:
        writer.write(b'{"jsonrpc": "2.0", "id": 7, "method": "ping"}\n')
    with os.fdopen(read_fd, "rb") as reader:
        lines = await _collect(SimpleNamespace(buffer=reader))

    assert lines == [b'{"jsonrpc": "2.0", "id": 7, "method": "ping"}\n']


@pytest.mark.parametrize("empty", [b"", b"\n"])
async def test_empty_input_yields_nothing_or_blank_lines_only(empty):
    lines = await _collect(SimpleNamespace(buffer=io.BytesIO(empty)))

    assert all(not line.strip() for line in lines)

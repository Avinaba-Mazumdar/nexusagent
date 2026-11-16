"""CRLF-preserving exact-replacement helper for batch edits."""

import os

ROOT = os.path.join(os.path.dirname(__file__), "..", "apps", "backend")


def rep(path: str, old: str, new: str, count: int = 1) -> None:
    full = os.path.join(ROOT, path)
    raw = open(full, encoding="utf-8", newline="").read()
    crlf = "\r\n" in raw
    s = raw.replace("\r\n", "\n")
    n = s.count(old)
    if n != count:
        raise SystemExit(f"{path}: expected {count} match(es), found {n}:\n{old}")
    s = s.replace(old, new)
    open(full, "w", encoding="utf-8", newline="").write(s.replace("\n", "\r\n") if crlf else s)


def show(path: str, start: int, end: int) -> None:
    full = os.path.join(ROOT, path)
    lines = open(full, encoding="utf-8").read().splitlines()
    for i in range(start - 1, min(end, len(lines))):
        print(f"{i + 1}: {lines[i]}")

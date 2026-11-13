"""Neon endpoint id, so the test suite can tell the production database from a test database."""

from urllib.parse import urlparse


def neon_endpoint(url: str) -> str:
    """Neon endpoint id (ep-...) of a URL or a bare id. Pooled and direct hosts of one branch match."""
    text = url.strip()
    host = urlparse(text).hostname if "://" in text else text.split("/")[0]
    return (host or "").split(".")[0].removesuffix("-pooler")

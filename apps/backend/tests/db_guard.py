"""Tell a Neon branch apart from another branch, so the tests never run on production."""

from urllib.parse import urlparse


def neon_endpoint(url: str) -> str:
    """Neon endpoint id (ep-...) of a URL. The pooled and the direct host of one branch share it."""
    host = urlparse(url).hostname or ""
    return host.split(".")[0].removesuffix("-pooler")

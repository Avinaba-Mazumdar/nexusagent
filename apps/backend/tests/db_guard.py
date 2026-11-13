"""Tell a Neon branch apart from another branch, so the tests never run on production."""

from app.db.endpoint import neon_endpoint

__all__ = ["neon_endpoint"]

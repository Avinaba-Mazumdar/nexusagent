from datetime import UTC, datetime

import asyncpg
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.db.neon import neon_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
async def get_health():
    """Return health check and runtime status information, including Neon DB connectivity."""
    db_connected = False
    engine_str: str | None = None
    extensions: list[str] = []
    if neon_db.pool is not None:
        try:
            async with neon_db.pool.acquire(timeout=2) as conn:
                db_connected = await conn.fetchval("SELECT 1;") == 1
                if db_connected and settings.is_dev:
                    # Version/extension fingerprints are dev-only; production does one query.
                    engine_str = f"PostgreSQL {await conn.fetchval('SHOW server_version;')}"
                    ext_rows = await conn.fetch(
                        "SELECT extname FROM pg_extension ORDER BY extname;"
                    )
                    extensions = [r["extname"] for r in ext_rows]
        except asyncpg.PostgresError, OSError, TimeoutError:
            db_connected = False
            engine_str = None
            extensions = []

    is_healthy = db_connected
    database = {
        "status": "connected" if db_connected else "disconnected",
        "connected": db_connected,
    }
    payload: dict = {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "database": database,
    }
    if settings.is_dev:
        # Version/extension fingerprints stay out of production responses.
        payload.update(
            app_name=settings.APP_NAME,
            version=settings.VERSION,
            environment=settings.ENVIRONMENT,
        )
        database.update(engine=engine_str, extensions=extensions)

    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)

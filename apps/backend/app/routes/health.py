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
            async with neon_db.pool.acquire() as conn:
                val = await conn.fetchval("SELECT 1;")
                db_connected = val == 1
                if db_connected:
                    version = await conn.fetchval("SHOW server_version;")
                    engine_str = f"PostgreSQL {version}"
                    ext_rows = await conn.fetch("SELECT extname FROM pg_extension ORDER BY extname;")
                    extensions = [r["extname"] for r in ext_rows]
        except (asyncpg.PostgresError, OSError):
            db_connected = False
            engine_str = None
            extensions = []

    is_healthy = db_connected
    payload = {
        "status": "healthy" if is_healthy else "unhealthy",
        "app_name": settings.APP_NAME,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "timestamp": datetime.now(UTC).isoformat(),
        "database": {
            "status": "connected" if db_connected else "disconnected",
            "connected": db_connected,
            "engine": engine_str,
            "extensions": extensions,
        },
    }

    status_code = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content=payload)

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.agent.llm import default_model_router
from app.agent.model_health import flush_pending_writes, sync_cooldowns, sync_cooldowns_forever
from app.agent.tools import web_search_model_router
from app.config import settings
from app.core.auth import get_client_ip
from app.core.body_limit import BodySizeLimitMiddleware
from app.core.csrf import CsrfProtectionMiddleware
from app.core.rate_limiter import SlidingWindowCounter
from app.core.security_events import security_event
from app.core.security_headers import SecurityHeadersMiddleware
from app.db.neon import DatabaseUnavailable, neon_db
from app.mcp.server import mcp, mcp_http_app
from app.rag.embeddings import default_embedding_service
from app.routes.agent import router as agent_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.rag import router as rag_router

# Uvicorn only configures its own loggers; without this the nexusagent.* INFO records are dropped.
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("nexusagent.main")


def ensure_single_worker() -> None:
    """Abuse counters and upload locks live in process memory, so N workers break them."""
    try:
        workers = int(os.environ.get("WEB_CONCURRENCY", "1"))
    except ValueError:
        return
    if workers > 1 and not settings.is_dev:
        raise RuntimeError(
            "NexusAgent keeps abuse counters and MCP rate limits in process memory; "
            "run exactly one worker (see README)."
        )


async def stop_background(sync_task: asyncio.Task[None] | None) -> None:
    """Stop the cooldown sync and always release the database, even if that task already failed."""
    if sync_task is not None:
        if not sync_task.done():
            sync_task.cancel()
        try:
            await sync_task
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.exception("Cooldown sync stopped with an error")
    try:
        await flush_pending_writes()
    except Exception:
        logger.exception("Could not flush model cooldowns during shutdown")
    try:
        await default_embedding_service.aclose()
    except Exception:
        logger.exception("Could not close the embedding client during shutdown")
    try:
        await neon_db.disconnect()
    except Exception:
        logger.exception("Could not close the database pool during shutdown")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for Neon PostgreSQL 18 connection pool and MCP session manager."""
    ensure_single_worker()
    connected = await neon_db.connect()
    if not connected and not settings.is_dev:
        raise RuntimeError("Database connection failed; refusing to start in production.")

    routers = [default_model_router, web_search_model_router]
    await sync_cooldowns(routers)
    sync_task = asyncio.create_task(sync_cooldowns_forever(routers))

    try:
        async with mcp.session_manager.run():
            yield
    finally:
        await stop_background(sync_task)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="NexusAgent: an open-source LLM benchmark assistant.",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
    lifespan=lifespan,
)

MCP_PATH = "/mcp"
mcp_rate_limiter = SlidingWindowCounter(limit=60, window=timedelta(minutes=1))
# One ceiling for all MCP clients together, so the public endpoint cannot use up the embedding quota.
MCP_GLOBAL_PER_MINUTE = 120
mcp_global_limiter = SlidingWindowCounter(limit=MCP_GLOBAL_PER_MINUTE, window=timedelta(minutes=1))


@app.middleware("http")
async def mcp_rate_limit_middleware(request: Request, call_next):
    if request.url.path.rstrip("/") == MCP_PATH:
        client_ip = get_client_ip(request)
        if not mcp_rate_limiter.hit(client_ip) or not mcp_global_limiter.hit("all"):
            security_event("quota.exceeded", ip=client_ip, kind="mcp")
            return JSONResponse(
                status_code=429,
                content={"detail": "MCP rate limit exceeded."},
                headers={"Retry-After": "60"},
            )
    return await call_next(request)


# Registered before CORS so CORS wraps it and 413 responses still carry CORS headers.
app.add_middleware(
    BodySizeLimitMiddleware,
    upload_limit=settings.MAX_UPLOAD_REQUEST_BYTES,
    default_limit=settings.MAX_JSON_REQUEST_BYTES,
)

app.add_middleware(SecurityHeadersMiddleware, hsts=not settings.is_dev)

app.add_middleware(CsrfProtectionMiddleware)

# Hardened CORS configuration: explicit origins from settings, restrictive methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
    ],
)


@app.exception_handler(DatabaseUnavailable)
async def database_unavailable_handler(_request: Request, _exc: DatabaseUnavailable):
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable"},
        headers={"Retry-After": "30"},
    )


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(documents_router, prefix="/api")
app.include_router(rag_router, prefix="/api")
app.include_router(agent_router, prefix="/api")
app.include_router(chat_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to NexusAgent: an open-source LLM benchmark assistant.",
        "version": settings.VERSION,
        "docs": "/docs" if settings.is_dev else None,
        "health": "/api/health",
    }


# Mount MCP Streamable HTTP server; FastAPI routes are matched first
app.mount("/", mcp_http_app)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )

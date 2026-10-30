import logging
from contextlib import asynccontextmanager

import asyncpg
import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.body_limit import BodySizeLimitMiddleware
from app.db.migrations import apply_migrations
from app.db.neon import DatabaseUnavailable, neon_db
from app.rag.embeddings import default_embedding_service
from app.routes.agent import router as agent_router
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.routes.documents import router as documents_router
from app.routes.health import router as health_router
from app.routes.mcp import router as mcp_router
from app.routes.rag import router as rag_router

logger = logging.getLogger("nexusagent.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for Neon PostgreSQL 18 connection pool & migrations."""
    if not settings.is_dev and settings.TRUSTED_PROXY_HOPS == 0:
        logger.warning(
            "IP-based limits use the socket address; set TRUSTED_PROXY_HOPS if you run behind a proxy."
        )
    connected = await neon_db.connect()
    if not connected and not settings.is_dev:
        raise RuntimeError("Database connection failed; refusing to start in production.")
    if connected:
        try:
            applied = await apply_migrations(neon_db)
            if applied:
                logger.info(f"Applied migrations: {applied}")
        except (asyncpg.PostgresError, OSError) as e:
            logger.error(f"Failed to execute startup migrations: {e}")
            raise

    yield
    await default_embedding_service.aclose()
    await neon_db.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="NexusAgent - Production-Grade Autonomous Orchestration Engine with Neon PostgreSQL 18 & LangGraph.",
    docs_url="/docs" if settings.is_dev else None,
    redoc_url="/redoc" if settings.is_dev else None,
    openapi_url="/openapi.json" if settings.is_dev else None,
    lifespan=lifespan,
)

# Registered before CORS so CORS wraps it and 413 responses still carry CORS headers.
app.add_middleware(
    BodySizeLimitMiddleware,
    upload_limit=settings.MAX_UPLOAD_REQUEST_BYTES,
    default_limit=settings.MAX_JSON_REQUEST_BYTES,
)

# Hardened CORS configuration: explicit origins from settings, restrictive methods and headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "Accept",
        "Origin",
        "X-Device-Id",
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
app.include_router(mcp_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    return {
        "message": "Welcome to NexusAgent - Autonomous Orchestration Engine is operational.",
        "version": settings.VERSION,
        "docs": "/docs" if settings.is_dev else None,
        "health": "/api/health",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )

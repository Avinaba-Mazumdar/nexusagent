import logging
from contextlib import asynccontextmanager

import asyncpg
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.migrations import apply_migrations
from app.db.neon import neon_db
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
    connected = await neon_db.connect()
    if connected:
        try:
            applied = await apply_migrations(neon_db)
            if applied:
                logger.info(f"Applied migrations: {applied}")
        except (asyncpg.PostgresError, OSError) as e:
            logger.error(f"Failed to execute startup migrations: {e}")
            raise

    yield
    await neon_db.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.VERSION,
    description="NexusAgent - Production-Grade Autonomous Orchestration Engine with Neon PostgreSQL 18 & LangGraph.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

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
        "X-Device-Id",
    ],
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
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
    )

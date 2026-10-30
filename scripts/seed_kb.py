#!/usr/bin/env python3
"""
NexusAgent Predefined Knowledge Base Seeding Pipeline.
Reads markdown files in knowledge_base/benchmarks/, creates semantic chunks using
the app's header-aware markdown parser, generates 768-dimensional embeddings via Gemini,
and upserts into Neon PostgreSQL inside an atomic transaction.

Usage:
  python scripts/seed_kb.py
"""

import asyncio
import hashlib
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# Add apps/backend to sys.path so backend imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps" / "backend"))

from app.config import settings
from app.db.models import Document, DocumentChunk
from app.db.neon import neon_db
from app.rag.embeddings import default_embedding_service
from app.rag.parser import default_markdown_parser

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_kb")

KB_DIR = BASE_DIR / "knowledge_base" / "benchmarks"


async def seed_knowledge_base():
    if not settings.GEMINI_API_KEY:
        logger.error("GEMINI_API_KEY is not set. Cannot generate embeddings without API key.")
        sys.exit(1)

    if not KB_DIR.exists():
        logger.error(f"Knowledge base directory {KB_DIR} does not exist.")
        sys.exit(1)

    files = sorted(KB_DIR.glob("*.md"))
    if not files:
        logger.warning(f"No markdown documents found in {KB_DIR}")
        return

    logger.info("Connecting to Neon database pool...")
    connected = await neon_db.connect()
    if not connected or not neon_db.pool:
        logger.error("Failed to connect to Neon database. Please check NEON_DATABASE_URL.")
        sys.exit(1)

    items: list[tuple[Document, list[DocumentChunk]]] = []
    now = datetime.now(UTC)

    for doc_path in files:
        raw_bytes = doc_path.read_bytes()
        text = raw_bytes.decode("utf-8")
        # Stable ID: re-seeding must not invalidate stored citation documentIds.
        doc_id = uuid5(NAMESPACE_URL, f"nexusagent:kb:{doc_path.name}")
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        chunks = default_markdown_parser.parse_markdown(
            text,
            document_id=doc_id,
            extra_metadata={"filename": doc_path.name},
            chunk_id_namespace=doc_id,  # stable chunk ids keep stored citations valid
        )
        if not chunks:
            continue

        logger.info(f"Embedding '{doc_path.name}' ({len(chunks)} chunks)...")
        embeddings = await default_embedding_service.get_embeddings([c.content for c in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk.embedding = embedding

        doc = Document(
            id=doc_id,
            user_id=None,
            filename=doc_path.name,
            mime_type="text/markdown",
            sha256_hash=sha256_hash,
            total_chunks=len(chunks),
            is_seeded=True,
            uploaded_at=now,
        )
        items.append((doc, chunks))

    if not items:
        logger.error("No seedable documents were produced; refusing to delete the existing corpus.")
        sys.exit(1)

    logger.info("Executing atomic upsert transaction...")
    await neon_db.replace_seeded_documents(items)

    logger.info(
        f"Successfully seeded {len(items)} documents and {sum(len(c) for _, c in items)} chunks into Neon DB!"
    )


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())

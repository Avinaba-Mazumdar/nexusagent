#!/usr/bin/env python3
"""
NexusAgent Predefined Knowledge Base Seeding Pipeline.
Reads markdown files in knowledge_base/benchmarks/, creates semantic chunks using
the app's MarkdownNodeParser, generates 768-dimensional embeddings via Gemini,
and upserts into Neon PostgreSQL inside an atomic transaction.

Usage:
  python scripts/seed_kb.py
"""

import asyncio
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

# Add apps/backend to sys.path so backend imports resolve
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "apps" / "backend"))

from app.config import settings
from app.db.models import Document
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

    doc_models: list[Document] = []
    chunk_records: list[tuple] = []
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
        )
        if not chunks:
            continue

        logger.info(f"Embedding '{doc_path.name}' ({len(chunks)} chunks)...")
        texts_to_embed = [c.content for c in chunks]
        embeddings = await default_embedding_service.get_embeddings(texts_to_embed)

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
        doc_models.append(doc)

        for idx, chunk in enumerate(chunks):
            chunk.embedding = embeddings[idx]
            chunk_records.append(
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.embedding,
                    settings.EMBEDDING_MODEL,
                    json.dumps(chunk.metadata),
                    chunk.created_at,
                )
            )

    doc_query = """
        INSERT INTO documents (id, user_id, filename, mime_type, sha256_hash, total_chunks, is_seeded, uploaded_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        ON CONFLICT (id) DO UPDATE SET
            sha256_hash = EXCLUDED.sha256_hash,
            total_chunks = EXCLUDED.total_chunks,
            uploaded_at = EXCLUDED.uploaded_at;
    """
    chunk_query = """
        INSERT INTO document_chunks (id, document_id, chunk_index, content, embedding, embedding_model, metadata, created_at)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8);
    """

    logger.info("Executing atomic upsert transaction...")
    async with neon_db.pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "DELETE FROM documents WHERE is_seeded = TRUE AND id <> ALL($1::uuid[]);",
            [d.id for d in doc_models],
        )
        await conn.execute(
            "DELETE FROM document_chunks WHERE document_id = ANY($1::uuid[]);",
            [d.id for d in doc_models],
        )
        for doc in doc_models:
            await conn.execute(
                doc_query,
                doc.id,
                doc.user_id,
                doc.filename,
                doc.mime_type,
                doc.sha256_hash,
                doc.total_chunks,
                doc.is_seeded,
                doc.uploaded_at,
            )
        if chunk_records:
            await conn.executemany(chunk_query, chunk_records)

    logger.info(
        f"Successfully seeded {len(doc_models)} documents and {len(chunk_records)} chunks into Neon DB!"
    )


if __name__ == "__main__":
    asyncio.run(seed_knowledge_base())

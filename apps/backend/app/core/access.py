"""Tenancy checks shared by the routers."""

from uuid import UUID

from fastapi import HTTPException, status

from app.db.models import Document
from app.db.neon import NeonDatabase


async def require_document_access(db: NeonDatabase, document_id: UUID) -> Document:
    """Validate document existence."""
    doc = await db.get_document_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc

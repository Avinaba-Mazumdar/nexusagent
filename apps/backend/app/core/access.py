"""Tenancy checks shared by the routers."""

from uuid import UUID

from fastapi import HTTPException, status

from app.db.models import Document, User
from app.db.neon import NeonDatabase


async def require_document_access(db: NeonDatabase, document_id: UUID, user: User) -> Document:
    """Validate document existence and tenancy access: seeded documents or user's own uploads."""
    doc = await db.get_document_by_id(document_id)
    if not doc or (not doc.is_seeded and doc.user_id != user.id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    return doc

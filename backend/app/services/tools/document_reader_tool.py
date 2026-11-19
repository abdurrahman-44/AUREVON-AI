from typing import Any, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.models.entities import Document, DocumentChunk
from backend.app.services.documents.rag import RAGService


class DocumentReaderTool:
    """Reads excerpts from a user's uploaded document with strict ownership isolation and injection filtering."""

    name = "document_reader"

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        user_id: Optional[str],
        document_id: Optional[str] = None,
        filename: Optional[str] = None,
        max_chunks: int = 5,
    ) -> Dict[str, Any]:
        stmt = select(Document).where(Document.processing_status == "completed")
        if user_id is not None:
            stmt = stmt.where(Document.user_id == user_id)
        else:
            stmt = stmt.where(Document.user_id.is_(None))

        if document_id:
            stmt = stmt.where(Document.id == document_id)
        elif filename:
            stmt = stmt.where(Document.filename.ilike(f"%{filename.strip()}%"))
        else:
            stmt = stmt.order_by(Document.created_at.desc())

        doc = (await db.execute(stmt.limit(1))).scalar_one_or_none()
        if not doc:
            return {
                "ok": False,
                "error": "No matching uploaded document found for this user.",
                "chunks": [],
            }

        chunk_res = await db.execute(
            select(DocumentChunk)
            .where(DocumentChunk.document_id == doc.id)
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(max(1, min(10, max_chunks)))
        )
        chunks = [
            {
                "chunk_id": c.id,
                "document_id": doc.id,
                "filename": doc.filename,
                "page_number": c.page_number,
                "content": RAGService.sanitize_chunk_text(c.content),
            }
            for c in chunk_res.scalars().all()
        ]
        return {
            "ok": True,
            "document_id": doc.id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "total_chunks": doc.chunk_count,
            "chunks": chunks,
        }

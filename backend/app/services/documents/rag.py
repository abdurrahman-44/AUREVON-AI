from typing import List, Dict, Any, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.models.entities import Document, DocumentChunk
from backend.app.services.documents.embeddings import EmbeddingService


class RAGService:
    """Retrieval-Augmented Generation retrieval and context builder."""

    @classmethod
    async def retrieve_relevant_chunks(
        cls,
        session: AsyncSession,
        query: str,
        user_id: Optional[str] = None,
        top_k: int = 4,
        min_similarity: float = 0.25,
    ) -> List[Dict[str, Any]]:
        query_vec = await EmbeddingService.get_embedding(query)

        # Retrieve all user's chunks
        stmt = select(DocumentChunk).join(Document, DocumentChunk.document_id == Document.id)
        if user_id:
            stmt = stmt.where(Document.user_id == user_id)
        stmt = stmt.options(selectinload(DocumentChunk.document))

        res = await session.execute(stmt)
        chunks = res.scalars().all()

        scored = []
        for c in chunks:
            if not c.embedding:
                continue
            sim = EmbeddingService.cosine_similarity(query_vec, c.embedding)
            if sim >= min_similarity:
                scored.append({
                    "chunk_id": c.id,
                    "document_id": c.document_id,
                    "filename": c.document.filename if c.document else "Unknown",
                    "page_number": c.page_number,
                    "content": c.content,
                    "similarity": round(sim, 4),
                })

        # Sort descending by similarity
        scored.sort(key=lambda x: x["similarity"], reverse=True)
        return scored[:top_k]

    @classmethod
    def format_grounded_context(cls, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return ""

        context_blocks = ["### 📄 Grounded Document References:"]
        for idx, c in enumerate(chunks, start=1):
            page_info = f" (Page {c['page_number']})" if c.get('page_number') else ""
            context_blocks.append(
                f"**[Source {idx}: {c['filename']}{page_info}]** (Relevance: {int(c['similarity']*100)}%):\n{c['content']}"
            )
        return "\n\n".join(context_blocks)

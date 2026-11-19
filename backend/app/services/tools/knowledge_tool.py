from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.services.documents.rag import RAGService


class KnowledgeRetrievalTool:
    """Runs hybrid FTS5 + semantic vector retrieval over the user's knowledge base."""

    name = "knowledge_retrieval"

    @classmethod
    async def execute(
        cls,
        db: AsyncSession,
        user_id: Optional[str],
        query: str,
        top_k: int = 4,
        document_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        clean_q = (query or "").strip()
        if not clean_q:
            return {"ok": False, "error": "Empty retrieval query", "chunks": []}

        chunks = await RAGService.retrieve_relevant_chunks(
            session=db,
            query=clean_q,
            user_id=user_id,
            top_k=max(1, min(8, top_k)),
            document_ids=document_ids,
        )
        return {
            "ok": True,
            "query": clean_q,
            "total_found": len(chunks),
            "chunks": chunks,
        }

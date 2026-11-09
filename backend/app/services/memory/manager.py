from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.entities import Memory
from backend.app.services.documents.embeddings import EmbeddingService


class MemoryManager:
    """Manages cross-conversation episodic and semantic memories."""

    @classmethod
    async def get_relevant_memories(
        cls,
        session: AsyncSession,
        prompt: str,
        user_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Memory]:
        stmt = select(Memory).where(Memory.is_active == True)
        if user_id:
            stmt = stmt.where(Memory.user_id == user_id)
        stmt = stmt.order_by(Memory.updated_at.desc()).limit(20)

        res = await session.execute(stmt)
        candidates = list(res.scalars().all())
        if not candidates:
            return []

        # Score relevance with feature vector
        prompt_vec = await EmbeddingService.get_embedding(prompt)
        scored = []
        for m in candidates:
            m_vec = await EmbeddingService.get_embedding(m.content)
            sim = EmbeddingService.cosine_similarity(prompt_vec, m_vec)
            scored.append((sim, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    @classmethod
    def format_memory_context(cls, memories: List[Memory]) -> str:
        if not memories:
            return ""
        items = [f"- [{m.category.upper()}]: {m.content}" for m in memories]
        return "### 🧠 Active User Long-Term Memories:\n" + "\n".join(items)

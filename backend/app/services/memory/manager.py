import re
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from backend.app.models.entities import Memory
from backend.app.services.documents.embeddings import EmbeddingService

_EXPLICIT_MEMORY_PATTERNS = [
    re.compile(r"(?i)^(?:please\s+)?remember\s+(?:that\s+)?(.+)$"),
    re.compile(r"(?i)^save\s+(?:this\s+)?to\s+memory\s*:\s*(.+)$"),
    re.compile(r"(?i)^keep\s+in\s+mind\s+(?:that\s+)?(.+)$"),
]


class MemoryManager:
    """Manages cross-conversation episodic and semantic memories with strict tenant isolation."""

    @classmethod
    def detect_explicit_memory_request(cls, prompt: str) -> Optional[Tuple[str, str]]:
        """Detect explicit user consent to remember a fact/preference."""
        clean = (prompt or "").strip()
        if not clean or len(clean) > 400:
            return None
        for pattern in _EXPLICIT_MEMORY_PATTERNS:
            m = pattern.match(clean)
            if m:
                fact = m.group(1).strip().rstrip(".")
                if len(fact) >= 4:
                    lowered = fact.lower()
                    category = "preference" if any(k in lowered for k in ("prefer", "like", "always", "style", "tone", "use ")) else "fact"
                    return fact, category
        return None

    @classmethod
    async def save_explicit_memory(
        cls,
        session: AsyncSession,
        user_id: Optional[str],
        content: str,
        category: str = "fact",
        source: str = "explicit_chat",
    ) -> Optional[Memory]:
        trimmed = (content or "").strip()
        if not trimmed:
            return None
        stmt = select(Memory).where(Memory.is_active == True)
        if user_id is not None:
            stmt = stmt.where(Memory.user_id == user_id)
        else:
            stmt = stmt.where(Memory.user_id.is_(None))
        existing = (await session.execute(stmt)).scalars().all()
        for item in existing:
            if item.content.strip().lower() == trimmed.lower():
                item.updated_at = datetime.now(timezone.utc)
                await session.commit()
                return item

        now = datetime.now(timezone.utc)
        mem = Memory(
            user_id=user_id,
            content=trimmed,
            category=category,
            source=source,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        session.add(mem)
        await session.commit()
        await session.refresh(mem)
        return mem

    @classmethod
    async def get_relevant_memories(
        cls,
        session: AsyncSession,
        prompt: str,
        user_id: Optional[str] = None,
        top_k: int = 5,
    ) -> List[Memory]:
        stmt = select(Memory).where(Memory.is_active == True)
        if user_id is not None:
            stmt = stmt.where(Memory.user_id == user_id)
        else:
            stmt = stmt.where(Memory.user_id.is_(None))
        stmt = stmt.order_by(Memory.updated_at.desc()).limit(30)

        res = await session.execute(stmt)
        candidates = list(res.scalars().all())
        if not candidates:
            return []

        prompt_vec = await EmbeddingService.get_embedding(prompt)
        prompt_kw = set(EmbeddingService.extract_keywords(prompt))
        scored = []
        for m in candidates:
            m_vec = await EmbeddingService.get_embedding(m.content)
            sim = EmbeddingService.cosine_similarity(prompt_vec, m_vec)
            kw_bonus = 0.0
            if prompt_kw:
                m_kw = set(EmbeddingService.extract_keywords(m.content))
                kw_bonus = 0.25 * (len(prompt_kw & m_kw) / max(1, len(prompt_kw)))
            scored.append((sim + kw_bonus, m))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored[:top_k]]

    @classmethod
    def format_memory_context(cls, memories: List[Memory]) -> str:
        if not memories:
            return ""
        items = [f"- [{m.category.upper()}]: {m.content}" for m in memories]
        return "### Active User Long-Term Memories:\n" + "\n".join(items)

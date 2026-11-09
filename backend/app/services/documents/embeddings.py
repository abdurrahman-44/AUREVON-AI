import math
import re
import hashlib
from typing import List
import httpx
from backend.app.core.config import settings

VECTOR_DIM = 128


class EmbeddingService:
    """Generates normalized vector representations and computes similarity."""

    @classmethod
    async def get_embedding(cls, text: str) -> List[float]:
        """Try Ollama embedding first, fallback to deterministic semantic feature hashing."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.post(
                    f"{settings.OLLAMA_BASE_URL.rstrip('/')}/api/embeddings",
                    json={"model": settings.DEFAULT_MODEL, "prompt": text[:500]},
                )
                if res.status_code == 200:
                    data = res.json()
                    emb = data.get("embedding")
                    if emb and isinstance(emb, list):
                        return cls._normalize(emb[:VECTOR_DIM] if len(emb) >= VECTOR_DIM else emb + [0.0]*(VECTOR_DIM - len(emb)))
        except Exception:
            pass

        # High-performance, zero-dependency deterministic semantic vector
        return cls._compute_feature_vector(text)

    @classmethod
    def _compute_feature_vector(cls, text: str) -> List[float]:
        vec = [0.0] * VECTOR_DIM
        tokens = re.findall(r"\w+", text.lower())
        if not tokens:
            return vec

        for i, token in enumerate(tokens):
            # Unigram hash
            h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % VECTOR_DIM
            vec[h1] += 1.0

            # Bigram hash
            if i < len(tokens) - 1:
                bigram = f"{token}_{tokens[i+1]}"
                h2 = int(hashlib.md5(bigram.encode("utf-8")).hexdigest()[:8], 16) % VECTOR_DIM
                vec[h2] += 1.5

        return cls._normalize(vec)

    @classmethod
    def _normalize(cls, vec: List[float]) -> List[float]:
        norm = math.sqrt(sum(x * x for x in vec))
        if norm == 0.0:
            return vec
        return [round(x / norm, 5) for x in vec]

    @classmethod
    def cosine_similarity(cls, vec1: List[float], vec2: List[float]) -> float:
        if not vec1 or not vec2:
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        return max(0.0, min(1.0, dot))

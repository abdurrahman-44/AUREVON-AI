import math
import re
import hashlib
from typing import List, Set

VECTOR_DIM = 128

_STOPWORDS: Set[str] = {
    "a", "an", "and", "are", "as", "at", "be", "but", "by", "for", "from",
    "has", "have", "he", "in", "is", "it", "its", "of", "on", "or", "she",
    "that", "the", "their", "there", "these", "they", "this", "to", "was",
    "were", "will", "with", "you", "your",
}


class EmbeddingService:
    """Fast local semantic vector generator without slow generation-model /api/embeddings calls."""

    @classmethod
    def extract_keywords(cls, text: str) -> List[str]:
        tokens = re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
        return [t for t in tokens if len(t) >= 2 and t not in _STOPWORDS]

    @classmethod
    async def get_embedding(cls, text: str) -> List[float]:
        """Compute deterministic weighted semantic feature vector in sub-millisecond local CPU time."""
        return cls._compute_feature_vector(text)

    @classmethod
    def _compute_feature_vector(cls, text: str) -> List[float]:
        vec = [0.0] * VECTOR_DIM
        tokens = re.findall(r"[A-Za-z0-9_]+", (text or "").lower())
        if not tokens:
            return vec

        filtered = [t for t in tokens if t not in _STOPWORDS] or tokens

        for i, token in enumerate(filtered):
            weight = 1.35 if len(token) >= 5 else 1.0
            h1 = int(hashlib.md5(token.encode("utf-8")).hexdigest()[:8], 16) % VECTOR_DIM
            vec[h1] += weight

            # Character trigram overlap helps match partial/inflected terms accurately
            if len(token) >= 4:
                for k in range(len(token) - 2):
                    tri = f"~{token[k:k+3]}"
                    ht = int(hashlib.md5(tri.encode("utf-8")).hexdigest()[:8], 16) % VECTOR_DIM
                    vec[ht] += 0.35

            # Bigram hash
            if i < len(filtered) - 1:
                bigram = f"{token}_{filtered[i+1]}"
                h2 = int(hashlib.md5(bigram.encode("utf-8")).hexdigest()[:8], 16) % VECTOR_DIM
                vec[h2] += 1.6

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

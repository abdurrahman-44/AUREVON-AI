import time
from collections import defaultdict, deque
from threading import Lock
from typing import Callable, Deque, Dict
from fastapi import HTTPException, Request, status

from backend.app.core.config import settings


class SlidingWindowRateLimiter:
    """In-memory per-IP/route sliding-window rate limiter."""

    def __init__(self):
        self._buckets: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, max_requests: int, window_seconds: int = 60) -> None:
        if not settings.RATE_LIMIT_ENABLED or max_requests <= 0:
            return
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            q = self._buckets[key]
            while q and q[0] <= cutoff:
                q.popleft()
            if len(q) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Rate limit exceeded. Please wait briefly before trying again.",
                    headers={"Retry-After": str(window_seconds)},
                )
            q.append(now)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()


rate_limiter = SlidingWindowRateLimiter()


def rate_limit_dependency(bucket_name: str, limit_getter: Callable[[], int], window_seconds: int = 60):
    async def _enforce(request: Request) -> None:
        forwarded_for = request.headers.get("x-forwarded-for")
        client_ip = forwarded_for.split(",")[0].strip() if forwarded_for else (request.client.host if request.client else "unknown")
        limit = limit_getter()
        rate_limiter.check(f"{bucket_name}:{client_ip}", max_requests=limit, window_seconds=window_seconds)

    return _enforce

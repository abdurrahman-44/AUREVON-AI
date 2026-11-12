import time
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Dict, Optional, Tuple


class ControlCentreCache:
    """Thread-safe bounded in-memory TTL cache for non-sensitive operational metadata."""

    def __init__(self, max_entries: int = 256):
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = Lock()
        self._max_entries = max_entries
        self._hits = 0
        self._misses = 0
        self._started_at = datetime.now(timezone.utc)

    def get(self, key: str) -> Optional[Any]:
        now = time.monotonic()
        with self._lock:
            item = self._store.get(key)
            if not item:
                self._misses += 1
                return None
            value, expires_at = item
            if expires_at <= now:
                self._store.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return value

    def set(self, key: str, value: Any, ttl_seconds: int = 30) -> None:
        expires_at = time.monotonic() + max(1, ttl_seconds)
        with self._lock:
            if len(self._store) >= self._max_entries and key not in self._store:
                oldest_key = next(iter(self._store))
                self._store.pop(oldest_key, None)
            self._store[key] = (value, expires_at)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._store.pop(key, None) is not None

    def clear(self) -> int:
        with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def status(self) -> Dict[str, Any]:
        now = time.monotonic()
        with self._lock:
            expired = [k for k, (_, exp) in self._store.items() if exp <= now]
            for k in expired:
                self._store.pop(k, None)
            total_lookups = self._hits + self._misses
            hit_rate = round((self._hits / total_lookups) * 100.0, 2) if total_lookups > 0 else None
            return {
                "entries": len(self._store),
                "max_entries": self._max_entries,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_pct": hit_rate,
                "started_at": self._started_at.isoformat(),
            }


app_cache = ControlCentreCache()

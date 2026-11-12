import logging
from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Deque, Dict, List


class RecentErrorHandler(logging.Handler):
    """Thread-safe bounded ring buffer capturing genuine runtime ERROR+ logs."""

    def __init__(self, maxlen: int = 100):
        super().__init__(level=logging.ERROR)
        self._records: Deque[Dict] = deque(maxlen=maxlen)
        self._lock = Lock()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = record.getMessage()
            if len(msg) > 240:
                msg = msg[:237] + "..."
            entry = {
                "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc),
                "source": record.name,
                "category": record.levelname.lower(),
                "message": msg,
            }
            with self._lock:
                self._records.appendleft(entry)
        except Exception:
            pass

    def get_recent(self, limit: int = 20) -> List[Dict]:
        with self._lock:
            return list(self._records)[:limit]

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


error_tracker = RecentErrorHandler(maxlen=100)


def configure_logging(debug: bool = True) -> None:
    level = logging.INFO if debug else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    root_logger = logging.getLogger()
    if error_tracker not in root_logger.handlers:
        root_logger.addHandler(error_tracker)

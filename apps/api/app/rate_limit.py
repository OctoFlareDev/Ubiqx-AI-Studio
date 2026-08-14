from __future__ import annotations

import hashlib
import math
import threading
import time
from collections import deque

from fastapi import Request


class SlidingWindowRateLimiter:
    """In-memory sliding-window limiter keyed by an opaque string.

    Keys are cheap and content-independent (a SHA-256 of the bearer token or
    a client address), so plaintext credentials never sit in the key table.
    """

    def __init__(self, limit: int, window_seconds: float) -> None:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self.limit = limit
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                queue = deque()
                self._hits[key] = queue
            while queue and now - queue[0] >= self.window_seconds:
                queue.popleft()
            if not queue:
                self._hits.pop(key, None)
                queue = deque()
                self._hits[key] = queue
            if len(queue) >= self.limit:
                return False
            queue.append(now)
            return True

    def retry_after(self, key: str) -> int:
        now = time.monotonic()
        with self._lock:
            queue = self._hits.get(key)
            if queue is None:
                return 0
            while queue and now - queue[0] >= self.window_seconds:
                queue.popleft()
            if not queue:
                self._hits.pop(key, None)
                return 0
            return max(1, math.ceil(self.window_seconds - (now - queue[0])))

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


def rate_limit_key(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    if authorization:
        digest = hashlib.sha256(authorization.encode("utf-8")).hexdigest()
        return "key:" + digest
    host = request.client.host if request.client else "unknown"
    return "ip:" + host

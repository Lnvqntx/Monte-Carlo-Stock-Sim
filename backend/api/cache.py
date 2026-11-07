"""Small thread-safe in-memory TTL cache (per process)."""

from __future__ import annotations

import os
import threading
import time
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

DEFAULT_TTL_SECONDS = 15 * 60
DEFAULT_MAX_ENTRIES = 100


def ttl_from_env(name: str = "CACHE_TTL_SECONDS", default: float = DEFAULT_TTL_SECONDS) -> float:
    """Read a TTL in seconds from the environment; fall back to `default` if unset or invalid."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(value, 0.0)


class TTLCache:
    """LRU-bounded cache whose entries expire `ttl` seconds after being stored.

    A ttl of 0 disables caching.
    """

    def __init__(self, ttl: float = DEFAULT_TTL_SECONDS, max_entries: int = DEFAULT_MAX_ENTRIES):
        self.ttl = float(ttl)
        self.max_entries = int(max_entries)
        self._data: OrderedDict[Hashable, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Hashable) -> Any | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            expires_at, value = item
            if time.monotonic() >= expires_at:
                del self._data[key]
                return None
            self._data.move_to_end(key)
            return value

    def set(self, key: Hashable, value: Any) -> None:
        if self.ttl <= 0 or self.max_entries <= 0:
            return
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._data)

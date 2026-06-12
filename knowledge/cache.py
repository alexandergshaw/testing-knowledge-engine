"""In-memory TTL cache so repeated questions don't re-hit the source APIs.
Per-process and unbounded-ish (pruned on write) — fine for a small app."""

import threading
import time


class TTLCache:
    def __init__(self, ttl_seconds=3600, max_entries=500):
        self.ttl = ttl_seconds
        self.max_entries = max_entries
        self._store = {}
        self._lock = threading.Lock()

    def get(self, key):
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires = entry
            if time.time() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key, value):
        with self._lock:
            if len(self._store) >= self.max_entries:
                now = time.time()
                self._store = {
                    k: v for k, v in self._store.items() if v[1] > now
                }
                while len(self._store) >= self.max_entries:
                    self._store.pop(next(iter(self._store)))
            self._store[key] = (value, time.time() + self.ttl)

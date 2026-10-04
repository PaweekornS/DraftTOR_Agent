"""Bounded concurrency for LLM work.

A process-wide semaphore caps in-flight LLM requests at TOR_LLM_CONCURRENCY (default 4);
extra calls queue. Thread pools are only for fan-out and never hold the semaphore while
waiting on futures, so nested fan-out (e.g. per-chapter judging inside parallel rules) can't deadlock.
"""
import hashlib
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Iterable, List, Optional, TypeVar

from app.config import settings

T = TypeVar("T")
R = TypeVar("R")

_llm_slots = threading.BoundedSemaphore(settings.TOR_LLM_CONCURRENCY)


def limited(fn: Callable[..., R]) -> Callable[..., R]:
    """Wrap an LLM callable so at most TOR_LLM_CONCURRENCY calls run at once."""
    def wrapper(*args, **kwargs):
        with _llm_slots:
            return fn(*args, **kwargs)
    return wrapper


def pmap(fn: Callable[[T], R], items: Iterable[T], max_workers: Optional[int] = None) -> List[R]:
    """Order-preserving parallel map. Exceptions propagate to the caller."""
    items = list(items)
    if len(items) <= 1:
        return [fn(i) for i in items]
    with ThreadPoolExecutor(max_workers=max_workers or min(len(items), 16)) as ex:
        return list(ex.map(fn, items))


def stable_hash(*parts: Any) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()


class JudgeCache:
    """Thread-safe LRU of LLM-judge verdicts keyed by (rule, citation, requirements, chapter text)."""

    def __init__(self, max_items: int = 2048):
        self._data: "OrderedDict[str, Any]" = OrderedDict()
        self._lock = threading.Lock()
        self.max_items = max_items
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            if key in self._data:
                self._data.move_to_end(key)
                self.hits += 1
                return self._data[key]
            self.misses += 1
            return None

    def put(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._data.move_to_end(key)
            while len(self._data) > self.max_items:
                self._data.popitem(last=False)

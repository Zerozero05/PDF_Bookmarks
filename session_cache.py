"""Bounded, process-local LRU for recognition data and preview PNG bytes.

Cached values are isolated copies. Nothing is persisted, and the cache never
owns a PDF document or invokes PyMuPDF. Callers still serialize PDF access.
"""

from collections import OrderedDict
from copy import deepcopy
from dataclasses import fields, is_dataclass
import os
from pathlib import Path
import sys
from threading import RLock


def pdf_identity(path):
    """Bind cache entries to the current file, not merely its displayed name."""
    path = Path(path).expanduser().resolve()
    stat = path.stat()
    return os.path.normcase(str(path)), stat.st_size, stat.st_mtime_ns


def _size(value, seen=None):
    """Account for owned Python payloads, including dataclass/list members."""
    seen = set() if seen is None else seen
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    total = sys.getsizeof(value)
    if isinstance(value, dict):
        total += sum(_size(key, seen) + _size(item, seen) for key, item in value.items())
    elif isinstance(value, (list, tuple, set, frozenset)):
        total += sum(_size(item, seen) for item in value)
    elif is_dataclass(value) and not isinstance(value, type):
        total += sys.getsizeof(vars(value)) if hasattr(value, "__dict__") else 0
        total += sum(_size(getattr(value, item.name), seen) for item in fields(value))
    return total


class SessionCache:
    """One shared budget across namespaces; LRU eviction never edits callers.

    ``document`` is a ``pdf_identity`` tuple. Observing a new identity for the
    same resolved path discards its old recognition and preview entries. A
    missing result is ``None``; callers should not cache ``None`` as a payload.
    """

    def __init__(self, max_bytes=64 * 1024 * 1024):
        if type(max_bytes) is not int or max_bytes < 0:
            raise ValueError("Cache budget must be a nonnegative integer.")
        self.max_bytes = max_bytes
        self.used_bytes = 0
        self.hits = self.misses = self.evictions = 0
        self._items = OrderedDict()
        self._lock = RLock()

    def __len__(self):
        with self._lock:
            return len(self._items)

    @property
    def count(self):
        return len(self)

    def _remove(self, key):
        _, size = self._items.pop(key)
        self.used_bytes -= size

    def _current_document(self, document):
        if document is not None:
            for key in list(self._items):
                old = key[2]
                if old is not None and old[0] == document[0] and old != document:
                    self._remove(key)

    def get(self, namespace, key, *, document=None):
        with self._lock:
            self._current_document(document)
            identity = (namespace, key, document)
            if identity not in self._items:
                self.misses += 1
                return None
            self.hits += 1
            self._items.move_to_end(identity)
            return deepcopy(self._items[identity][0])

    def put(self, namespace, key, value, *, document=None):
        with self._lock:
            self._current_document(document)
            identity = (namespace, key, document)
            # Measure before copying a huge value; failed/oversized replacement
            # must not retain a stale value under the same key.
            size = _size(identity) + _size(value) + 128
            if identity in self._items:
                self._remove(identity)
            if value is None or size > self.max_bytes:
                return False
            copied = deepcopy(value)
            size = _size(identity) + _size(copied) + 128
            if size > self.max_bytes:
                return False
            while self._items and self.used_bytes + size > self.max_bytes:
                self._remove(next(iter(self._items)))
                self.evictions += 1
            self._items[identity] = copied, size
            self.used_bytes += size
            return True

    def invalidate(self, document=None, namespace=None):
        """Discard a namespace, all versions of a document path, or all data."""
        with self._lock:
            for key in list(self._items):
                if (namespace is None or key[0] == namespace) and (
                        document is None or key[2] is not None and key[2][0] == document[0]):
                    self._remove(key)

    def clear(self):
        self.invalidate()

import threading
from typing import Any, Dict
from yasin_core.storage.base import BaseStorage


class InMemoryStorage(BaseStorage):
    """
    In-Memory Storage provider. Useful for fast caching, testing, and mock scenarios.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._data = {}
        self._initialized = False

    def initialize(self) -> None:
        with self._lock:
            self._initialized = True

    def shutdown(self) -> None:
        with self._lock:
            self._initialized = False

    def reload(self) -> None:
        pass

    def health(self) -> Dict[str, Any]:
        with self._lock:
            if not self._initialized:
                return {
                    "status": "unhealthy",
                    "healthy": False,
                    "error": "Not initialized",
                }
            return {"status": "healthy", "healthy": True}

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "backend_type": "in-memory",
            "persistent": False,
            "key_value": True,
        }

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]

    def clear(self) -> None:
        with self._lock:
            self._data.clear()

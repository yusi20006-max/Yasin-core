import json
import os
import threading
from typing import Any, Dict
from yasin_core.storage.base import BaseStorage
from yasin_core.storage.exceptions import StorageConnectionError, StorageValidationError


class JSONFileStorage(BaseStorage):
    """
    Persistent JSON file-based storage provider.
    """

    def __init__(self, filepath: str):
        self._lock = threading.RLock()
        self.filepath = filepath
        self._data = {}
        self._initialized = False
        self.load()

    def initialize(self) -> None:
        with self._lock:
            self._initialized = True
            self.load()

    def shutdown(self) -> None:
        with self._lock:
            self.save()
            self._initialized = False

    def reload(self) -> None:
        with self._lock:
            self.load()

    def load(self):
        with self._lock:
            if os.path.exists(self.filepath):
                try:
                    with open(self.filepath, "r", encoding="utf-8") as f:
                        self._data = json.load(f)
                except Exception:
                    self._data = {}
            else:
                self._data = {}

    def save(self):
        with self._lock:
            dir_path = os.path.dirname(self.filepath)
            if dir_path and not os.path.exists(dir_path):
                try:
                    os.makedirs(dir_path, exist_ok=True)
                except Exception as e:
                    raise StorageConnectionError(
                        f"Failed to create directory for database storage: {e}"
                    ) from e

            try:
                with open(self.filepath, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, indent=4)
            except Exception as e:
                raise StorageConnectionError(
                    f"Failed to write to storage file {self.filepath}: {e}"
                ) from e

    def health(self) -> Dict[str, Any]:
        with self._lock:
            try:
                # Check write permissions or create directory
                dir_path = os.path.dirname(self.filepath)
                if dir_path and not os.path.exists(dir_path):
                    # Check if we can write to parent
                    parent_dir = os.path.dirname(dir_path) or "."
                    if not os.access(parent_dir, os.W_OK):
                        return {
                            "status": "unhealthy",
                            "healthy": False,
                            "error": f"Parent directory {parent_dir} is not writable",
                        }
                elif os.path.exists(self.filepath):
                    if not os.access(self.filepath, os.W_OK):
                        return {
                            "status": "unhealthy",
                            "healthy": False,
                            "error": f"File {self.filepath} is not writable",
                        }
                return {"status": "healthy", "healthy": True}
            except Exception as e:
                return {"status": "unhealthy", "healthy": False, "error": str(e)}

    @property
    def metadata(self) -> Dict[str, Any]:
        return {
            "backend_type": "json",
            "persistent": True,
            "key_value": True,
            "filepath": self.filepath,
        }

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self.save()

    def delete(self, key: str) -> None:
        with self._lock:
            if key in self._data:
                del self._data[key]
                self.save()

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self.save()

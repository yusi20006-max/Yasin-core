import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from yasin_core.memory.base import LongTermMemory, MemoryEntry
from yasin_core.storage.base import BaseStorage
from yasin_core.events import EventBus


class StorageBackedLongTermMemory(LongTermMemory):
    """
    Thread-safe persistent memory provider integrated with any standard Yasin Storage backend.
    """
    def __init__(self, storage: BaseStorage, event_bus: Optional[EventBus] = None):
        self._lock = threading.RLock()
        self.storage = storage
        self.event_bus = event_bus

    def _cleanup_expired(self) -> None:
        """Scan keys to identify and remove expired entries passively."""
        with self._lock:
            # We assume storage could be read/written under the lock
            keys_to_delete = []
            # Gather all stored entries
            for key in list(self._get_all_keys()):
                entry = self.get_entry(key)
                if entry and entry.is_expired():
                    keys_to_delete.append(key)
            for key in keys_to_delete:
                self.delete(key)

    def _get_all_keys(self) -> List[str]:
        # If the storage backend provides an internal keys/dictionary representation, we use it,
        # otherwise we fallback to empty list or we can inspect _data if it's JSONFileStorage.
        if hasattr(self.storage, "_data"):
            return list(self.storage._data.keys())
        return []

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._cleanup_expired()
            entry = self.get_entry(key)
            if entry is not None:
                return entry.value
            return default

    def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> None:
        with self._lock:
            self._cleanup_expired()
            expire_at = None
            if ttl is not None:
                expire_at = (datetime.now(timezone.utc) + timedelta(seconds=ttl)).isoformat()

            entry = MemoryEntry(
                key=key,
                value=value,
                metadata=metadata,
                expire_at=expire_at
            )
            self.storage.set(key, entry.to_dict())

            if self.event_bus:
                self.event_bus.publish(
                    "memory_saved",
                    {"key": key, "category": "long-term"},
                    metadata={"entry": entry.to_dict()}
                )

    def delete(self, key: str) -> None:
        with self._lock:
            self._cleanup_expired()
            self.storage.delete(key)
            if self.event_bus:
                self.event_bus.publish(
                    "memory_deleted",
                    {"key": key, "category": "long-term"}
                )

    def clear(self) -> None:
        with self._lock:
            self.storage.clear()
            if self.event_bus:
                self.event_bus.publish(
                    "memory_cleared",
                    {"category": "long-term"}
                )

    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        with self._lock:
            data = self.storage.get(key)
            if data is None:
                return None
            try:
                # If data was stored as a raw value (backward compatibility fallback), wrap it.
                if not isinstance(data, dict) or "key" not in data or "value" not in data:
                    return MemoryEntry(key=key, value=data)
                entry = MemoryEntry.from_dict(data)
                if entry.is_expired():
                    # Delete passively
                    self.storage.delete(key)
                    return None
                return entry
            except Exception:
                return MemoryEntry(key=key, value=data)

    def search(self, query: str) -> List[MemoryEntry]:
        with self._lock:
            self._cleanup_expired()
            q = query.lower()
            results = []
            for key in self._get_all_keys():
                entry = self.get_entry(key)
                if entry:
                    match = (
                        q in entry.key.lower() or
                        q in str(entry.value).lower() or
                        any(q in str(k).lower() or q in str(v).lower() for k, v in entry.metadata.items())
                    )
                    if match:
                        results.append(entry)
            return results

    def filter(self, metadata_filters: Dict[str, Any]) -> List[MemoryEntry]:
        with self._lock:
            self._cleanup_expired()
            results = []
            for key in self._get_all_keys():
                entry = self.get_entry(key)
                if entry:
                    match = True
                    for fk, fv in metadata_filters.items():
                        if fk not in entry.metadata or entry.metadata[fk] != fv:
                            match = False
                            break
                    if match:
                        results.append(entry)
            return results

    def health(self) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            return {
                "status": "healthy",
                "total_entries": len(self._get_all_keys())
            }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            return {
                "state": "active",
                "total_entries": len(self._get_all_keys()),
                "keys": self._get_all_keys()
            }

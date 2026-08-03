import threading
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from yasin_core.memory.base import BaseMemory, ShortTermMemory, LongTermMemory, MemoryEntry
from yasin_core.events import Event, EventBus


class InMemoryMemoryBase(BaseMemory):
    """
    Common thread-safe and feature-rich foundation for in-memory memory engines.
    """
    def __init__(self, event_bus: Optional[EventBus] = None, memory_type: str = "in_memory"):
        self._lock = threading.RLock()
        self._data: Dict[str, MemoryEntry] = {}
        self.event_bus = event_bus
        self._memory_type = memory_type

    def _cleanup_expired(self) -> None:
        """Passive/active internal cleanup of expired entries."""
        with self._lock:
            expired_keys = [k for k, entry in self._data.items() if entry.is_expired()]
            for k in expired_keys:
                del self._data[k]

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            self._cleanup_expired()
            entry = self._data.get(key)
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
            self._data[key] = entry

            if self.event_bus:
                self.event_bus.publish(
                    "memory_saved",
                    {"key": key, "category": self._memory_type},
                    metadata={"entry": entry.to_dict()}
                )

    def delete(self, key: str) -> None:
        with self._lock:
            self._cleanup_expired()
            if key in self._data:
                del self._data[key]
                if self.event_bus:
                    self.event_bus.publish(
                        "memory_deleted",
                        {"key": key, "category": self._memory_type}
                    )

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            if self.event_bus:
                self.event_bus.publish(
                    "memory_cleared",
                    {"category": self._memory_type}
                )

    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        with self._lock:
            self._cleanup_expired()
            return self._data.get(key)

    def search(self, query: str) -> List[MemoryEntry]:
        with self._lock:
            self._cleanup_expired()
            q = query.lower()
            results = []
            for entry in self._data.values():
                # Check key, string representation of value, or metadata keys/values
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
            for entry in self._data.values():
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
                "total_entries": len(self._data)
            }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            self._cleanup_expired()
            return {
                "state": "active",
                "total_entries": len(self._data),
                "keys": list(self._data.keys())
            }


class InMemoryShortTermMemory(InMemoryMemoryBase, ShortTermMemory):
    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus=event_bus, memory_type="short-term")


class InMemoryLongTermMemory(InMemoryMemoryBase, LongTermMemory):
    def __init__(self, event_bus: Optional[EventBus] = None):
        super().__init__(event_bus=event_bus, memory_type="long-term")

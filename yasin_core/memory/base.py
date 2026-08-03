from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from yasin_core.runtime.interfaces import BaseService


class MemoryEntry:
    """
    Represents a single entry in the memory system, containing the core value,
    creation timestamp, optional expiration timestamp (TTL), and metadata.
    """
    def __init__(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        created_at: Optional[str] = None,
        expire_at: Optional[str] = None,
    ):
        self.key = key
        self.value = value
        self.metadata = dict(metadata) if metadata is not None else {}
        self.created_at = created_at or datetime.now(timezone.utc).isoformat()
        self.expire_at = expire_at

    def is_expired(self) -> bool:
        """Check if this entry has expired relative to current UTC time."""
        if not self.expire_at:
            return False
        try:
            exp = datetime.fromisoformat(self.expire_at)
            now = datetime.now(timezone.utc) if exp.tzinfo else datetime.now()
            return now > exp
        except Exception:
            return False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize memory entry to dictionary."""
        return {
            "key": self.key,
            "value": self.value,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "expire_at": self.expire_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEntry":
        """Deserialize memory entry from dictionary."""
        return cls(
            key=data["key"],
            value=data["value"],
            metadata=data.get("metadata"),
            created_at=data.get("created_at"),
            expire_at=data.get("expire_at"),
        )

    def __repr__(self) -> str:
        return f"MemoryEntry(key='{self.key}', value={self.value}, metadata={self.metadata})"


class BaseMemory(BaseService, ABC):
    """
    Abstract interface for memory systems in the Yasin Ecosystem.
    Inherits from BaseService to manage lifecycle, status, and health reporting.
    """

    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve memory value by key."""
        pass

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> None:
        """
        Store value under key with optional metadata and expiration (ttl in seconds).
        """
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key from memory."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """Clear all entries in memory."""
        pass

    @abstractmethod
    def get_entry(self, key: str) -> Optional[MemoryEntry]:
        """Retrieve the raw MemoryEntry, including its metadata and lifecycle status."""
        pass

    @abstractmethod
    def search(self, query: str) -> List[MemoryEntry]:
        """Search memory entries containing query in key, value, or metadata."""
        pass

    @abstractmethod
    def filter(self, metadata_filters: Dict[str, Any]) -> List[MemoryEntry]:
        """Filter memory entries matching metadata filters."""
        pass


class ShortTermMemory(BaseMemory, ABC):
    """Base abstraction for short-term memory providers."""
    pass


class LongTermMemory(BaseMemory, ABC):
    """Base abstraction for long-term memory providers."""
    pass

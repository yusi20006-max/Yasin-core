from datetime import datetime
import uuid
from typing import Any, Dict, Optional


class Event(dict):
    """
    Standard event model representing an event instance within the Yasin Ecosystem.

    Inherits from dict to maintain 100% backward compatibility with existing subscribers
    and systems that expect a dictionary payload.
    """

    def __init__(
        self,
        name: str,
        payload: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
        event_id: Optional[str] = None
    ):
        self.name = name
        self.payload = payload if payload is not None else {}
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now()
        self.event_id = event_id or str(uuid.uuid4())

        # Ensure core fields are mirrored inside metadata for better context/tracing
        if "event_id" not in self.metadata:
            self.metadata["event_id"] = self.event_id
        if "timestamp" not in self.metadata:
            self.metadata["timestamp"] = self.timestamp.isoformat()

        # Initialize parent dict with payload keys if payload is dictionary-like
        if isinstance(self.payload, dict):
            super().__init__(self.payload)
        else:
            super().__init__()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the event object to a dictionary representation.

        This separates the event model data from transport logic and allows
        future distributed communication or serialization over JSON/transports.
        """
        return {
            "event_id": self.event_id,
            "name": self.name,
            "payload": self.payload,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Event":
        """
        Deserialize a dictionary representation back into an Event object.
        """
        timestamp_str = data.get("timestamp")
        timestamp = None
        if timestamp_str:
            try:
                timestamp = datetime.fromisoformat(timestamp_str)
            except ValueError:
                pass

        return cls(
            name=data.get("name", "unknown"),
            payload=data.get("payload"),
            metadata=data.get("metadata"),
            timestamp=timestamp,
            event_id=data.get("event_id"),
        )

    def __eq__(self, other: Any) -> bool:
        """
        Custom equality check to support backward compatibility.
        If compared with another Event, check by event_id.
        Otherwise, compare against the internal payload directly.
        """
        if isinstance(other, Event):
            return self.event_id == other.event_id
        if isinstance(other, dict) and isinstance(self.payload, dict):
            return super().__eq__(other)
        return self.payload == other

    def __repr__(self) -> str:
        return f"Event(name='{self.name}', id='{self.event_id}', payload={self.payload})"

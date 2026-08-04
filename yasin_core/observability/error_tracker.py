import time
import traceback
import threading
from typing import Dict, Any, List, Optional

class ErrorRecord:
    """Structured representation of a recorded error or exception."""
    def __init__(
        self,
        component: str,
        message: str,
        traceback_str: Optional[str] = None,
        context_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[float] = None
    ):
        self.timestamp = timestamp or time.time()
        self.component = component
        self.message = message
        self.traceback_str = traceback_str
        self.context_id = context_id
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "component": self.component,
            "message": self.message,
            "traceback": self.traceback_str,
            "context_id": self.context_id,
            "metadata": self.metadata,
        }


class ErrorTracker:
    """Thread-safe collector and manager for tracking ecosystem-wide errors and exceptions."""
    def __init__(self, max_errors: int = 500):
        self.max_errors = max_errors
        self._errors: List[ErrorRecord] = []
        self._lock = threading.RLock()

    def record_error(
        self,
        component: str,
        exception: Exception,
        context_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        """Record an exception thread-safely with full stack trace."""
        tb_list = traceback.format_exception(type(exception), exception, exception.__traceback__)
        tb_str = "".join(tb_list)

        record = ErrorRecord(
            component=component,
            message=str(exception),
            traceback_str=tb_str,
            context_id=context_id,
            metadata=metadata
        )

        with self._lock:
            self._errors.append(record)
            if len(self._errors) > self.max_errors:
                self._errors.pop(0)

        return record

    def record_custom_error(
        self,
        component: str,
        message: str,
        traceback_str: Optional[str] = None,
        context_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> ErrorRecord:
        """Record an error directly without raising an exception."""
        record = ErrorRecord(
            component=component,
            message=message,
            traceback_str=traceback_str,
            context_id=context_id,
            metadata=metadata
        )

        with self._lock:
            self._errors.append(record)
            if len(self._errors) > self.max_errors:
                self._errors.pop(0)

        return record

    def get_errors(
        self,
        component: Optional[str] = None,
        context_id: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        limit: Optional[int] = None
    ) -> List[ErrorRecord]:
        """Query and filter recorded errors thread-safely."""
        with self._lock:
            filtered = []
            for record in self._errors:
                if component and record.component != component:
                    continue
                if context_id and record.context_id != context_id:
                    continue
                if start_time and record.timestamp < start_time:
                    continue
                if end_time and record.timestamp > end_time:
                    continue
                filtered.append(record)

            if limit is not None:
                filtered = filtered[-limit:]
            return list(filtered)

    def clear(self) -> None:
        """Clear the recorded errors."""
        with self._lock:
            self._errors.clear()

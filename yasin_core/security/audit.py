import datetime
import threading
from typing import Any, Dict, List, Optional
from yasin_core.utils.logger import get_logger
from yasin_core.events import EventBus

# Security Event constants
SECURITY_EVENT_AUDIT = "security:audit"
SECURITY_ACCESS_GRANTED = "security:access_granted"
SECURITY_ACCESS_DENIED = "security:access_denied"


class AuditLogger:
    """
    Centralized security auditing component.
    Tracks security incidents, grants, and failures, and reports them to the central EventBus.
    """

    def __init__(self, event_bus: Optional[EventBus] = None, max_history_size: int = 200):
        self.logger = get_logger("SECURITY-AUDIT")
        self.event_bus = event_bus
        self.max_history_size = max_history_size
        self._history: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def log_event(
        self,
        action: str,
        subject_id: str,
        subject_type: str,
        resource: str,
        result: str,  # "GRANTED", "DENIED", "ERROR", etc.
        details: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Record a security event, log it, append to history, and dispatch to the EventBus.
        """
        entry = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "action": action,
            "subject_id": subject_id,
            "subject_type": subject_type,
            "resource": resource,
            "result": result,
            "details": details or "",
            "extra": extra or {}
        }

        # Thread-safe append to history
        with self._lock:
            self._history.append(entry)
            if len(self._history) > self.max_history_size:
                self._history.pop(0)

        # Log via system logger
        log_msg = f"[{result}] Subject='{subject_id}' ({subject_type}) performed '{action}' on '{resource}'."
        if details:
            log_msg += f" Details: {details}"

        if result == "DENIED":
            self.logger.warning(log_msg)
        elif result == "ERROR":
            self.logger.error(log_msg)
        else:
            self.logger.info(log_msg)

        # Dispatch to the Event Bus
        if self.event_bus:
            try:
                # Standard audit payload
                self.event_bus.publish(SECURITY_EVENT_AUDIT, data=entry)

                # Specific event payloads
                if result == "GRANTED":
                    self.event_bus.publish(SECURITY_ACCESS_GRANTED, data=entry)
                elif result == "DENIED":
                    self.event_bus.publish(SECURITY_ACCESS_DENIED, data=entry)
            except Exception as e:
                self.logger.debug(f"Failed to publish security audit event to event bus: {e}")

        return entry

    def get_history(
        self,
        limit: Optional[int] = None,
        subject_id: Optional[str] = None,
        result: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Retrieve audit history with optional filtering."""
        with self._lock:
            records = self._history
            if subject_id:
                records = [r for r in records if r["subject_id"] == subject_id]
            if result:
                records = [r for r in records if r["result"] == result]
            if limit is not None:
                records = records[-limit:]
            return list(records)

    def clear_history(self) -> None:
        """Clear audit history."""
        with self._lock:
            self._history.clear()

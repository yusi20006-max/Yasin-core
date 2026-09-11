"""
Shared ecosystem service-observation contracts (Yasin-Core).

Canonical vocabulary and snapshot models for *observed* service state as
reported by the Control Plane. These are read models: they describe what a
service looks like, never how to start/stop it. Lifecycle ownership stays
with YasinHub; Runit stays behind YasinHub.

The status values mirror the ecosystem-verified observation vocabulary
(RUNNING / STOPPED / FAILED / UNKNOWN plus the Hub report states IDLE /
SUCCESS / STALE) so producers and consumers share one language without
copying each other's implementations.

Python 3.9 compatible (no PEP 604 unions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ServiceStatusValue(str, Enum):
    """Observed service states (read-only vocabulary, not commands)."""

    RUNNING = "RUNNING"
    STOPPED = "STOPPED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    IDLE = "IDLE"
    SUCCESS = "SUCCESS"
    STALE = "STALE"


class ControlAction(str, Enum):
    """Lifecycle action names as named in Control Plane verdicts."""

    START = "start"
    STOP = "stop"
    RESTART = "restart"


def coerce_status_value(value: Any) -> ServiceStatusValue:
    """Coerce a string to ServiceStatusValue (case-insensitive). Raises ValueError."""
    if isinstance(value, ServiceStatusValue):
        return value
    if isinstance(value, str) and value.strip().upper() in ServiceStatusValue.__members__:
        return ServiceStatusValue[value.strip().upper()]
    allowed = sorted(member.value for member in ServiceStatusValue)
    raise ValueError(f"Unknown service status {value!r}; expected one of {allowed}.")


def coerce_control_action(value: Any) -> ControlAction:
    """Coerce a string to ControlAction (case-insensitive). Raises ValueError."""
    if isinstance(value, ControlAction):
        return value
    if isinstance(value, str) and value.strip().lower() in ControlAction._value2member_map_:
        return ControlAction(value.strip().lower())
    allowed = sorted(member.value for member in ControlAction)
    raise ValueError(f"Unknown control action {value!r}; expected one of {allowed}.")


def _validate_pid(pid: Optional[int], field_name: str = "pid") -> None:
    if pid is None:
        return
    if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
        raise ValueError(f"{field_name} must be a positive integer PID or None.")


@dataclass
class ServiceStatus:
    """Observed snapshot of one managed service (Control Plane truth)."""

    name: str
    status: ServiceStatusValue = ServiceStatusValue.UNKNOWN
    pid: Optional[int] = None
    running: bool = False
    message: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise ValueError when the snapshot is malformed."""
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("ServiceStatus.name must be a non-empty string.")
        if not isinstance(self.status, ServiceStatusValue):
            raise ValueError("ServiceStatus.status must be a ServiceStatusValue.")
        _validate_pid(self.pid)
        if not isinstance(self.running, bool):
            raise ValueError("ServiceStatus.running must be a bool.")
        if not isinstance(self.message, str):
            raise ValueError("ServiceStatus.message must be a string.")
        if not isinstance(self.extra, dict):
            raise ValueError("ServiceStatus.extra must be a dict.")

    def to_dict(self) -> Dict[str, Any]:
        """JSON-compatible snapshot."""
        self.validate()
        return {
            "name": self.name,
            "status": self.status.value,
            "pid": self.pid,
            "running": self.running,
            "message": self.message,
            "extra": dict(self.extra),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ServiceStatus":
        """Parse a snapshot dict. Raises ValueError on malformed input."""
        if not isinstance(data, dict):
            raise ValueError("ServiceStatus snapshot must be a dict.")
        snapshot = cls(
            name=data.get("name", ""),
            status=coerce_status_value(data.get("status", "UNKNOWN")),
            pid=data.get("pid"),
            running=bool(data.get("running", False)),
            message=data.get("message", "") or "",
            extra=dict(data.get("extra", {}) or {}),
        )
        snapshot.validate()
        return snapshot


@dataclass
class ControlResult:
    """Verdict of one Control Plane lifecycle operation (already executed).

    A record of what the Control Plane decided and observed — holding one
    never grants the holder any power to start/stop anything.
    """

    service: str
    action: ControlAction
    success: bool
    status: ServiceStatusValue = ServiceStatusValue.UNKNOWN
    pid: Optional[int] = None
    message: str = ""

    def validate(self) -> None:
        """Raise ValueError when the verdict is malformed."""
        if not isinstance(self.service, str) or not self.service.strip():
            raise ValueError("ControlResult.service must be a non-empty string.")
        if not isinstance(self.action, ControlAction):
            raise ValueError("ControlResult.action must be a ControlAction.")
        if not isinstance(self.success, bool):
            raise ValueError("ControlResult.success must be a bool.")
        if not isinstance(self.status, ServiceStatusValue):
            raise ValueError("ControlResult.status must be a ServiceStatusValue.")
        _validate_pid(self.pid)
        if not isinstance(self.message, str):
            raise ValueError("ControlResult.message must be a string.")

    def to_dict(self) -> Dict[str, Any]:
        """JSON-compatible verdict."""
        self.validate()
        return {
            "service": self.service,
            "action": self.action.value,
            "success": self.success,
            "status": self.status.value,
            "pid": self.pid,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ControlResult":
        """Parse a verdict dict. Raises ValueError on malformed input."""
        if not isinstance(data, dict):
            raise ValueError("ControlResult verdict must be a dict.")
        verdict = cls(
            service=data.get("service", ""),
            action=coerce_control_action(data.get("action", "")),
            success=bool(data.get("success", False)),
            status=coerce_status_value(data.get("status", "UNKNOWN")),
            pid=data.get("pid"),
            message=data.get("message", "") or "",
        )
        verdict.validate()
        return verdict


__all__ = [
    "ServiceStatusValue",
    "ControlAction",
    "ServiceStatus",
    "ControlResult",
    "coerce_status_value",
    "coerce_control_action",
]

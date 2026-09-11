"""
Shared ecosystem health contracts (Yasin-Core).

Small, dependency-free observation vocabulary for service health reporting.
No lifecycle, no process control, no transport: producers (Control Plane,
services) report, consumers (CLI, dashboards) read.

Python 3.9 compatible (no PEP 604 unions).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class HealthState(str, Enum):
    """Canonical health verdict for one service."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNHEALTHY = "UNHEALTHY"
    UNKNOWN = "UNKNOWN"


def coerce_health_state(value: Any) -> HealthState:
    """Coerce a string to HealthState (case-insensitive). Raises ValueError."""
    if isinstance(value, HealthState):
        return value
    if isinstance(value, str) and value.strip().upper() in HealthState.__members__:
        return HealthState[value.strip().upper()]
    allowed = sorted(member.value for member in HealthState)
    raise ValueError(f"Unknown health state {value!r}; expected one of {allowed}.")


@dataclass
class HealthReport:
    """Point-in-time health observation for a named service."""

    service: str
    state: HealthState = HealthState.UNKNOWN
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        """Raise ValueError when the report is malformed."""
        if not isinstance(self.service, str) or not self.service.strip():
            raise ValueError("HealthReport.service must be a non-empty string.")
        if not isinstance(self.state, HealthState):
            raise ValueError("HealthReport.state must be a HealthState.")
        if not isinstance(self.message, str):
            raise ValueError("HealthReport.message must be a string.")
        if not isinstance(self.details, dict):
            raise ValueError("HealthReport.details must be a dict.")

    @property
    def is_healthy(self) -> bool:
        """True only for an explicit HEALTHY verdict (never guess)."""
        return self.state is HealthState.HEALTHY

    def to_dict(self) -> Dict[str, Any]:
        """JSON-compatible snapshot (never contains secrets by construction)."""
        self.validate()
        return {
            "service": self.service,
            "state": self.state.value,
            "message": self.message,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HealthReport":
        """Parse a snapshot dict. Raises ValueError on malformed input."""
        if not isinstance(data, dict):
            raise ValueError("HealthReport snapshot must be a dict.")
        report = cls(
            service=data.get("service", ""),
            state=coerce_health_state(data.get("state", "UNKNOWN")),
            message=data.get("message", "") or "",
            details=dict(data.get("details", {}) or {}),
        )
        report.validate()
        return report


__all__ = [
    "HealthState",
    "HealthReport",
    "coerce_health_state",
]

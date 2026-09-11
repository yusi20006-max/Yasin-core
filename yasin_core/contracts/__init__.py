"""
Shared ecosystem contracts (Yasin-Core).

Dependency-free observation vocabulary for the Yasin Ecosystem:

- :mod:`yasin_core.contracts.health` — service health states and reports.
- :mod:`yasin_core.contracts.services` — observed service status snapshots
  and Control Plane operation verdicts (read models only).
- :mod:`yasin_core.contracts.errors` — structured error info with secret
  redaction.

Scope boundary (hard rule): contracts describe observable state. They
grant no lifecycle power — no process control, no Runit logic, no
PID/port ownership checks, no transport. YasinHub remains the sole
Control Plane; YasinCLI remains its client.

Consumers must import these from ``yasin_core.sdk`` (the public boundary),
not from ``yasin_core.contracts`` directly.
"""

from __future__ import annotations

from .errors import ErrorCode, ErrorInfo, coerce_error_code, redact_secrets
from .health import HealthReport, HealthState, coerce_health_state
from .services import (
    ControlAction,
    ControlResult,
    ServiceStatus,
    ServiceStatusValue,
    coerce_control_action,
    coerce_status_value,
)

__all__ = [
    "HealthState",
    "HealthReport",
    "coerce_health_state",
    "ServiceStatusValue",
    "ControlAction",
    "ServiceStatus",
    "ControlResult",
    "coerce_status_value",
    "coerce_control_action",
    "ErrorCode",
    "ErrorInfo",
    "redact_secrets",
    "coerce_error_code",
]

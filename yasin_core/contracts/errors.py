"""
Shared ecosystem error contracts (Yasin-Core).

Minimal, transport-neutral error-info model plus a secret-redaction
primitive shared by every component that reports failures outward
(Control Plane verdicts, CLI output, logs, API errors).

Redaction is best-effort hygiene, not a security boundary: callers must
still avoid placing secrets into messages in the first place.

Python 3.9 compatible (no PEP 604 unions).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """Ecosystem-agnostic failure categories (components map their own
    taxonomies onto these; the enum itself commands nothing)."""

    UNKNOWN = "UNKNOWN"
    INVALID = "INVALID"
    NOT_FOUND = "NOT_FOUND"
    UNAVAILABLE = "UNAVAILABLE"
    TIMEOUT = "TIMEOUT"
    REFUSED = "REFUSED"
    CONFLICT = "CONFLICT"


_SECRET_PATTERN = re.compile(
    r"(token|secret|password|passwd|api[_-]?key|bearer|authorization)(\s*[:=]\s*)\S+",
    re.IGNORECASE,
)
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")


def redact_secrets(text: Any, limit: int = 500) -> str:
    """Redact token-like material from a message. Never raises."""
    try:
        cleaned = _SECRET_PATTERN.sub(r"\1\2***", str(text))
        cleaned = _JWT_PATTERN.sub("***", cleaned)
        return cleaned[:max(1, int(limit))]
    except Exception:
        return "Unknown error."


def coerce_error_code(value: Any) -> ErrorCode:
    """Coerce a string to ErrorCode (case-insensitive). Raises ValueError."""
    if isinstance(value, ErrorCode):
        return value
    if isinstance(value, str) and value.strip().upper() in ErrorCode.__members__:
        return ErrorCode[value.strip().upper()]
    allowed = sorted(member.value for member in ErrorCode)
    raise ValueError(f"Unknown error code {value!r}; expected one of {allowed}.")


@dataclass
class ErrorInfo:
    """Structured, shareable failure description (message redacted at build)."""

    code: ErrorCode = ErrorCode.UNKNOWN
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Redact exactly once at construction; stored form is always safe
        # to log, display, or serialize.
        try:
            self.message = redact_secrets(self.message)
        except Exception:
            self.message = "Unknown error."

    def validate(self) -> None:
        """Raise ValueError when the record is malformed."""
        if not isinstance(self.code, ErrorCode):
            raise ValueError("ErrorInfo.code must be an ErrorCode.")
        if not isinstance(self.message, str):
            raise ValueError("ErrorInfo.message must be a string.")
        if not isinstance(self.details, dict):
            raise ValueError("ErrorInfo.details must be a dict.")

    def to_dict(self) -> Dict[str, Any]:
        """JSON-compatible record (safe to log/display by construction)."""
        self.validate()
        return {
            "code": self.code.value,
            "message": self.message,
            "details": dict(self.details),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorInfo":
        """Parse a record dict. Raises ValueError on malformed input."""
        if not isinstance(data, dict):
            raise ValueError("ErrorInfo record must be a dict.")
        record = cls(
            code=coerce_error_code(data.get("code", "UNKNOWN")),
            message=data.get("message", "") or "",
            details=dict(data.get("details", {}) or {}),
        )
        record.validate()
        return record


__all__ = [
    "ErrorCode",
    "ErrorInfo",
    "redact_secrets",
    "coerce_error_code",
]

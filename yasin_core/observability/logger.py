import json
import logging
import time
from typing import Any, Dict, Optional

class JSONFormatter(logging.Formatter):
    """Custom logging Formatter that outputs log records as structured JSON."""
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt) or time.time(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "line": record.lineno,
        }

        # Merge extra fields if passed via extra={}
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_data.update(record.extra)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def get_structured_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Convenience function to get a structured JSON logger."""
    logger = logging.getLogger(f"YASIN-OBS-{name}")
    logger.setLevel(level)

    # Avoid duplicate handlers if already added
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False

    return logger


class StructuredLogger:
    """Thread-safe high-level wrapper to log structured info directly."""
    def __init__(self, name: str, level: int = logging.INFO):
        self._logger = get_structured_logger(name, level)

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        lvl = getattr(logging, level.upper(), logging.INFO)
        # Pass extra fields using python standard logging extra dict
        self._logger.log(lvl, message, extra={"extra": kwargs})

    def info(self, message: str, **kwargs: Any) -> None:
        self.log("INFO", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        self.log("ERROR", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        self.log("WARNING", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        self.log("DEBUG", message, **kwargs)

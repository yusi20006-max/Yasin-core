import json
import logging
import time
from typing import Any, Dict, Optional

class JSONFormatter(logging.Formatter):
    """Custom logging Formatter that outputs log records as structured JSON."""
    def format(self, record: logging.LogRecord) -> str:
        """
        Serialize a log record as a JSON object containing its metadata, message, extra fields, and exception details when available.
        
        Parameters:
            record (logging.LogRecord): The log record to serialize.
        
        Returns:
            str: The serialized JSON log record.
        """
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
    """
    Create or retrieve a structured JSON logger.
    
    Parameters:
        name (str): Name appended to the logger's `YASIN-OBS-` prefix.
        level (int): Logging threshold for the logger.
    
    Returns:
        logging.Logger: The configured structured logger.
    """
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
        """Initialize a structured logger with the specified name and logging level.
        
        Parameters:
        	name (str): The logger name.
        	level (int): The minimum logging level.
        """
        self._logger = get_structured_logger(name, level)

    def log(self, level: str, message: str, **kwargs: Any) -> None:
        """
        Log a message at the specified severity level with structured fields.
        
        Parameters:
        	level (str): Logging level name; unrecognized names use the INFO level.
        	message (str): Message to log.
        	**kwargs (Any): Additional structured fields associated with the log record.
        """
        lvl = getattr(logging, level.upper(), logging.INFO)
        # Pass extra fields using python standard logging extra dict
        self._logger.log(lvl, message, extra={"extra": kwargs})

    def info(self, message: str, **kwargs: Any) -> None:
        """Log an informational message with optional structured fields.
        
        Parameters:
            message (str): The message to log.
            **kwargs (Any): Additional fields included in the structured log record.
        """
        self.log("INFO", message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log an error-level message with optional structured fields.
        
        Parameters:
        	message (str): The message to log
        	**kwargs (Any): Additional structured fields to include with the log record
        """
        self.log("ERROR", message, **kwargs)

    def warn(self, message: str, **kwargs: Any) -> None:
        """Logs a warning-level message with optional structured fields.
        
        Parameters:
        	message (str): The message to log
        	**kwargs (Any): Additional structured fields to include with the log record
        """
        self.log("WARNING", message, **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log a debug-level message with optional structured fields.
        
        Parameters:
            message (str): The message to log.
            **kwargs (Any): Additional structured fields included with the log record.
        """
        self.log("DEBUG", message, **kwargs)

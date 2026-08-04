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
        """
        Create an error record with its component, message, and optional context.
        
        Parameters:
            component (str): Component where the error occurred.
            message (str): Description of the error.
            traceback_str (Optional[str]): Formatted traceback associated with the error.
            context_id (Optional[str]): Identifier for the related execution context.
            metadata (Optional[Dict[str, Any]]): Additional structured information.
            timestamp (Optional[float]): Error timestamp, or the current time when omitted.
        """
        self.timestamp = timestamp or time.time()
        self.component = component
        self.message = message
        self.traceback_str = traceback_str
        self.context_id = context_id
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the error record into a dictionary.
        
        Returns:
        	dict: The record's timestamp, component, message, traceback, context ID, and metadata.
        """
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
        """
        Initialize an error tracker with a maximum number of retained records.
        
        Parameters:
            max_errors (int): Maximum number of error records to retain.
        """
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
        """
        Record an exception with its message, stack trace, and associated context.
        
        Parameters:
        	component (str): The component where the exception occurred.
        	exception (Exception): The exception to record.
        	context_id (Optional[str]): An identifier for the related execution context.
        	metadata (Optional[Dict[str, Any]]): Additional metadata associated with the error.
        
        Returns:
        	ErrorRecord: The recorded error.
        """
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
        """Record an error using a supplied message and optional diagnostic context.
        
        Parameters:
            traceback_str (Optional[str]): Formatted traceback associated with the error.
            context_id (Optional[str]): Identifier for the context in which the error occurred.
            metadata (Optional[Dict[str, Any]]): Additional structured information about the error.
        
        Returns:
            ErrorRecord: The recorded error.
        """
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
        """
        Query recorded errors using optional component, context, and time filters.
        
        Parameters:
        	component (str, optional): Component name to match.
        	context_id (str, optional): Context identifier to match.
        	start_time (float, optional): Earliest timestamp to include.
        	end_time (float, optional): Latest timestamp to include.
        	limit (int, optional): Maximum number of most recent matching records to return.
        
        Returns:
        	List[ErrorRecord]: Matching error records.
        """
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

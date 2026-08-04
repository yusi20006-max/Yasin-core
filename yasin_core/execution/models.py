import time
import uuid
import threading
from enum import Enum
from typing import Any, Dict, Optional, Union, Callable, Tuple, List


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobPriority(int, Enum):
    LOW = 10
    NORMAL = 20
    HIGH = 30
    CRITICAL = 40


class Job:
    """
    Unified model representing a workload/task inside the Task Execution Engine.
    Exposes thread-safe property access and mutation.
    """

    def __init__(
        self,
        target: Union[Callable, str],
        args: Optional[Tuple[Any, ...]] = None,
        kwargs: Optional[Dict[str, Any]] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        priority: Union[int, JobPriority] = JobPriority.NORMAL,
        retries: int = 0,
        timeout: Optional[float] = None,
        context_id: Optional[str] = None,
    ):
        self._lock = threading.RLock()
        self._id = id or str(uuid.uuid4())
        self._name = name or f"job-{self._id[:8]}"
        self._target = target
        self._args = tuple(args) if args is not None else ()
        self._kwargs = dict(kwargs) if kwargs is not None else {}
        self._priority = int(priority)
        self._retries = retries
        self._retry_count = 0
        self._timeout = timeout
        self._status = JobStatus.PENDING
        self._result = None
        self._error = None
        self._created_at = time.time()
        self._started_at = None
        self._completed_at = None
        self._context_id = context_id
        self._cancelled = False
        self._worker_id = kwargs.get("worker_id") if kwargs else None

    @property
    def id(self) -> str:
        return self._id

    @property
    def name(self) -> str:
        return self._name

    @property
    def target(self) -> Union[Callable, str]:
        return self._target

    @property
    def args(self) -> Tuple[Any, ...]:
        return self._args

    @property
    def kwargs(self) -> Dict[str, Any]:
        return self._kwargs

    @property
    def priority(self) -> int:
        with self._lock:
            return self._priority

    @priority.setter
    def priority(self, val: int) -> None:
        with self._lock:
            self._priority = int(val)

    @property
    def retries(self) -> int:
        return self._retries

    @property
    def retry_count(self) -> int:
        with self._lock:
            return self._retry_count

    @retry_count.setter
    def retry_count(self, val: int) -> None:
        with self._lock:
            self._retry_count = val

    @property
    def timeout(self) -> Optional[float]:
        return self._timeout

    @property
    def status(self) -> JobStatus:
        with self._lock:
            return self._status

    @status.setter
    def status(self, val: Union[str, JobStatus]) -> None:
        with self._lock:
            if isinstance(val, str):
                self._status = JobStatus(val.lower())
            else:
                self._status = val

    @property
    def result(self) -> Any:
        with self._lock:
            return self._result

    @result.setter
    def result(self, val: Any) -> None:
        with self._lock:
            self._result = val

    @property
    def error(self) -> Optional[str]:
        with self._lock:
            return self._error

    @error.setter
    def error(self, val: Optional[str]) -> None:
        with self._lock:
            self._error = val

    @property
    def created_at(self) -> float:
        return self._created_at

    @property
    def started_at(self) -> Optional[float]:
        with self._lock:
            return self._started_at

    @started_at.setter
    def started_at(self, val: Optional[float]) -> None:
        with self._lock:
            self._started_at = val

    @property
    def completed_at(self) -> Optional[float]:
        with self._lock:
            return self._completed_at

    @completed_at.setter
    def completed_at(self, val: Optional[float]) -> None:
        with self._lock:
            self._completed_at = val

    @property
    def context_id(self) -> Optional[str]:
        with self._lock:
            return self._context_id

    @context_id.setter
    def context_id(self, val: Optional[str]) -> None:
        with self._lock:
            self._context_id = val

    @property
    def worker_id(self) -> Optional[str]:
        with self._lock:
            return self._worker_id

    @worker_id.setter
    def worker_id(self, val: Optional[str]) -> None:
        with self._lock:
            self._worker_id = val

    @property
    def cancelled(self) -> bool:
        with self._lock:
            return self._cancelled

    def cancel(self) -> bool:
        """
        Mark the job as cancelled if not already finished.
        Returns True if transition to cancelled was successful, False otherwise.
        """
        with self._lock:
            if self._status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                return False
            self._cancelled = True
            self._status = JobStatus.CANCELLED
            self._completed_at = time.time()
            return True

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "id": self._id,
                "name": self._name,
                "target": self._target.__name__ if callable(self._target) else str(self._target),
                "args": list(self._args),
                "kwargs": self._kwargs,
                "priority": self._priority,
                "retries": self._retries,
                "retry_count": self._retry_count,
                "timeout": self._timeout,
                "status": self._status.value,
                "result": self._result,
                "error": self._error,
                "created_at": self._created_at,
                "started_at": self._started_at,
                "completed_at": self._completed_at,
                "context_id": self._context_id,
                "cancelled": self._cancelled,
                "worker_id": self._worker_id,
            }


# Alias for backward or flexible naming compatibility
ExecutionTask = Job

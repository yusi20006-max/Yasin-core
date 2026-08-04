import logging
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Union

from yasin_core.runtime.interfaces import BaseService
from yasin_core.execution.models import Job as ExecutionJob, JobPriority
from yasin_core.events import Event


def parse_cron_field(field: str, min_val: int, max_val: int) -> set:
    """
    Parses a single cron field expression (e.g. *, 1-5, */10)
    and returns a set of valid integer values for that field.
    """
    if field == "*":
        return set(range(min_val, max_val + 1))

    values = set()
    parts = field.split(",")
    for part in parts:
        step = 1
        if "/" in part:
            part, step_str = part.split("/")
            step = int(step_str)

        if part == "*":
            start, end = min_val, max_val
        elif "-" in part:
            start_str, end_str = part.split("-")
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(part)

        values.update(range(start, end + 1, step))
    return values


def get_next_cron_time(cron_expr: str, base_time: Optional[datetime] = None) -> datetime:
    """
    Given a cron expression and a base time, calculates the next run datetime.
    Supports standard 5-field cron format: minute hour day month day_of_week
    """
    if base_time is None:
        base_time = datetime.now()

    # Truncate seconds and microseconds and start from the next minute
    current = base_time.replace(second=0, microsecond=0) + timedelta(minutes=1)

    fields = cron_expr.split()
    if len(fields) != 5:
        raise ValueError("Invalid cron expression. Must have exactly 5 fields.")

    minutes = parse_cron_field(fields[0], 0, 59)
    hours = parse_cron_field(fields[1], 0, 23)
    days = parse_cron_field(fields[2], 1, 31)
    months = parse_cron_field(fields[3], 1, 12)

    # Days of week: 0 to 7 (where 0 or 7 is Sunday, 1 is Monday, etc.)
    days_of_week = parse_cron_field(fields[4], 0, 7)
    if 7 in days_of_week:
        days_of_week.add(0)

    # Search window limit of 100,000 minutes (~70 days) to prevent infinite loops
    for _ in range(100000):
        py_weekday = current.weekday()
        cron_weekday = (py_weekday + 1) % 7

        if (
            current.minute in minutes
            and current.hour in hours
            and current.day in days
            and current.month in months
            and cron_weekday in days_of_week
        ):
            return current
        current += timedelta(minutes=1)

    raise ValueError("Could not determine next run time for cron expression within search window.")


def serialize_target(target: Any) -> Dict[str, Any]:
    """
    Helper to serialize target to a JSON-compatible format.
    """
    if isinstance(target, str):
        return {"type": "str", "val": target}
    elif callable(target):
        return {
            "type": "callable",
            "module": getattr(target, "__module__", None),
            "name": getattr(target, "__name__", None),
        }
    raise TypeError(f"Cannot serialize job target of type {type(target)}")


def deserialize_target(data: Dict[str, Any]) -> Any:
    """
    Helper to deserialize target from a JSON-compatible format.
    """
    if not data:
        return None
    if data["type"] == "str":
        return data["val"]
    elif data["type"] == "callable":
        import importlib
        module_name = data.get("module")
        func_name = data.get("name")
        if module_name and func_name:
            try:
                module = importlib.import_module(module_name)
                return getattr(module, func_name)
            except Exception:
                pass
        return func_name
    raise ValueError(f"Unknown serialized target type: {data.get('type')}")


class ScheduledJob:
    """
    Thread-safe model representing a scheduled background job in Yasin-Core.
    """

    def __init__(
        self,
        target: Union[Callable, str],
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        priority: Union[int, JobPriority] = JobPriority.NORMAL,
        retries: int = 0,
        timeout: Optional[float] = None,
        # Scheduling parameters
        interval: Optional[float] = None,
        delay: Optional[float] = None,
        cron: Optional[str] = None,
        max_runs: Optional[int] = None,
        next_run_time: Optional[float] = None,
        run_count: int = 0,
        last_run_time: Optional[float] = None,
        created_at: Optional[float] = None,
    ):
        self.id = id or str(uuid.uuid4())
        self.name = name or f"sched-job-{self.id[:8]}"
        self.target = target
        self.args = tuple(args) if args is not None else ()
        self.kwargs = dict(kwargs) if kwargs is not None else {}
        self.priority = int(priority)
        self.retries = retries
        self.timeout = timeout

        self.interval = interval
        self.delay = delay
        self.cron = cron
        self.max_runs = max_runs
        self.run_count = run_count

        self.created_at = created_at or time.time()
        self.last_run_time = last_run_time
        self._lock = threading.RLock()
        self.cancelled = False

        if next_run_time is not None:
            self.next_run_time = next_run_time
        else:
            self.calculate_next_run()

    def calculate_next_run(self) -> None:
        """
        Calculates and schedules the next execution time for the job.
        """
        with self._lock:
            if self.cancelled:
                self.next_run_time = None
                return

            if self.max_runs is not None and self.run_count >= self.max_runs:
                self.next_run_time = None
                return

            now = time.time()
            if self.run_count == 0:
                if self.delay is not None:
                    self.next_run_time = now + self.delay
                elif self.cron is not None:
                    self.next_run_time = get_next_cron_time(
                        self.cron, datetime.fromtimestamp(now)
                    ).timestamp()
                elif self.interval is not None:
                    self.next_run_time = now + self.interval
                else:
                    self.next_run_time = now
            else:
                if self.cron is not None:
                    self.next_run_time = get_next_cron_time(
                        self.cron, datetime.fromtimestamp(now)
                    ).timestamp()
                elif self.interval is not None:
                    self.next_run_time = now + self.interval
                else:
                    self.next_run_time = None

    def cancel(self) -> None:
        """
        Cancels scheduling of the job.
        """
        with self._lock:
            self.cancelled = True
            self.next_run_time = None

    def to_dict(self) -> dict:
        """
        Returns JSON-compatible representation of the job.
        """
        with self._lock:
            return {
                "id": self.id,
                "name": self.name,
                "target": serialize_target(self.target),
                "args": list(self.args),
                "kwargs": self.kwargs,
                "priority": self.priority,
                "retries": self.retries,
                "timeout": self.timeout,
                "interval": self.interval,
                "delay": self.delay,
                "cron": self.cron,
                "max_runs": self.max_runs,
                "run_count": self.run_count,
                "created_at": self.created_at,
                "last_run_time": self.last_run_time,
                "next_run_time": self.next_run_time,
                "cancelled": self.cancelled,
            }


class Scheduler(BaseService):
    """
    Centralized Scheduler & Background Jobs System service in Yasin-Core.
    Manages periodic tasks, cron schedules, delayed runs, state tracking, and persistence.
    """

    def __init__(self, client: Any = None):
        super().__init__()
        self.client = client
        self._lock = threading.RLock()
        self._jobs: Dict[str, ScheduledJob] = {}
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.logger = logging.getLogger("YASIN-SCHEDULER")
        self._total_triggers = 0

    def initialize(self) -> None:
        """
        Initializes the Scheduler. Starts background polling thread and loads saved schedules.
        """
        with self._lock:
            if self._thread and self._thread.is_alive():
                self.logger.warning("Scheduler is already initialized and running.")
                return

            self._stop_event.clear()
            self._load_schedule()

            self._thread = threading.Thread(
                target=self._run_loop, name="yasin-scheduler-thread", daemon=True
            )
            self._thread.start()
            self.logger.info("Scheduler service successfully started.")

    def shutdown(self) -> None:
        """
        Gracefully shuts down the Scheduler. Stops the polling thread.
        """
        with self._lock:
            if not self._thread:
                return

            self.logger.info("Stopping Scheduler service.")
            self._stop_event.set()

        self._thread.join(timeout=3.0)
        if self._thread and self._thread.is_alive():
            self.logger.warning("Scheduler background thread did not stop within the 3.0s timeout.")
        self._thread = None
        self.logger.info("Scheduler service stopped successfully.")

    def reload(self) -> None:
        """
        Reloads persistent configuration and active schedules dynamically.
        """
        with self._lock:
            self.logger.info("Reloading scheduler state.")
            self._load_schedule()

    def schedule_job(
        self,
        target: Union[Callable, str],
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        id: Optional[str] = None,
        name: Optional[str] = None,
        priority: Union[int, JobPriority] = JobPriority.NORMAL,
        retries: int = 0,
        timeout: Optional[float] = None,
        interval: Optional[float] = None,
        delay: Optional[float] = None,
        cron: Optional[str] = None,
        max_runs: Optional[int] = None,
    ) -> ScheduledJob:
        """
        Schedules a job. Automatically calculates next execution time.
        """
        job = ScheduledJob(
            target=target,
            args=args,
            kwargs=kwargs,
            id=id,
            name=name,
            priority=priority,
            retries=retries,
            timeout=timeout,
            interval=interval,
            delay=delay,
            cron=cron,
            max_runs=max_runs,
        )

        with self._lock:
            self._jobs[job.id] = job
            self._save_schedule()

        self.logger.info(f"Scheduled job {job.id} ({job.name}) added successfully.")
        self._publish_event("job_scheduled", job)
        return job

    def unschedule_job(self, job_id: str) -> bool:
        """
        Unschedule or cancel a job by its unique ID.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            job.cancel()
            self._jobs.pop(job_id, None)
            self._save_schedule()

        self.logger.info(f"Unscheduled job {job_id} successfully.")
        self._publish_event("job_unscheduled", job)
        return True

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """
        Retrieves a scheduled job instance by ID thread-safely.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def list_jobs(self) -> List[ScheduledJob]:
        """
        Lists all registered scheduled jobs thread-safely.
        """
        with self._lock:
            return list(self._jobs.values())

    def clear_jobs(self) -> None:
        """
        Clears all jobs that are cancelled or finished.
        """
        with self._lock:
            to_remove = [jid for jid, j in self._jobs.items() if j.cancelled or j.next_run_time is None]
            for jid in to_remove:
                self._jobs.pop(jid, None)
            self._save_schedule()

    def health(self) -> Dict[str, Any]:
        """
        Returns structured health check report.
        """
        with self._lock:
            healthy = self._thread is not None and self._thread.is_alive()
            return {
                "healthy": healthy,
                "status": "healthy" if healthy else "stopped",
                "total_jobs": len(self._jobs),
            }

    def status(self) -> Dict[str, Any]:
        """
        Returns structured metrics status report.
        """
        with self._lock:
            active_jobs = sum(1 for j in self._jobs.values() if j.next_run_time is not None)
            return {
                "state": "active" if (self._thread and self._thread.is_alive()) else "inactive",
                "total_scheduled": len(self._jobs),
                "active_schedules": active_jobs,
                "total_triggers": self._total_triggers,
            }

    def _run_loop(self) -> None:
        """
        Internal background polling loop. Tick-based evaluation of job runs.
        """
        while not self._stop_event.is_set():
            try:
                self._tick()
            except Exception as e:
                self.logger.error(f"Error in scheduler tick: {e}", exc_info=True)
            time.sleep(0.1)  # High resolution sub-second check

    def _tick(self) -> None:
        """
        Evaluates and triggers any scheduled jobs whose execution time has passed.
        """
        now = time.time()
        triggered_jobs: List[ScheduledJob] = []

        with self._lock:
            for job in self._jobs.values():
                if job.next_run_time is not None and job.next_run_time <= now and not job.cancelled:
                    triggered_jobs.append(job)

        for job in triggered_jobs:
            self._trigger_job(job)

    def _trigger_job(self, job: ScheduledJob) -> None:
        """
        Constructs and triggers execution of a scheduled job in the TaskExecutionEngine.
        """
        if self.client and hasattr(self.client, "execution") and self.client.execution:
            exec_job = ExecutionJob(
                target=job.target,
                args=job.args,
                kwargs=job.kwargs,
                name=job.name,
                priority=job.priority,
                retries=job.retries,
                timeout=job.timeout,
            )

            self.logger.info(f"Triggering scheduled job {job.id} ({job.name}) on Task Execution Engine.")
            self.client.execution.submit_job(exec_job)

            with job._lock:
                job.run_count += 1
                job.last_run_time = time.time()
                job.calculate_next_run()

            with self._lock:
                self._total_triggers += 1

            self._publish_event("job_triggered", job)
            self._save_schedule()
        else:
            self.logger.error(f"Cannot execute scheduled job {job.id}: Task Execution Engine is not available.")

    def _save_schedule(self) -> None:
        """
        Persists active scheduled jobs to BaseStorage if integrated.
        """
        if self.client and hasattr(self.client, "storage") and self.client.storage:
            try:
                serialized = {}
                with self._lock:
                    for jid, job in self._jobs.items():
                        if not job.cancelled and job.next_run_time is not None:
                            try:
                                serialized[jid] = job.to_dict()
                            except Exception as e:
                                self.logger.error(f"Failed to serialize job {jid}: {e}")

                self.client.storage.set("scheduler:schedule", serialized)
                self.logger.debug("Scheduler schedule state successfully persisted.")
            except Exception as e:
                self.logger.error(f"Failed to save scheduler schedule: {e}")

    def _load_schedule(self) -> None:
        """
        Loads saved scheduled jobs from BaseStorage if integrated.
        """
        if self.client and hasattr(self.client, "storage") and self.client.storage:
            try:
                saved = self.client.storage.get("scheduler:schedule")
                if saved and isinstance(saved, dict):
                    with self._lock:
                        for jid, data in saved.items():
                            try:
                                # Re-construct target and arguments safely
                                target = deserialize_target(data["target"])
                                job = ScheduledJob(
                                    target=target,
                                    args=tuple(data.get("args", ())),
                                    kwargs=data.get("kwargs", {}),
                                    id=data.get("id"),
                                    name=data.get("name"),
                                    priority=data.get("priority", JobPriority.NORMAL),
                                    retries=data.get("retries", 0),
                                    timeout=data.get("timeout"),
                                    interval=data.get("interval"),
                                    delay=data.get("delay"),
                                    cron=data.get("cron"),
                                    max_runs=data.get("max_runs"),
                                    next_run_time=data.get("next_run_time"),
                                    run_count=data.get("run_count", 0),
                                    last_run_time=data.get("last_run_time"),
                                    created_at=data.get("created_at"),
                                )
                                self._jobs[job.id] = job
                            except Exception as e:
                                self.logger.error(f"Failed to deserialize job {jid}: {e}")
                    self.logger.info(f"Successfully loaded {len(self._jobs)} scheduled jobs from storage.")
            except Exception as e:
                self.logger.error(f"Failed to load scheduler schedule from storage: {e}")

    def _publish_event(self, event_name: str, job: ScheduledJob) -> None:
        """
        Publishes detailed job lifecycle events to the central Event Bus.
        """
        if self.client and hasattr(self.client, "event_bus") and self.client.event_bus:
            try:
                event = Event(
                    name=event_name,
                    payload={
                        "job_id": job.id,
                        "job_name": job.name,
                        "interval": job.interval,
                        "cron": job.cron,
                        "delay": job.delay,
                        "next_run_time": job.next_run_time,
                        "run_count": job.run_count,
                        "job": job.to_dict(),
                    },
                )
                self.client.event_bus.publish(event_name, event)
            except Exception as e:
                self.logger.error(f"Failed to publish scheduler event '{event_name}': {e}")

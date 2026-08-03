import logging
import threading
from typing import Dict, Any, List, Optional, Union, Callable

from yasin_core.runtime.interfaces import BaseService
from yasin_core.events import Event
from .models import Job, JobStatus
from .queue import JobQueue
from .worker import JobWorker


class TaskExecutionEngine(BaseService):
    """
    Centralized Task Execution Engine service in Yasin-Core.
    Coordinates job queues, worker threads, retries, timeouts,
    cooperative cancellations, event bus publishing, and memory/context integration.
    """

    def __init__(self, client: Any = None):
        super().__init__()
        self.client = client
        self.queue = JobQueue()
        self._lock = threading.RLock()
        self._jobs: Dict[str, Job] = {}
        self._workers: List[JobWorker] = []
        self.logger = logging.getLogger("YASIN-TASK-EXECUTION-ENGINE")

    def initialize(self) -> None:
        """
        Initializes the Task Execution Engine. Starts background workers.
        """
        with self._lock:
            if self._workers:
                self.logger.warning("Task Execution Engine is already initialized/running workers.")
                return

            # Determine number of worker threads to start
            num_workers = 2
            if self.client and hasattr(self.client, "config"):
                try:
                    num_workers = self.client.config.get("execution.workers", 2)
                except Exception:
                    pass

            self.logger.info(f"Initializing Task Execution Engine with {num_workers} workers.")
            for i in range(num_workers):
                worker = JobWorker(name=f"worker-{i}", engine=self)
                worker.start()
                self._workers.append(worker)

    def shutdown(self) -> None:
        """
        Gracefully shuts down the Task Execution Engine. Stops all worker threads.
        """
        with self._lock:
            self.logger.info("Shutting down Task Execution Engine.")
            # Signal stop to all workers
            for worker in self._workers:
                worker.stop()

            # Wait for all workers to finish
            for worker in self._workers:
                worker.join(timeout=2.0)

            self._workers.clear()
            self.queue.clear()
            self.logger.info("Task Execution Engine shut down successfully.")

    def submit_job(self, job: Job) -> Job:
        """
        Submits a job to the execution engine.
        Associates active context, stores the job in the registry, and enqueues it.
        """
        with self._lock:
            # Capture and propagate active context if not already set
            if not job.context_id:
                try:
                    from yasin_core.context.manager import get_current_context
                    from yasin_core.context.engine import RuntimeContext
                    ctx = get_current_context()
                    if ctx and isinstance(ctx, RuntimeContext):
                        job.context_id = ctx.id
                except Exception as e:
                    self.logger.warning(f"Could not propagate active context: {e}")

            # Register the job
            self._jobs[job.id] = job
            job.status = JobStatus.QUEUED

            # Enqueue the job
            self.queue.put(job)
            self.logger.info(f"Job {job.id} ({job.name}) submitted and queued.")
            self._publish_event("job_queued", job)
            return job

    def create_job(
        self,
        target: Union[Callable, str],
        args: Optional[tuple] = None,
        kwargs: Optional[dict] = None,
        name: Optional[str] = None,
        priority: int = 20,
        retries: int = 0,
        timeout: Optional[float] = None,
    ) -> Job:
        """
        Helper method to construct a Job and immediately submit it to the queue.
        """
        job = Job(
            target=target,
            args=args,
            kwargs=kwargs,
            name=name,
            priority=priority,
            retries=retries,
            timeout=timeout,
        )
        return self.submit_job(job)

    def get_job(self, job_id: str) -> Optional[Job]:
        """
        Retrieves a job by its unique ID thread-safely.
        """
        with self._lock:
            return self._jobs.get(job_id)

    def cancel_job(self, job_id: str) -> bool:
        """
        Cancels a pending or running job by ID.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return False

            success = job.cancel()
            if success:
                self.logger.info(f"Job {job_id} was successfully cancelled.")
                self._publish_event("job_cancelled", job)
            return success

    def list_jobs(self) -> List[Job]:
        """
        Lists all tracked jobs in the registry.
        """
        with self._lock:
            return list(self._jobs.values())

    def clear_jobs(self) -> None:
        """
        Clears all completed, failed, or cancelled jobs from the tracked registry.
        """
        with self._lock:
            active_statuses = (JobStatus.PENDING, JobStatus.QUEUED, JobStatus.RUNNING)
            self._jobs = {jid: j for jid, j in self._jobs.items() if j.status in active_statuses}

    def _execute_target(self, job: Job) -> Any:
        """
        Resolves and executes the job target (Callable, Agent, or Plugin).
        """
        target = job.target
        args = job.args
        kwargs = job.kwargs

        # Case 1: Callable target
        if callable(target):
            return target(*args, **kwargs)

        # Case 2: Target is a string representing a registered Agent or Plugin
        if isinstance(target, str):
            # Check Agent registration
            if self.client and hasattr(self.client, "get_agent"):
                agent = self.client.get_agent(target)
                if agent:
                    if not getattr(agent, "running", False):
                        agent.start()
                    # Resolve payload: can be first positional arg, or kwargs, or empty dict
                    payload = {}
                    if args:
                        if isinstance(args[0], dict):
                            payload = args[0]
                    elif kwargs:
                        payload = kwargs
                    return agent.execute(payload)

            # Check Plugin registration
            if self.client and hasattr(self.client, "get_plugin"):
                plugin = self.client.get_plugin(target)
                if plugin:
                    if hasattr(plugin, "execute"):
                        return plugin.execute(*args, **kwargs)
                    elif hasattr(plugin, "run"):
                        return plugin.run(*args, **kwargs)
                    elif callable(plugin):
                        return plugin(*args, **kwargs)

            raise ValueError(
                f"Target string '{target}' could not be resolved to any registered Agent or Plugin."
            )

        raise TypeError(f"Unsupported job target type: {type(target)}")

    def _publish_event(self, event_name: str, job: Job) -> None:
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
                        "status": job.status.value,
                        "result": job.result,
                        "error": job.error,
                        "priority": job.priority,
                        "retry_count": job.retry_count,
                        "context_id": job.context_id,
                        "job": job.to_dict(),
                    },
                )
                self.client.event_bus.publish(event_name, event)
            except Exception as e:
                self.logger.error(f"Failed to publish execution event '{event_name}': {e}")

    def _save_to_memory(self, job: Job) -> None:
        """
        Saves job results/failures to Short-Term Memory if integrated.
        """
        if self.client and hasattr(self.client, "save_memory"):
            try:
                key = f"job_execution:{job.id}"
                metadata = {
                    "job_id": job.id,
                    "job_name": job.name,
                    "status": job.status.value,
                    "completed_at": job.completed_at,
                }
                if job.context_id:
                    metadata["context_id"] = job.context_id

                value = {
                    "result": job.result,
                    "error": job.error,
                    "status": job.status.value,
                }
                self.client.save_memory(
                    key=key,
                    value=value,
                    category="short-term",
                    metadata=metadata,
                )
            except Exception as e:
                self.logger.error(f"Failed to save job execution results to memory: {e}")

    def health(self) -> Dict[str, Any]:
        """
        Provides health report for the service.
        """
        with self._lock:
            # Active if we have workers initialized
            healthy = len(self._workers) > 0
            return {
                "healthy": healthy,
                "status": "healthy" if healthy else "degraded",
                "worker_count": len(self._workers),
            }

    def status(self) -> Dict[str, Any]:
        """
        Provides structured status report for the service.
        """
        with self._lock:
            pending_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.PENDING)
            queued_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.QUEUED)
            running_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.RUNNING)
            completed_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.COMPLETED)
            failed_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.FAILED)
            cancelled_count = sum(1 for j in self._jobs.values() if j.status == JobStatus.CANCELLED)

            return {
                "state": "active" if self._workers else "inactive",
                "total_workers": len(self._workers),
                "queue_size": self.queue.size(),
                "jobs": {
                    "total": len(self._jobs),
                    "pending": pending_count,
                    "queued": queued_count,
                    "running": running_count,
                    "completed": completed_count,
                    "failed": failed_count,
                    "cancelled": cancelled_count,
                },
            }

import queue
import time
import logging
import threading
from typing import Any, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from .models import Job, JobStatus


class JobWorker(threading.Thread):
    """
    Worker thread that pulls jobs from the queue and executes them safely,
    supporting timeouts, cooperative cancellation, retries, and context propagation.
    """

    def __init__(self, name: str, engine: Any):
        super().__init__(name=name, daemon=True)
        self.engine = engine
        self.logger = logging.getLogger(f"YASIN-TASK-WORKER-{name}")
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """
        Signals the worker thread to stop after its current job is processed.
        """
        self._stop_event.set()

    def run(self) -> None:
        self.logger.info(f"Worker {self.name} started.")
        while not self._stop_event.is_set():
            try:
                # Poll with a small timeout to allow checking self._stop_event regularly
                job = self.engine.queue.get(timeout=0.5)
            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error reading from queue: {e}")
                continue

            # Process the retrieved job
            try:
                self._process_job(job)
            except Exception as e:
                self.logger.error(f"Unhandled error processing job {job.id}: {e}")

    def _process_job(self, job: Job) -> None:
        # Check cooperative cancellation before running
        if job.cancelled or job.status == JobStatus.CANCELLED:
            self.logger.info(f"Job {job.id} was cancelled before execution.")
            job.status = JobStatus.CANCELLED
            job.completed_at = time.time()
            self.engine._publish_event("job_cancelled", job)
            return

        job.status = JobStatus.RUNNING
        job.started_at = time.time()
        self.engine._publish_event("job_started", job)

        # Context propagation setup
        context_engine = getattr(self.engine.client, "context_engine", None)
        active_context_mgr = None
        current_ctx = None

        if context_engine and job.context_id:
            current_ctx = context_engine.get_context(job.context_id)

        if current_ctx:
            # Activate context inside the worker thread
            from yasin_core.context.manager import active_context
            active_context_mgr = active_context(current_ctx)
            active_context_mgr.__enter__()

        try:
            # Execute with timeout management
            result = self._execute_with_timeout(job)

            # Successful completion
            job.result = result
            job.status = JobStatus.COMPLETED
            job.completed_at = time.time()

            self.engine._publish_event("job_completed", job)
            self.engine._save_to_memory(job)

        except Exception as e:
            # Check for retry capability
            if job.retry_count < job.retries:
                job.retry_count += 1
                job.status = JobStatus.QUEUED
                self.logger.warning(
                    f"Job {job.id} failed with error: {e}. Retrying ({job.retry_count}/{job.retries})..."
                )
                self.engine._publish_event("job_retrying", job)
                self.engine.queue.put(job)
            else:
                # Permenant failure
                job.error = str(e)
                job.status = JobStatus.FAILED
                job.completed_at = time.time()
                self.logger.error(f"Job {job.id} failed permanently: {e}")
                self.engine._publish_event("job_failed", job)
                self.engine._save_to_memory(job)

        finally:
            if active_context_mgr:
                active_context_mgr.__exit__(None, None, None)

    def _execute_with_timeout(self, job: Job) -> Any:
        if job.timeout is None or job.timeout <= 0:
            return self.engine._execute_target(job)

        # Execute inside a background ThreadPool to handle timeouts
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(self.engine._execute_target, job)
            try:
                return future.result(timeout=job.timeout)
            except TimeoutError:
                raise TimeoutError(f"Job execution exceeded timeout of {job.timeout} seconds.")

import time
import logging
import uuid
import threading
from enum import Enum
from typing import Any, Dict, List, Optional, Union
from queue import Queue

from yasin_core.runtime.interfaces import BaseService
from yasin_core.events import Event
from yasin_core.execution.models import Job, JobStatus

class WorkerState(str, Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    OFFLINE = "offline"
    SUSPENDED = "suspended"
    FAILED = "failed"

class WorkerNode:
    """
    Represents the centralized metadata and state of a registered worker node.
    """
    def __init__(
        self,
        worker_id: str,
        name: str,
        capabilities: Optional[List[str]] = None,
        health: Optional[Dict[str, Any]] = None,
    ):
        self.id = worker_id
        self.name = name
        self.status = WorkerState.REGISTERED
        self.capabilities = set(capabilities) if capabilities else set()
        self.health = health or {}
        self.last_heartbeat = time.time()
        self.queue: Queue = Queue()
        self.assigned_jobs: Dict[str, Job] = {}
        self._lock = threading.RLock()

    def update_heartbeat(self, health_metrics: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self.last_heartbeat = time.time()
            if health_metrics:
                self.health.update(health_metrics)
            if self.status in (WorkerState.REGISTERED, WorkerState.OFFLINE):
                self.status = WorkerState.ACTIVE

    def is_alive(self, timeout_seconds: float) -> bool:
        with self._lock:
            if self.status in (WorkerState.OFFLINE, WorkerState.FAILED):
                return False
            return (time.time() - self.last_heartbeat) < timeout_seconds

    def report_capability(self, capability: str) -> None:
        with self._lock:
            self.capabilities.add(capability)

    def remove_capability(self, capability: str) -> None:
        with self._lock:
            self.capabilities.discard(capability)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "id": self.id,
                "name": self.name,
                "status": self.status.value,
                "capabilities": list(self.capabilities),
                "health": dict(self.health),
                "last_heartbeat": self.last_heartbeat,
                "assigned_job_count": len(self.assigned_jobs),
                "queue_size": self.queue.qsize(),
            }


class BaseDistributedWorker:
    """
    Base interface and abstract runner for distributed worker execution.
    Can be run in a separate thread, process, or remote system.
    """
    def __init__(
        self,
        name: str,
        manager: Any,  # reference to DistributedWorkerManager or YasinCoreClient
        worker_id: Optional[str] = None,
        capabilities: Optional[List[str]] = None,
        heartbeat_interval: float = 2.0,
    ):
        self.id = worker_id or str(uuid.uuid4())
        self.name = name
        self.manager = manager
        self.capabilities = capabilities or []
        self.heartbeat_interval = heartbeat_interval
        self.logger = logging.getLogger(f"YASIN-DISTRIBUTED-WORKER-{name}")

        self._stop_event = threading.Event()
        self._heartbeat_thread: Optional[threading.Thread] = None
        self._execution_thread: Optional[threading.Thread] = None
        self.status = WorkerState.REGISTERED

    def start(self) -> None:
        """
        Starts the worker lifecycle: registers with manager, starts heartbeat and job pulling.
        """
        self.logger.info(f"Starting worker {self.name} ({self.id}).")
        self._stop_event.clear()

        # Register worker
        self.manager.register_worker(
            worker_id=self.id,
            name=self.name,
            capabilities=self.capabilities,
            health=self._get_system_health()
        )
        self.status = WorkerState.ACTIVE

        # Start heartbeat polling thread
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name=f"worker-heartbeat-{self.id[:8]}",
            daemon=True
        )
        self._heartbeat_thread.start()

        # Start job execution loop thread
        self._execution_thread = threading.Thread(
            target=self._execution_loop,
            name=f"worker-exec-{self.id[:8]}",
            daemon=True
        )
        self._execution_thread.start()

        # Publish event
        self._publish_event("worker_started")

    def stop(self) -> None:
        """
        Stops the worker gracefully and unregisters.
        """
        self.logger.info(f"Stopping worker {self.name} ({self.id}).")
        self._stop_event.set()

        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=2.0)
        if self._execution_thread:
            self._execution_thread.join(timeout=2.0)

        # Unregister from manager
        self.manager.unregister_worker(self.id)
        self.status = WorkerState.OFFLINE
        self._publish_event("worker_stopped")

    def pause(self) -> None:
        """
        Suspends the worker.
        """
        self.status = WorkerState.SUSPENDED
        node = self.manager.get_worker(self.id)
        if node:
            node.status = WorkerState.SUSPENDED
        self._publish_event("worker_suspended")

    def resume(self) -> None:
        """
        Resumes the suspended worker.
        """
        self.status = WorkerState.ACTIVE
        node = self.manager.get_worker(self.id)
        if node:
            node.status = WorkerState.ACTIVE
        self._publish_event("worker_resumed")

    def send_heartbeat(self) -> bool:
        """
        Sends heartbeat and system health metrics to manager.
        """
        health = self._get_system_health()
        return self.manager.send_heartbeat(self.id, health=health)

    def _get_system_health(self) -> Dict[str, Any]:
        """
        Collect system load metrics.
        """
        return {
            "active_threads": threading.active_count(),
            "time": time.time(),
            "status": self.status.value,
        }

    def _heartbeat_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self.status == WorkerState.ACTIVE:
                    self.send_heartbeat()
            except Exception as e:
                self.logger.error(f"Error sending heartbeat: {e}")

            # Sleep in small increments to respond quickly to stop signals
            for _ in range(int(self.heartbeat_interval * 10)):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def _execution_loop(self) -> None:
        while not self._stop_event.is_set():
            if self.status != WorkerState.ACTIVE:
                time.sleep(0.5)
                continue

            try:
                job = self._fetch_job()
                if job:
                    self._execute_job(job)
                else:
                    time.sleep(0.2)
            except Exception as e:
                self.logger.error(f"Error in worker execution loop: {e}")

    def _fetch_job(self) -> Optional[Job]:
        """
        Retrieves the next job assigned to this worker node.
        """
        node = self.manager.get_worker(self.id)
        if node and not node.queue.empty():
            try:
                return node.queue.get_nowait()
            except Exception:
                pass
        return None

    def _execute_job(self, job: Job) -> None:
        self.logger.info(f"Worker {self.id} executing job {job.id} ({job.name}).")

        # Report status: RUNNING
        self.manager.report_job_status(self.id, job.id, JobStatus.RUNNING)

        try:
            if job.cancelled:
                self.manager.report_job_status(self.id, job.id, JobStatus.CANCELLED)
                return

            result = self.execute_task_target(job)
            self.manager.report_job_status(self.id, job.id, JobStatus.COMPLETED, result=result)
        except Exception as e:
            self.logger.error(f"Worker {self.id} failed to execute job {job.id}: {e}")
            self.manager.report_job_status(self.id, job.id, JobStatus.FAILED, error=str(e))

    def execute_task_target(self, job: Job) -> Any:
        """
        Executes the job's target. Can be customized/overridden for Agent execution environments.
        """
        if hasattr(self.manager, "client") and self.manager.client:
            exec_service = self.manager.client.execution
            if exec_service:
                return exec_service._execute_target(job)
        raise ValueError("No execution capability available on the manager client.")

    def _publish_event(self, event_name: str) -> None:
        if hasattr(self.manager, "client") and self.manager.client:
            client = self.manager.client
            if client.event_bus:
                try:
                    event = Event(
                        name=event_name,
                        payload={
                            "worker_id": self.id,
                            "worker_name": self.name,
                            "status": self.status.value,
                            "capabilities": self.capabilities,
                        }
                    )
                    client.event_bus.publish(event_name, event)
                except Exception as e:
                    self.logger.error(f"Failed to publish event {event_name}: {e}")


class DistributedWorkerManager(BaseService):
    """
    Centralized Distributed Worker Manager Service in Yasin-Core.
    Coordinates worker registration, heartbeats, discovery, load balancing,
    and task assignment/routing.
    """
    def __init__(self, client: Any = None):
        super().__init__()
        self.client = client
        self._workers: Dict[str, WorkerNode] = {}
        self._lock = threading.RLock()
        self.logger = logging.getLogger("YASIN-WORKER-MANAGER")

        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self.heartbeat_timeout = 6.0  # Mark offline if no heartbeat for 6 seconds
        self._total_assignments = 0

    def initialize(self) -> None:
        with self._lock:
            if self._monitor_thread and self._monitor_thread.is_alive():
                return

            self._stop_event.clear()
            self._monitor_thread = threading.Thread(
                target=self._monitoring_loop,
                name="yasin-worker-monitor-thread",
                daemon=True
            )
            self._monitor_thread.start()
            self.logger.info("Distributed Worker Manager service successfully started.")

    def shutdown(self) -> None:
        with self._lock:
            if not self._monitor_thread:
                return

            self.logger.info("Stopping Distributed Worker Manager service.")
            self._stop_event.set()

        self._monitor_thread.join(timeout=3.0)
        self._monitor_thread = None

        with self._lock:
            for worker_id, node in list(self._workers.items()):
                node.status = WorkerState.OFFLINE
            self._workers.clear()

        self.logger.info("Distributed Worker Manager service stopped successfully.")

    def register_worker(
        self,
        worker_id: str,
        name: str,
        capabilities: Optional[List[str]] = None,
        health: Optional[Dict[str, Any]] = None,
    ) -> WorkerNode:
        with self._lock:
            node = WorkerNode(worker_id, name, capabilities, health)
            self._workers[worker_id] = node
            self.logger.info(f"Registered distributed worker: {name} ({worker_id}).")
            self._publish_event("worker_registered", node)
            return node

    def unregister_worker(self, worker_id: str) -> Optional[WorkerNode]:
        with self._lock:
            node = self._workers.pop(worker_id, None)
            if node:
                node.status = WorkerState.OFFLINE
                self.logger.info(f"Unregistered distributed worker: {node.name} ({worker_id}).")
                self._publish_event("worker_unregistered", node)
            return node

    def get_worker(self, worker_id: str) -> Optional[WorkerNode]:
        with self._lock:
            return self._workers.get(worker_id)

    def list_workers(self, status: Optional[WorkerState] = None) -> List[WorkerNode]:
        with self._lock:
            if status:
                return [w for w in self._workers.values() if w.status == status]
            return list(self._workers.values())

    def discover_workers(self, capability: str) -> List[WorkerNode]:
        """
        Find all active, healthy workers that report a given capability.
        """
        with self._lock:
            active_workers = self.list_workers(WorkerState.ACTIVE)
            matching = []
            for w in active_workers:
                if capability in w.capabilities:
                    matching.append(w)
            return matching

    def send_heartbeat(self, worker_id: str, health: Optional[Dict[str, Any]] = None) -> bool:
        with self._lock:
            node = self._workers.get(worker_id)
            if not node:
                self.logger.warning(f"Heartbeat received for unknown worker: {worker_id}")
                return False

            node.update_heartbeat(health)
            self._publish_event("worker_heartbeat", node)
            return True

    def assign_job(self, job_id: str, worker_id: str) -> bool:
        """
        Manually assign a specific job to a specific worker.
        """
        with self._lock:
            node = self._workers.get(worker_id)
            if not node:
                self.logger.error(f"Cannot assign job {job_id}: worker {worker_id} not found.")
                return False

            if node.status != WorkerState.ACTIVE:
                self.logger.error(f"Cannot assign job {job_id}: worker {worker_id} is not active ({node.status.value}).")
                return False

            if not self.client or not hasattr(self.client, "execution"):
                self.logger.error("No execution service available to fetch job.")
                return False

            job = self.client.execution.get_job(job_id)
            if not job:
                self.logger.error(f"Job {job_id} not found in execution engine.")
                return False

            with node._lock:
                node.assigned_jobs[job_id] = job
                job.worker_id = worker_id
                job.status = JobStatus.QUEUED
                node.queue.put(job)
                self._total_assignments += 1

            self.logger.info(f"Assigned job {job_id} ({job.name}) to worker {node.name} ({worker_id}).")
            self._publish_event("job_assigned", node, job)
            return True

    def assign_job_by_capability(self, job: Job) -> Optional[WorkerNode]:
        """
        Automatically match a job to the most suitable healthy worker based on capabilities.
        Tries to load balance using lowest assigned job count / queue size.
        """
        required_capability = job.kwargs.get("required_capability") or job.kwargs.get("capability")
        if not required_capability:
            if isinstance(job.target, str):
                required_capability = f"target:{job.target}"
            else:
                required_capability = "default"

        with self._lock:
            candidates = self.discover_workers(required_capability)
            if not candidates:
                candidates = self.discover_workers("default")

            if not candidates:
                candidates = self.list_workers(WorkerState.ACTIVE)

            if not candidates:
                self.logger.warning(f"No active distributed workers found to execute job {job.id}.")
                return None

            selected_worker = min(candidates, key=lambda w: len(w.assigned_jobs))
            success = self.assign_job(job.id, selected_worker.id)
            if success:
                return selected_worker
            return None

    def get_assigned_jobs(self, worker_id: str) -> List[Job]:
        with self._lock:
            node = self._workers.get(worker_id)
            if node:
                with node._lock:
                    return list(node.assigned_jobs.values())
            return []

    def report_job_status(
        self,
        worker_id: str,
        job_id: str,
        status: JobStatus,
        result: Optional[Any] = None,
        error: Optional[str] = None
    ) -> bool:
        """
        Called by a worker to update status and/or result of a job.
        Updates the job inside the centralized TaskExecutionEngine.
        """
        with self._lock:
            node = self._workers.get(worker_id)
            if not node:
                self.logger.error(f"Status report for unknown worker: {worker_id}")
                return False

            if not self.client or not hasattr(self.client, "execution"):
                return False

            job = self.client.execution.get_job(job_id)
            if not job:
                self.logger.error(f"Status report for unknown job: {job_id}")
                return False

            with job._lock:
                job.status = status
                if status == JobStatus.RUNNING:
                    job.started_at = time.time()
                elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
                    job.completed_at = time.time()
                    job.result = result
                    job.error = error
                    with node._lock:
                        node.assigned_jobs.pop(job_id, None)

            exec_engine = self.client.execution
            if status == JobStatus.RUNNING:
                exec_engine._publish_event("job_started", job)
            elif status == JobStatus.COMPLETED:
                exec_engine._publish_event("job_completed", job)
                exec_engine._save_to_memory(job)
            elif status == JobStatus.FAILED:
                if job.retry_count < job.retries:
                    job.retry_count += 1
                    job.status = JobStatus.QUEUED
                    self.logger.warning(
                        f"Job {job.id} failed on worker {worker_id}. Retrying ({job.retry_count}/{job.retries})...."
                    )
                    exec_engine._publish_event("job_retrying", job)
                    with node._lock:
                        node.assigned_jobs[job_id] = job
                        node.queue.put(job)
                else:
                    exec_engine._publish_event("job_failed", job)
                    exec_engine._save_to_memory(job)
            elif status == JobStatus.CANCELLED:
                exec_engine._publish_event("job_cancelled", job)

            if self.client and hasattr(self.client, "observability") and self.client.observability:
                try:
                    counter = self.client.observability.metrics.counter(
                        name="yasin_distributed_worker_job_processed_total",
                        description="Total number of jobs processed by distributed workers",
                        labels={"worker_id": worker_id, "status": status.value}
                    )
                    counter.inc()
                except Exception:
                    pass

            return True

    def monitor_workers(self) -> None:
        """
        Sweeps registered workers, checking for stale heartbeats.
        Transition stale workers to OFFLINE or SUSPENDED.
        Also, handles failure recovery: re-queues unfinished assigned jobs!
        """
        now = time.time()
        stale_threshold = self.heartbeat_timeout

        with self._lock:
            for worker_id, node in list(self._workers.items()):
                if node.status == WorkerState.ACTIVE:
                    if (now - node.last_heartbeat) >= stale_threshold:
                        self.logger.warning(f"Worker {node.name} ({worker_id}) heartbeat stale. Marking SUSPENDED.")
                        node.status = WorkerState.SUSPENDED
                        self._publish_event("worker_suspended", node)

                elif node.status == WorkerState.SUSPENDED:
                    if (now - node.last_heartbeat) >= (stale_threshold * 2):
                        self.logger.warning(f"Worker {node.name} ({worker_id}) heartbeat dead. Marking OFFLINE.")
                        node.status = WorkerState.OFFLINE
                        self._publish_event("worker_offline", node)
                        self._recover_worker_jobs(node)

    def _recover_worker_jobs(self, node: WorkerNode) -> None:
        """
        Re-enqueues unfinished jobs from an offline worker back into the central execution queue.
        """
        with node._lock:
            unfinished_jobs = list(node.assigned_jobs.values())
            node.assigned_jobs.clear()
            while not node.queue.empty():
                try:
                    node.queue.get_nowait()
                except Exception:
                    break

        if unfinished_jobs:
            self.logger.warning(f"Recovering {len(unfinished_jobs)} unfinished jobs from offline worker {node.name}.")
            for job in unfinished_jobs:
                with job._lock:
                    job.status = JobStatus.QUEUED
                    job.worker_id = None

                if self.client and hasattr(self.client, "execution") and self.client.execution:
                    self.client.execution.queue.put(job)
                    self.client.execution._publish_event("job_queued", job)

    def _monitoring_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.monitor_workers()
            except Exception as e:
                self.logger.error(f"Error in worker monitoring loop: {e}")

            for _ in range(10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)

    def health(self) -> Dict[str, Any]:
        with self._lock:
            active_count = len(self.list_workers(WorkerState.ACTIVE))
            healthy = self._monitor_thread is not None and self._monitor_thread.is_alive()
            return {
                "healthy": healthy,
                "status": "healthy" if healthy else "stopped",
                "active_workers": active_count,
                "total_registered_workers": len(self._workers),
            }

    def status(self) -> Dict[str, Any]:
        with self._lock:
            active_count = len(self.list_workers(WorkerState.ACTIVE))
            suspended_count = len(self.list_workers(WorkerState.SUSPENDED))
            offline_count = len(self.list_workers(WorkerState.OFFLINE))

            return {
                "state": "active" if (self._monitor_thread and self._monitor_thread.is_alive()) else "inactive",
                "total_registered_workers": len(self._workers),
                "workers": {
                    "active": active_count,
                    "suspended": suspended_count,
                    "offline": offline_count,
                },
                "total_assignments": self._total_assignments,
            }

    def _publish_event(self, event_name: str, worker: WorkerNode, job: Optional[Job] = None) -> None:
        if self.client and hasattr(self.client, "event_bus") and self.client.event_bus:
            try:
                payload = {
                    "worker_id": worker.id,
                    "worker_name": worker.name,
                    "status": worker.status.value,
                    "capabilities": list(worker.capabilities),
                }
                if job:
                    payload["job_id"] = job.id
                    payload["job_name"] = job.name
                event = Event(name=event_name, payload=payload)
                self.client.event_bus.publish(event_name, event)
            except Exception as e:
                self.logger.error(f"Failed to publish worker event '{event_name}': {e}")

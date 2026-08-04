import time
import pytest
from unittest.mock import MagicMock, patch

from yasin_core.sdk import (
    YasinCoreClient,
    WorkerState,
    WorkerNode,
    BaseDistributedWorker,
    DistributedWorkerManager,
    Job,
    JobStatus,
    Event,
)


def dummy_target(**kwargs):
    return "worker-success"


def dummy_fail_target(**kwargs):
    raise ValueError("worker-failure")


def test_worker_registration_and_unregistration():
    client = YasinCoreClient()
    manager = client.worker_manager

    # Register worker
    node = manager.register_worker(
        worker_id="worker-123",
        name="test-worker",
        capabilities=["agent_run", "default"],
        health={"cpu": 10.0}
    )

    assert node.id == "worker-123"
    assert node.name == "test-worker"
    assert node.status == WorkerState.REGISTERED
    assert "agent_run" in node.capabilities
    assert node.health["cpu"] == 10.0
    assert manager.get_worker("worker-123") == node
    assert len(manager.list_workers()) == 1

    # Send heartbeat
    success = manager.send_heartbeat("worker-123", health={"cpu": 15.0})
    assert success
    assert node.status == WorkerState.ACTIVE
    assert node.health["cpu"] == 15.0

    # Unregister worker
    unreg_node = manager.unregister_worker("worker-123")
    assert unreg_node == node
    assert node.status == WorkerState.OFFLINE
    assert len(manager.list_workers()) == 0


def test_worker_lifecycle_transitions():
    client = YasinCoreClient()
    manager = client.worker_manager

    # Start manager service (not fully starting threads for unit test simplicity)
    worker = BaseDistributedWorker(
        name="lifecycle-worker",
        manager=manager,
        capabilities=["default"],
        heartbeat_interval=0.1
    )

    # Initially registered
    worker.start()
    assert worker.status == WorkerState.ACTIVE

    node = manager.get_worker(worker.id)
    assert node is not None
    assert node.status == WorkerState.ACTIVE

    # Pause worker
    worker.pause()
    assert worker.status == WorkerState.SUSPENDED
    assert node.status == WorkerState.SUSPENDED

    # Resume worker
    worker.resume()
    assert worker.status == WorkerState.ACTIVE
    assert node.status == WorkerState.ACTIVE

    # Stop worker
    worker.stop()
    assert worker.status == WorkerState.OFFLINE
    assert manager.get_worker(worker.id) is None


def test_worker_discovery_by_capabilities():
    client = YasinCoreClient()
    manager = client.worker_manager

    # Register worker 1 with capability 'telegram'
    manager.register_worker(
        worker_id="w1",
        name="worker-telegram",
        capabilities=["telegram"]
    )
    # Register worker 2 with capability 'ai'
    manager.register_worker(
        worker_id="w2",
        name="worker-ai",
        capabilities=["ai"]
    )

    # At this point, both are REGISTERED, discover_workers looks for ACTIVE workers
    # Send heartbeats to activate them
    manager.send_heartbeat("w1")
    manager.send_heartbeat("w2")

    # Discover capability 'telegram'
    tg_workers = manager.discover_workers("telegram")
    assert len(tg_workers) == 1
    assert tg_workers[0].id == "w1"

    # Discover capability 'ai'
    ai_workers = manager.discover_workers("ai")
    assert len(ai_workers) == 1
    assert ai_workers[0].id == "w2"

    # Discover capability 'unknown'
    unknown_workers = manager.discover_workers("unknown")
    assert len(unknown_workers) == 0


def test_heartbeat_timeout_and_monitoring():
    client = YasinCoreClient()
    manager = client.worker_manager

    # Set extremely short timeouts for testing
    manager.heartbeat_timeout = 0.1

    node = manager.register_worker("w1", "timeout-worker")
    manager.send_heartbeat("w1")
    assert node.status == WorkerState.ACTIVE

    # Let time pass
    time.sleep(0.15)
    manager.monitor_workers()
    # Heartbeat is stale -> SUSPENDED
    assert node.status == WorkerState.SUSPENDED

    # Let more time pass (exceed threshold * 2)
    time.sleep(0.15)
    manager.monitor_workers()
    # Stale threshold * 2 -> OFFLINE
    assert node.status == WorkerState.OFFLINE


def test_task_assignment_and_execution_integration():
    client = YasinCoreClient()
    manager = client.worker_manager

    # Initialize execution engine
    client.execution.initialize()

    # Create worker
    worker = BaseDistributedWorker(
        name="exec-worker",
        manager=manager,
        capabilities=["fast_jobs"],
        heartbeat_interval=1.0
    )
    worker.start()

    # Submit job
    job = client.create_job(target=dummy_target, kwargs={"required_capability": "fast_jobs"})

    # Wait for execution to be picked up and processed by the worker
    time.sleep(0.5)

    # Job should be completed successfully on the worker node
    assert job.status == JobStatus.COMPLETED
    assert job.result == "worker-success"
    assert job.worker_id == worker.id

    worker.stop()
    client.execution.shutdown()


def test_task_assignment_routing_failure_recovery():
    client = YasinCoreClient()
    manager = client.worker_manager
    manager.heartbeat_timeout = 0.1

    # Start local workers
    client.execution.initialize()

    # Create worker
    node = manager.register_worker("w-fail", "fail-worker")
    manager.send_heartbeat("w-fail")

    # Submit a job assigned explicitly to this worker
    job = client.create_job(target=dummy_target, kwargs={"worker_id": "w-fail"})
    assert job.worker_id == "w-fail"
    assert job.status == JobStatus.QUEUED

    # Simulate worker goes offline / heartbeat timeout
    time.sleep(0.15)
    manager.monitor_workers()  # Active -> Suspended
    time.sleep(0.15)
    manager.monitor_workers()  # Suspended -> Offline

    assert node.status == WorkerState.OFFLINE
    # The job should be recovered and put back into the central queue
    assert job.worker_id is None
    # Wait for the central/local worker pool to pick up and run the recovered job
    time.sleep(0.3)
    assert job.status == JobStatus.COMPLETED
    assert job.result == "worker-success"

    client.execution.shutdown()


def test_event_bus_notifications():
    client = YasinCoreClient()
    manager = client.worker_manager

    published_events = []

    def on_event(event_name, event):
        published_events.append((event_name, event))

    client.event_bus.subscribe("worker_registered", lambda ev: on_event("worker_registered", ev))
    client.event_bus.subscribe("worker_unregistered", lambda ev: on_event("worker_unregistered", ev))
    client.event_bus.subscribe("job_assigned", lambda ev: on_event("job_assigned", ev))

    # Register
    node = manager.register_worker("w-ev", "event-worker")
    manager.send_heartbeat("w-ev")

    # Assign job
    job = Job(target=dummy_target)
    client.execution._jobs[job.id] = job
    manager.assign_job(job.id, "w-ev")

    # Unregister
    manager.unregister_worker("w-ev")

    event_names = [name for name, _ in published_events]
    assert "worker_registered" in event_names
    assert "job_assigned" in event_names
    assert "worker_unregistered" in event_names


def test_observability_metrics_integration():
    client = YasinCoreClient()
    manager = client.worker_manager
    client.observability.initialize()

    # Register worker and simulate report_job_status completing a job
    node = manager.register_worker("w-metrics", "metrics-worker")
    manager.send_heartbeat("w-metrics")

    job = Job(target=dummy_target)
    client.execution._jobs[job.id] = job
    manager.assign_job(job.id, "w-metrics")

    manager.report_job_status("w-metrics", job.id, JobStatus.COMPLETED, result="metrics-success")

    # Check metrics
    val = client.observability.get_metric_value(
        "yasin_distributed_worker_job_processed_total",
        {"worker_id": "w-metrics", "status": "completed"}
    )
    assert val == 1.0

    client.observability.shutdown()

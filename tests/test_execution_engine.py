import time
import pytest
import threading
from unittest.mock import Mock, patch

from yasin_core.sdk import (
    YasinCoreClient,
    Job,
    ExecutionTask,
    JobStatus,
    JobPriority,
    TaskExecutionEngine,
    get_current_context,
    active_context,
)
from yasin_core.core.runtime import YasinRuntime
from yasin_core.events import Event
from yasin_core.agents import BaseAgent
from yasin_core.plugins import YasinPlugin


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def sample_add(a: int, b: int) -> int:
    return a + b


def sample_failing_func():
    raise ValueError("Simulated failure")


def sample_slow_func(sleep_time: float):
    time.sleep(sleep_time)
    return "done"


class DummyAgent(BaseAgent):
    def __init__(self, name: str):
        super().__init__(name=name)
        self.running = False
        self.executed_with = None

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, payload: dict) -> str:
        self.executed_with = payload
        return f"Agent {self.name} executed with payload: {payload}"


class DummyPlugin(YasinPlugin):
    name = "dummy-plugin"

    def __init__(self, name: str):
        self.name = name

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def execute(self, val: str) -> str:
        return f"Plugin {self.name} execute: {val}"


# ---------------------------------------------------------------------------
# 1. Task/Job Model Creation Tests
# ---------------------------------------------------------------------------

def test_job_model_creation():
    job = Job(target=sample_add, args=(5, 3), kwargs={"name": "test"}, priority=JobPriority.HIGH, retries=3, timeout=5.0)

    assert job.id is not None
    assert job.name.startswith("job-")
    assert job.target == sample_add
    assert job.args == (5, 3)
    assert job.kwargs == {"name": "test"}
    assert job.priority == JobPriority.HIGH
    assert job.retries == 3
    assert job.retry_count == 0
    assert job.timeout == 5.0
    assert job.status == JobStatus.PENDING
    assert job.result is None
    assert job.error is None
    assert job.cancelled is False


def test_job_alias_compatibility():
    # Verify ExecutionTask is an alias for Job
    task = ExecutionTask(target=sample_add, args=(1, 2))
    assert isinstance(task, Job)


# ---------------------------------------------------------------------------
# 2. Priority Queue Sorting Tests
# ---------------------------------------------------------------------------

def test_priority_queue_sorting():
    from yasin_core.execution.queue import JobQueue

    queue = JobQueue()
    job_low = Job(target=sample_add, args=(1, 1), priority=JobPriority.LOW)
    job_normal = Job(target=sample_add, args=(1, 1), priority=JobPriority.NORMAL)
    job_high = Job(target=sample_add, args=(1, 1), priority=JobPriority.HIGH)
    job_critical = Job(target=sample_add, args=(1, 1), priority=JobPriority.CRITICAL)

    # Put in mixed order
    queue.put(job_normal)
    queue.put(job_critical)
    queue.put(job_low)
    queue.put(job_high)

    # Dequeue and verify order: highest first (CRITICAL -> HIGH -> NORMAL -> LOW)
    assert queue.get() is job_critical
    assert queue.get() is job_high
    assert queue.get() is job_normal
    assert queue.get() is job_low


def test_priority_queue_fifo_fallback_on_equal_priorities():
    from yasin_core.execution.queue import JobQueue

    queue = JobQueue()
    # Create two jobs with identical priorities, but different created_at
    job1 = Job(target=sample_add, args=(1, 1), priority=JobPriority.NORMAL)
    time.sleep(0.01)  # Ensure distinct created_at timestamp
    job2 = Job(target=sample_add, args=(2, 2), priority=JobPriority.NORMAL)

    queue.put(job1)
    queue.put(job2)

    # Dequeue - should be job1 (older) then job2 (newer)
    assert queue.get() is job1
    assert queue.get() is job2


# ---------------------------------------------------------------------------
# 3. Job Execution, Worker lifecycle, and Happy Path Tests
# ---------------------------------------------------------------------------

def test_task_execution_happy_path():
    client = YasinCoreClient()
    client.start()  # Initializes TaskExecutionEngine and starts workers

    job = client.create_job(target=sample_add, args=(10, 20), priority=JobPriority.NORMAL)

    # Wait for completion (should be extremely fast)
    timeout = time.time() + 3.0
    while job.status not in (JobStatus.COMPLETED, JobStatus.FAILED) and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.result == 30
    assert job.error is None
    assert job.completed_at is not None
    assert job.started_at is not None

    client.stop()


# ---------------------------------------------------------------------------
# 4. Error Handling and Permanent Failure Tests
# ---------------------------------------------------------------------------

def test_task_execution_failure():
    client = YasinCoreClient()
    client.start()

    job = client.create_job(target=sample_failing_func)

    timeout = time.time() + 3.0
    while job.status not in (JobStatus.COMPLETED, JobStatus.FAILED) and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert job.result is None
    assert "Simulated failure" in job.error

    client.stop()


# ---------------------------------------------------------------------------
# 5. Retry Mechanism Tests
# ---------------------------------------------------------------------------

def test_retry_mechanism():
    client = YasinCoreClient()
    client.start()

    job = client.create_job(target=sample_failing_func, retries=2)

    timeout = time.time() + 3.0
    while job.status not in (JobStatus.COMPLETED, JobStatus.FAILED) and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert job.retry_count == 2  # Retried twice, total 3 execution attempts
    assert "Simulated failure" in job.error

    client.stop()


# ---------------------------------------------------------------------------
# 6. Timeout Management Tests
# ---------------------------------------------------------------------------

def test_timeout_management():
    client = YasinCoreClient()
    client.start()

    # Create a job that sleeps for 2 seconds but has a timeout of 0.2 seconds
    job = client.create_job(target=sample_slow_func, args=(2.0,), timeout=0.2)

    timeout = time.time() + 3.0
    while job.status not in (JobStatus.COMPLETED, JobStatus.FAILED) and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.FAILED
    assert job.result is None
    assert "exceeded timeout of 0.2 seconds" in job.error

    client.stop()


# ---------------------------------------------------------------------------
# 7. Cooperative Cancellation Support Tests
# ---------------------------------------------------------------------------

def test_cooperative_cancellation_queued():
    client = YasinCoreClient()
    # DO NOT start client, so workers are not running, jobs will remain in queue
    job = client.create_job(target=sample_add, args=(1, 2))

    assert job.status == JobStatus.QUEUED

    # Cancel the job
    cancelled = client.cancel_job(job.id)
    assert cancelled is True
    assert job.status == JobStatus.CANCELLED
    assert job.cancelled is True


def test_cooperative_cancellation_running():
    client = YasinCoreClient()
    client.start()

    # Create a slow job
    job = client.create_job(target=sample_slow_func, args=(1.0,))

    # Wait for it to start running
    timeout = time.time() + 2.0
    while job.status != JobStatus.RUNNING and time.time() < timeout:
        time.sleep(0.05)

    # Cancel while running
    cancelled = client.cancel_job(job.id)
    # Even if cancelled flag is cooperative, the state transitions correctly
    assert job.cancelled is True

    client.stop()


# ---------------------------------------------------------------------------
# 8. Event Bus Integration Tests
# ---------------------------------------------------------------------------

def test_event_bus_integration():
    client = YasinCoreClient()

    received_events = []
    def on_event(event):
        received_events.append(event)

    client.event_bus.subscribe("job_queued", on_event)
    client.event_bus.subscribe("job_started", on_event)
    client.event_bus.subscribe("job_completed", on_event)

    client.start()
    job = client.create_job(target=sample_add, args=(5, 5))

    timeout = time.time() + 3.0
    while job.status != JobStatus.COMPLETED and time.time() < timeout:
        time.sleep(0.1)
    time.sleep(0.2)  # Give event bus time to dispatch events

    # Expecting events: job_queued, job_started, job_completed
    event_names = [e.name for e in received_events]
    assert "job_queued" in event_names
    assert "job_started" in event_names
    assert "job_completed" in event_names

    # Check payload structure
    queued_evt = next(e for e in received_events if e.name == "job_queued")
    assert queued_evt.payload["job_id"] == job.id
    assert queued_evt.payload["job_name"] == job.name
    assert queued_evt.payload["status"] == "queued"

    client.stop()


# ---------------------------------------------------------------------------
# 9. Context Propagation Tests
# ---------------------------------------------------------------------------

def test_context_propagation():
    client = YasinCoreClient()
    client.start()

    # Create a runtime context with specific data
    ctx = client.context_engine.create_context(data={"request_user": "Jules"})

    captured_context_val = None
    def context_checking_target():
        nonlocal captured_context_val
        active_ctx = get_current_context()
        captured_context_val = active_ctx.get("request_user")
        return "success"

    # Submit job inside the active context
    with active_context(ctx):
        job = client.create_job(target=context_checking_target)

    # Wait for completion
    timeout = time.time() + 3.0
    while job.status != JobStatus.COMPLETED and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    # Verify context value was propagated and activated inside the worker thread
    assert captured_context_val == "Jules"
    assert job.context_id == ctx.id

    client.stop()


# ---------------------------------------------------------------------------
# 10. Memory Integration Tests
# ---------------------------------------------------------------------------

def test_memory_integration():
    client = YasinCoreClient()
    client.start()

    job = client.create_job(target=sample_add, args=(40, 2))

    timeout = time.time() + 3.0
    while job.status != JobStatus.COMPLETED and time.time() < timeout:
        time.sleep(0.1)

    # Check if the memory contains the job execution details
    mem_key = f"job_execution:{job.id}"
    mem_val = client.get_memory(key=mem_key, category="short-term")

    assert mem_val is not None
    assert mem_val["status"] == "completed"
    assert mem_val["result"] == 42
    assert mem_val["error"] is None

    client.stop()


# ---------------------------------------------------------------------------
# 11. Agent Integration Tests
# ---------------------------------------------------------------------------

def test_agent_integration():
    client = YasinCoreClient()
    client.start()

    # Register Dummy Agent
    agent = DummyAgent("test-agent")
    client.register_agent(agent)

    # Submit job targeting the agent name
    job = client.create_job(target="test-agent", args=({"input_val": "hello"},))

    timeout = time.time() + 3.0
    while job.status != JobStatus.COMPLETED and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.result == "Agent test-agent executed with payload: {'input_val': 'hello'}"
    assert agent.running is True
    assert agent.executed_with == {"input_val": "hello"}

    client.stop()


# ---------------------------------------------------------------------------
# 12. Plugin Integration Tests
# ---------------------------------------------------------------------------

def test_plugin_integration():
    client = YasinCoreClient()
    client.start()

    # Register Dummy Plugin
    plugin = DummyPlugin("test-plugin")
    client.register_plugin(plugin)

    # Submit job targeting the plugin name
    job = client.create_job(target="test-plugin", args=("plugin-param",))

    timeout = time.time() + 3.0
    while job.status != JobStatus.COMPLETED and time.time() < timeout:
        time.sleep(0.1)

    assert job.status == JobStatus.COMPLETED
    assert job.result == "Plugin test-plugin execute: plugin-param"

    client.stop()


# ---------------------------------------------------------------------------
# 13. Runtime Orchestrator Lifecycle Integration Tests
# ---------------------------------------------------------------------------

def test_runtime_orchestrator_integration():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    assert "execution" in runtime.registry.list_services()

    # Start runtime - should initialize TaskExecutionEngine and background workers
    orchestrator.start()
    execution_service = runtime.registry.get_service("execution")
    assert execution_service.health()["healthy"] is True
    assert execution_service.status()["state"] == "active"
    assert execution_service.status()["total_workers"] == 2

    # Stop runtime - should stop workers
    orchestrator.stop()
    assert execution_service.status()["state"] == "inactive"
    assert execution_service.status()["total_workers"] == 0

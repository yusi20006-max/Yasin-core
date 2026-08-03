import time
import pytest
from unittest.mock import Mock, patch

from yasin_core.core.runtime import YasinRuntime
from yasin_core.core.orchestrator import RuntimeOrchestrator, RuntimeState, OrchestratorError
from yasin_core.sdk import YasinCoreClient
from yasin_core.events import Event, EventBus
from yasin_core.runtime.interfaces import BaseService


class DummyLifecycleService(BaseService):
    def __init__(self, name, sequence_list, fail_on_init=False, fail_on_shutdown=False):
        self.name = name
        self.sequence_list = sequence_list
        self.fail_on_init = fail_on_init
        self.fail_on_shutdown = fail_on_shutdown

    def initialize(self) -> None:
        if self.fail_on_init:
            raise ValueError(f"Simulated init failure on {self.name}")
        self.sequence_list.append(f"init_{self.name}")

    def shutdown(self) -> None:
        if self.fail_on_shutdown:
            raise ValueError(f"Simulated shutdown failure on {self.name}")
        self.sequence_list.append(f"shutdown_{self.name}")

    def status(self):
        return {"custom_key": f"status_{self.name}"}


def test_orchestrator_initial_state():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    assert orchestrator.state == RuntimeState.UNINITIALIZED
    assert not runtime.running

    status = orchestrator.status()
    assert status["state"] == "uninitialized"
    assert not status["running"]


def test_orchestrator_lifecycle_transitions_happy_path():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    # Capture event bus notifications
    events = []
    def on_event(event):
        events.append(event)
    runtime.event_bus.subscribe("runtime_state_changed", on_event)

    # 1. Start the runtime orchestrator
    orchestrator.start()
    assert orchestrator.state == RuntimeState.RUNNING
    assert runtime.running

    # Verify event bus received state changes
    # Expected: uninitialized -> initializing -> running
    assert len(events) >= 2
    assert events[0].payload["new_state"] == "initializing"
    assert events[1].payload["new_state"] == "running"

    # Verify status report
    status = orchestrator.status()
    assert status["running"] is True
    assert status["state"] == "running"
    assert "uptime_seconds" in status
    assert status["uptime_seconds"] >= 0.0

    # Verify health monitoring
    health = orchestrator.health()
    assert health["healthy"] is True
    assert health["state"] == "running"

    # 2. Stop the runtime orchestrator
    events.clear()
    orchestrator.stop()
    assert orchestrator.state == RuntimeState.STOPPED
    assert not runtime.running

    # Expected: running -> shutting_down -> stopped
    assert len(events) >= 2
    assert events[0].payload["new_state"] == "shutting_down"
    assert events[1].payload["new_state"] == "stopped"

    # Status after stop
    status_stop = orchestrator.status()
    assert status_stop["running"] is False
    assert status_stop["state"] == "stopped"


def test_orchestrator_dependency_ordering():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    sequence = []

    # Register three dummy services with dependency relationships:
    # service_c depends on service_b
    # service_b depends on service_a
    service_a = DummyLifecycleService("service_a", sequence)
    service_b = DummyLifecycleService("service_b", sequence)
    service_c = DummyLifecycleService("service_c", sequence)

    # Register them
    runtime.registry.register_service("service_a", service_a, dependencies=[])
    runtime.registry.register_service("service_c", service_c, dependencies=["service_b"])
    runtime.registry.register_service("service_b", service_b, dependencies=["service_a"])

    # Start
    orchestrator.start()
    assert sequence == ["init_service_a", "init_service_b", "init_service_c"]

    # Stop
    sequence.clear()
    orchestrator.stop()
    assert sequence == ["shutdown_service_c", "shutdown_service_b", "shutdown_service_a"]


def test_orchestrator_failure_recovery_on_startup():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    sequence = []
    # Register dummy services; service_b will fail to initialize
    service_a = DummyLifecycleService("service_a", sequence)
    service_b = DummyLifecycleService("service_b", sequence, fail_on_init=True)

    runtime.registry.register_service("service_a", service_a, dependencies=[])
    runtime.registry.register_service("service_b", service_b, dependencies=["service_a"])

    events = []
    runtime.event_bus.subscribe("runtime_failed", events.append)

    # Attempt startup - should raise OrchestratorError and transition to FAILED
    with pytest.raises(OrchestratorError) as exc_info:
        orchestrator.start()

    assert "Startup sequence failed" in str(exc_info.value)
    assert orchestrator.state == RuntimeState.FAILED
    assert len(events) == 1
    assert events[0].payload["new_state"] == "failed"

    # Verify status reflects FAILED state
    status = orchestrator.status()
    assert status["state"] == "failed"
    assert status["running"] is False

    # Check that reload or commands cannot run in FAILED unless started again
    with pytest.raises(OrchestratorError):
        orchestrator.reload()


def test_orchestrator_failure_recovery_on_shutdown():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    sequence = []
    service_a = DummyLifecycleService("service_a", sequence, fail_on_shutdown=True)
    runtime.registry.register_service("service_a", service_a)

    orchestrator.start()
    assert orchestrator.state == RuntimeState.RUNNING

    # Attempt shutdown - should raise and transition to FAILED
    with pytest.raises(OrchestratorError) as exc_info:
        orchestrator.stop()

    assert "Shutdown sequence failed" in str(exc_info.value)
    assert orchestrator.state == RuntimeState.FAILED


def test_orchestrator_command_execution():
    runtime = YasinRuntime()
    orchestrator = runtime.orchestrator

    # Execute 'start' command
    res_start = orchestrator.execute_command("start")
    assert res_start["status"] == "success"
    assert orchestrator.state == RuntimeState.RUNNING

    # Execute 'status' command
    res_status = orchestrator.execute_command("status")
    assert res_status["state"] == "running"

    # Execute 'health' command
    res_health = orchestrator.execute_command("health")
    assert res_health["healthy"] is True

    # Execute 'reload' command
    res_reload = orchestrator.execute_command("reload")
    assert res_reload["status"] == "success"

    # Execute 'stop' command
    res_stop = orchestrator.execute_command("stop")
    assert res_stop["status"] == "success"
    assert orchestrator.state == RuntimeState.STOPPED

    # Invalid command
    with pytest.raises(ValueError):
        orchestrator.execute_command("invalid_action_name")


def test_sdk_client_orchestrator_integration():
    client = YasinCoreClient()
    orchestrator = client.orchestrator

    assert orchestrator is not None
    assert isinstance(orchestrator, RuntimeOrchestrator)

    # Test SDK client wrappers
    client.start()
    assert client.orchestrator.state == RuntimeState.RUNNING

    status = client.status()
    assert status["state"] == "running"

    health = client.health()
    assert health["healthy"] is True

    client.reload()

    client.stop()
    assert client.orchestrator.state == RuntimeState.STOPPED


def test_orchestrator_di_container_lookup():
    runtime = YasinRuntime()
    orchestrator_from_di = runtime.container.resolve(RuntimeOrchestrator)
    assert orchestrator_from_di is runtime.orchestrator

    orchestrator_by_name = runtime.container.resolve("orchestrator")
    assert orchestrator_by_name is runtime.orchestrator

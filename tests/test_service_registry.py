import pytest
import threading
import time
from typing import Dict, Any

from yasin_core.runtime import (
    RuntimeServiceRegistry,
    BaseService,
    ServiceMetadata,
    ServiceState,
    ServiceNotFoundError
)
from yasin_core.core.runtime import YasinRuntime
from yasin_core.sdk import YasinCoreClient


class DummyService(BaseService):
    def __init__(self, state_dict=None, name="dummy"):
        self.name = name
        self.state_dict = state_dict if state_dict is not None else {}
        self.state_dict[f"{name}_init"] = False
        self.state_dict[f"{name}_shutdown"] = False
        self.state_dict[f"{name}_reload"] = False

    def initialize(self) -> None:
        self.state_dict[f"{self.name}_init"] = True

    def shutdown(self) -> None:
        self.state_dict[f"{self.name}_shutdown"] = True

    def reload(self) -> None:
        self.state_dict[f"{self.name}_reload"] = True


def test_registry_registration_and_discovery():
    registry = RuntimeServiceRegistry()
    service = DummyService(name="test_svc")

    registry.register_service(
        name="test_svc",
        service=service,
        version="2.1.0",
        description="A test registry service",
        metadata_dict={"provider": "yasin", "env": "prod"}
    )

    assert registry.has_service("test_svc") is True
    assert registry.get_service("test_svc") is service
    assert registry.list_services() == ["test_svc"]

    meta = registry.get_service_metadata("test_svc")
    assert meta.name == "test_svc"
    assert meta.version == "2.1.0"
    assert meta.description == "A test registry service"
    assert meta.metadata == {"provider": "yasin", "env": "prod"}


def test_registry_missing_service_metadata():
    registry = RuntimeServiceRegistry()
    with pytest.raises(ServiceNotFoundError):
        registry.get_service_metadata("non_existent")


def test_registry_lifecycle_delegation():
    registry = RuntimeServiceRegistry()
    states = {}

    svc_db = DummyService(state_dict=states, name="db")
    svc_auth = DummyService(state_dict=states, name="auth")

    registry.register_service(name="db", service=svc_db)
    registry.register_service(name="auth", service=svc_auth, dependencies=["db"])

    # Initialize
    registry.initialize_services()
    assert states["db_init"] is True
    assert states["auth_init"] is True

    # Reload
    registry.reload_services()
    assert states["db_reload"] is True
    assert states["auth_reload"] is True

    # Shutdown
    registry.shutdown_services()
    assert states["db_shutdown"] is True
    assert states["auth_shutdown"] is True


def test_registry_health_and_status():
    registry = RuntimeServiceRegistry()
    svc = DummyService(name="health_svc")

    registry.register_service(name="health_svc", service=svc)

    status = registry.get_status()
    assert status["initialized"] is False
    assert "health_svc" in status["services"]

    health = registry.get_health()
    assert health["healthy"] is True


def test_registry_thread_safety():
    registry = RuntimeServiceRegistry()
    service = DummyService(name="concurrent")

    # We will register from multiple threads
    errors = []

    def worker(i):
        try:
            # All threads try to register different names
            registry.register_service(name=f"thread_svc_{i}", service=service)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    assert len(registry.list_services()) == 10


def test_runtime_integration():
    runtime = YasinRuntime()
    states = {}
    svc = DummyService(state_dict=states, name="core_svc")

    # Register core service onto the runtime registry
    runtime.registry.register_service(name="core_svc", service=svc)

    # Start runtime should initialize services
    runtime.start()
    assert runtime.running is True
    assert states["core_svc_init"] is True

    status = runtime.status()
    assert status["running"] is True
    assert status["registry"]["initialized"] is True
    assert status["registry"]["services"]["core_svc"]["state"] == "ACTIVE"

    # Stop runtime should shutdown services
    runtime.stop()
    assert runtime.running is False
    assert states["core_svc_shutdown"] is True


def test_sdk_client_access():
    client = YasinCoreClient()
    assert isinstance(client.service_registry, RuntimeServiceRegistry)

    # Can register and discover services directly via SDK
    svc = DummyService(name="sdk_svc")
    client.service_registry.register_service(name="sdk_svc", service=svc)

    assert client.service_registry.has_service("sdk_svc") is True
    assert client.service_registry.get_service("sdk_svc") is svc

import pytest
from typing import Dict, Any

from yasin_core.runtime import (
    RuntimeServiceManager,
    BaseService,
    ServiceMetadata,
    ServiceState,
    DuplicateServiceError,
    ServiceNotFoundError,
    MissingDependencyError,
    CircularDependencyError,
    DependencyError,
    ServiceError
)

# Dummy services to test lifecycle and sequencing
class DummyService(BaseService):
    def __init__(self):
        self.initialized = False
        self.shutdown_called = False
        self.reloaded = False
        self.init_seq = []
        self.shutdown_seq = []

    def initialize(self) -> None:
        self.initialized = True

    def shutdown(self) -> None:
        self.shutdown_called = True

    def reload(self) -> None:
        self.reloaded = True


class RecordingService(DummyService):
    def __init__(self, name: str, init_record: list, shutdown_record: list):
        super().__init__()
        self.name = name
        self.init_record = init_record
        self.shutdown_record = shutdown_record

    def initialize(self) -> None:
        super().initialize()
        self.init_record.append(self.name)

    def shutdown(self) -> None:
        super().shutdown()
        self.shutdown_record.append(self.name)


def test_service_registration_and_lookup():
    manager = RuntimeServiceManager()
    service = DummyService()
    metadata = ServiceMetadata(name="auth", version="1.0.0", description="Auth Service")

    manager.register_service(service, metadata)
    assert manager.has_service("auth") is True
    assert manager.get_service("auth") is service
    assert manager.list_services() == ["auth"]

    status = manager.status()
    assert status["initialized"] is False
    assert status["service_count"] == 1
    assert status["services"]["auth"]["state"] == "UNINITIALIZED"
    assert status["services"]["auth"]["version"] == "1.0.0"


def test_duplicate_registration_error():
    manager = RuntimeServiceManager()
    service1 = DummyService()
    service2 = DummyService()
    metadata = ServiceMetadata(name="auth")

    manager.register_service(service1, metadata)
    with pytest.raises(DuplicateServiceError):
        manager.register_service(service2, metadata)


def test_service_lookup_not_found():
    manager = RuntimeServiceManager()
    with pytest.raises(ServiceNotFoundError):
        manager.get_service("non_existent")


def test_unregister_service():
    manager = RuntimeServiceManager()
    service = DummyService()
    metadata = ServiceMetadata(name="database")

    manager.register_service(service, metadata)
    assert manager.has_service("database") is True

    manager.unregister_service("database")
    assert manager.has_service("database") is False

    with pytest.raises(ServiceNotFoundError):
        manager.unregister_service("database")


def test_unregister_dependent_service_error():
    manager = RuntimeServiceManager()
    service_db = DummyService()
    service_cache = DummyService()

    manager.register_service(service_db, ServiceMetadata(name="db"))
    manager.register_service(service_cache, ServiceMetadata(name="cache", dependencies=["db"]))

    with pytest.raises(DependencyError):
        manager.unregister_service("db")

    # Should succeed after dependent service is unregistered
    manager.unregister_service("cache")
    manager.unregister_service("db")


def test_missing_dependency_detection():
    manager = RuntimeServiceManager()
    service = DummyService()
    # auth depends on redis, but redis is not registered
    metadata = ServiceMetadata(name="auth", dependencies=["redis"])
    manager.register_service(service, metadata)

    with pytest.raises(MissingDependencyError):
        manager.initialize()


def test_circular_dependency_detection():
    manager = RuntimeServiceManager()
    service_a = DummyService()
    service_b = DummyService()

    # A depends on B, and B depends on A
    manager.register_service(service_a, ServiceMetadata(name="A", dependencies=["B"]))
    manager.register_service(service_b, ServiceMetadata(name="B", dependencies=["A"]))

    with pytest.raises(CircularDependencyError):
        manager.initialize()


def test_startup_and_shutdown_ordering():
    manager = RuntimeServiceManager()
    init_order = []
    shutdown_order = []

    # Services: db -> cache -> auth
    db = RecordingService("db", init_order, shutdown_order)
    cache = RecordingService("cache", init_order, shutdown_order)
    auth = RecordingService("auth", init_order, shutdown_order)

    # Register in a non-dependency order to verify sorting is correct
    manager.register_service(auth, ServiceMetadata(name="auth", dependencies=["cache"]))
    manager.register_service(cache, ServiceMetadata(name="cache", dependencies=["db"]))
    manager.register_service(db, ServiceMetadata(name="db"))

    # Initialize
    manager.initialize()
    assert init_order == ["db", "cache", "auth"]
    assert db.initialized is True
    assert cache.initialized is True
    assert auth.initialized is True

    # Status check
    status = manager.status()
    assert status["initialized"] is True
    assert status["services"]["db"]["state"] == "ACTIVE"
    assert status["services"]["cache"]["state"] == "ACTIVE"
    assert status["services"]["auth"]["state"] == "ACTIVE"

    # Shutdown
    manager.shutdown()
    assert shutdown_order == ["auth", "cache", "db"]
    assert db.shutdown_called is True
    assert cache.shutdown_called is True
    assert auth.shutdown_called is True


def test_service_reload():
    manager = RuntimeServiceManager()
    service_a = DummyService()
    service_b = DummyService()

    manager.register_service(service_a, ServiceMetadata(name="A"))
    manager.register_service(service_b, ServiceMetadata(name="B", dependencies=["A"]))

    manager.initialize()
    manager.reload()

    assert service_a.reloaded is True
    assert service_b.reloaded is True


def test_service_initialization_failure():
    class FailingService(BaseService):
        def initialize(self) -> None:
            raise ValueError("Something went wrong")

    manager = RuntimeServiceManager()
    service = FailingService()
    manager.register_service(service, ServiceMetadata(name="failing"))

    with pytest.raises(ServiceError) as exc_info:
        manager.initialize()
    assert "initialization failed" in str(exc_info.value)

    status = manager.status()
    assert status["services"]["failing"]["state"] == "FAILED"


def test_health_reporting():
    class CustomHealthService(BaseService):
        def __init__(self, is_healthy=True):
            self.is_healthy = is_healthy

        def health(self) -> Dict[str, Any]:
            if self.is_healthy:
                return {"status": "healthy", "healthy": True}
            return {"status": "unhealthy", "healthy": False, "reason": "out of disk"}

    manager = RuntimeServiceManager()
    healthy_svc = CustomHealthService(is_healthy=True)
    unhealthy_svc = CustomHealthService(is_healthy=False)

    manager.register_service(healthy_svc, ServiceMetadata(name="healthy_service"))
    manager.register_service(unhealthy_svc, ServiceMetadata(name="unhealthy_service"))

    # Not initialized yet, default health checks won't execute custom health method, state is UNINITIALIZED
    h_report_pre = manager.health()
    assert h_report_pre["healthy"] is True  # Overall manager is healthy because uninitialized services are not failed

    # Initialize
    manager.initialize()
    h_report_post = manager.health()
    assert h_report_post["healthy"] is False
    assert h_report_post["services"]["healthy_service"]["healthy"] is True
    assert h_report_post["services"]["unhealthy_service"]["healthy"] is False
    assert h_report_post["services"]["unhealthy_service"]["details"]["reason"] == "out of disk"

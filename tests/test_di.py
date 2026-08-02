import pytest
from typing import Optional
from yasin_core.di import (
    DIContainer,
    ServiceLifetime,
    DIError,
    DependencyResolutionError,
    CircularDependencyError,
)
from yasin_core.core.runtime import YasinRuntime
from yasin_core.sdk import YasinCoreClient, ContextEngine
from yasin_core.runtime.registry import RuntimeServiceRegistry


# 1. Dummy Classes for Testing Constructor Injection
class Engine:
    pass


class Car:
    def __init__(self, engine: Engine):
        self.engine = engine


class Unregistered:
    pass


class House:
    def __init__(self, room: Unregistered):
        self.room = room


# 2. Dummy Classes for Circular Dependency Testing
class NodeA:
    def __init__(self, b: "NodeB"):
        self.b = b


class NodeB:
    def __init__(self, a: NodeA):
        self.a = a


# 3. Base & Subclass interface testing
class IDatabase:
    pass


class SQLiteDatabase(IDatabase):
    pass


def test_basic_registration_and_resolution():
    container = DIContainer()
    container.register_instance("api_key", "secret123")
    assert container.has("api_key") is True
    assert container.resolve("api_key") == "secret123"

    with pytest.raises(DependencyResolutionError) as exc_info:
        container.resolve("non_existent")
    assert "No service registered for key 'non_existent'" in str(exc_info.value)


def test_lifetimes_singleton_vs_transient():
    container = DIContainer()

    # Singleton
    container.register_singleton("engine", Engine)
    eng1 = container.resolve("engine")
    eng2 = container.resolve("engine")
    assert eng1 is eng2
    assert isinstance(eng1, Engine)

    # Transient
    container.register_transient("transient_engine", Engine)
    eng3 = container.resolve("transient_engine")
    eng4 = container.resolve("transient_engine")
    assert eng3 is not eng4  # Wait, wait! Transient should be DIFFERENT!
    # Ah, let's make sure eng3 is NOT eng4!
    assert eng3 is not eng4


def test_constructor_injection_and_autowiring():
    container = DIContainer()
    container.register_singleton(Engine, Engine)
    container.register_singleton(Car, Car)

    car = container.resolve(Car)
    assert isinstance(car, Car)
    assert isinstance(car.engine, Engine)


def test_autowiring_unregistered_class():
    container = DIContainer()
    container.register_singleton(Engine, Engine)

    # Car is not registered, but we resolve it. The container should autowire it!
    car = container.resolve(Car)
    assert isinstance(car, Car)
    assert isinstance(car.engine, Engine)


def test_parameter_name_injection():
    class App:
        def __init__(self, db_url: str):
            self.db_url = db_url

    container = DIContainer()
    container.register_instance("db_url", "sqlite:///:memory:")

    app = container.resolve(App)
    assert app.db_url == "sqlite:///:memory:"


def test_missing_dependency_exception():
    container = DIContainer()

    # House depends on Unregistered, which is not registered or resolvable
    with pytest.raises(DependencyResolutionError) as exc_info:
        container.resolve(House)

    assert "Cannot resolve parameter 'room'" in str(exc_info.value)


def test_circular_dependency_protection():
    container = DIContainer()
    container.register_singleton(NodeA, NodeA)
    container.register_singleton(NodeB, NodeB)

    with pytest.raises(CircularDependencyError) as exc_info:
        container.resolve(NodeA)

    assert "Circular dependency detected" in str(exc_info.value)


def test_interface_to_implementation_resolution():
    container = DIContainer()
    container.register_singleton(IDatabase, SQLiteDatabase)

    db = container.resolve(IDatabase)
    assert isinstance(db, SQLiteDatabase)


def test_runtime_integration():
    runtime = YasinRuntime()
    assert isinstance(runtime.container, DIContainer)
    assert runtime.container.resolve(YasinRuntime) is runtime
    assert runtime.container.resolve(RuntimeServiceRegistry) is runtime.registry
    assert runtime.container.resolve(ContextEngine) is runtime.context_engine

    status = runtime.status()
    assert "di_container" in status
    assert len(status["di_container"]["registered_services"]) > 0


def test_sdk_client_integration():
    client = YasinCoreClient()
    assert isinstance(client.di_container, DIContainer)
    assert client.di_container.resolve(YasinCoreClient) is client
    assert client.di_container.resolve("client") is client
    assert client.di_container.resolve(RuntimeServiceRegistry) is client.service_registry
    assert client.di_container.resolve(ContextEngine) is client.context_engine

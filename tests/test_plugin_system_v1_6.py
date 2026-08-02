import pytest
from typing import List, Dict, Any

from yasin_core.sdk import YasinCoreClient
from yasin_core.plugins import YasinPlugin, PluginRegistry
from yasin_core.plugins.registry import PluginState
from yasin_core.plugins.exceptions import (
    PluginError,
    PluginDependencyError,
    PluginVersionError,
    PluginNotFoundError,
)
from yasin_core.events import Event


class DummyPlugin(YasinPlugin):
    name = "dummy"
    version = "1.2.3"
    description = "A dummy plugin"
    dependencies: List[str] = []
    core_version_compat = ">=1.0.0"

    def __init__(self):
        self.initialized = False
        self.loaded = False
        self.started = False
        self.unloaded = False

    def initialize(self):
        self.initialized = True

    def load(self):
        self.loaded = True

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def unload(self):
        self.unloaded = True


class DependentPlugin(YasinPlugin):
    name = "dependent"
    version = "2.0.0"
    dependencies = ["dummy"]
    core_version_compat = "^1.5.0"

    def __init__(self):
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False


class IncompatiblePlugin(YasinPlugin):
    name = "incompatible"
    core_version_compat = ">=99.0.0"  # Way ahead of the current core version

    def start(self):
        pass

    def stop(self):
        pass


class CircularAPlugin(YasinPlugin):
    name = "circular_a"
    dependencies = ["circular_b"]

    def start(self): pass
    def stop(self): pass


class CircularBPlugin(YasinPlugin):
    name = "circular_b"
    dependencies = ["circular_a"]

    def start(self): pass
    def stop(self): pass


def test_basic_plugin_registration_and_lifecycle():
    client = YasinCoreClient()
    plugin = DummyPlugin()

    # Before registration
    with pytest.raises(PluginNotFoundError):
        client.get_plugin_state("dummy")

    client.register_plugin(plugin)
    assert client.get_plugin_state("dummy") == "REGISTERED"

    # Load
    client.load_plugin("dummy")
    assert client.get_plugin_state("dummy") == "LOADED"
    assert plugin.initialized is True
    assert plugin.loaded is True

    # Start
    client.start_plugin("dummy")
    assert client.get_plugin_state("dummy") == "ACTIVE"
    assert plugin.started is True

    # Stop
    client.stop_plugin("dummy")
    assert client.get_plugin_state("dummy") == "STOPPED"
    assert plugin.started is False

    # Unload
    client.unload_plugin("dummy")
    assert client.get_plugin_state("dummy") == "REGISTERED"
    assert plugin.unloaded is True


def test_version_compatibility_checking():
    registry = PluginRegistry()

    # Exact match & wildcards
    assert registry.check_version_compatibility("*", "1.6.0") is True
    assert registry.check_version_compatibility("", "1.6.0") is True
    assert registry.check_version_compatibility("1.6.0", "1.6.0") is True

    # Operators
    assert registry.check_version_compatibility(">=1.5.0", "1.6.0") is True
    assert registry.check_version_compatibility(">=2.0.0", "1.6.0") is False
    assert registry.check_version_compatibility("<2.0.0", "1.6.0") is True
    assert registry.check_version_compatibility("<=1.6.0", "1.6.0") is True
    assert registry.check_version_compatibility("==1.6.0", "1.6.0") is True
    assert registry.check_version_compatibility("!=1.5.0", "1.6.0") is True

    # Carat compatibility (same major version, >= specified)
    assert registry.check_version_compatibility("^1.5.0", "1.6.0") is True
    assert registry.check_version_compatibility("^1.5.0", "2.0.0") is False
    assert registry.check_version_compatibility("^2.0.0", "1.6.0") is False


def test_plugin_version_validation_failure():
    client = YasinCoreClient()
    incompat = IncompatiblePlugin()
    client.register_plugin(incompat)

    with pytest.raises(PluginError) as exc:
        client.load_plugin("incompatible")
    assert "incompatible" in str(exc.value)
    assert "requires" in str(exc.value)
    assert client.get_plugin_state("incompatible") == "FAILED"


def test_plugin_dependencies_resolution():
    client = YasinCoreClient()
    dummy = DummyPlugin()
    dep = DependentPlugin()

    client.register_plugin(dummy)
    client.register_plugin(dep)

    # Starting dependent plugin should automatically load and start dummy dependency first
    client.start_plugin("dependent")

    assert client.get_plugin_state("dummy") == "ACTIVE"
    assert client.get_plugin_state("dependent") == "ACTIVE"
    assert dummy.started is True
    assert dep.started is True


def test_plugin_missing_dependency():
    client = YasinCoreClient()
    dep = DependentPlugin()
    client.register_plugin(dep)

    # Cannot load dependent because "dummy" is not registered
    with pytest.raises(PluginError) as exc:
        client.load_plugin("dependent")
    assert "dummy" in str(exc.value)
    assert client.get_plugin_state("dependent") == "FAILED"


def test_circular_dependencies():
    client = YasinCoreClient()
    a = CircularAPlugin()
    b = CircularBPlugin()
    client.register_plugin(a)
    client.register_plugin(b)

    with pytest.raises(PluginError) as exc:
        client.load_plugin("circular_a")
    assert "Circular dependency" in str(exc.value)


def test_plugin_unregistration_safeguard():
    client = YasinCoreClient()
    dummy = DummyPlugin()
    dep = DependentPlugin()

    client.register_plugin(dummy)
    client.register_plugin(dep)

    # Should raise error if trying to unregister dummy while dependent needs it
    with pytest.raises(PluginDependencyError):
        client.unregister_plugin("dummy")

    # Unregister dependent first, then dummy should succeed
    client.unregister_plugin("dependent")
    client.unregister_plugin("dummy")
    assert "dummy" not in client.list_plugins()


def test_runtime_service_manager_integration():
    client = YasinCoreClient()
    dummy = DummyPlugin()
    client.register_plugin(dummy)

    # PluginRegistry should be registered under runtime services
    assert client.service_registry.has_service("plugin_registry") is True

    # Retrieve PluginRegistry status and health
    health_info = client.service_registry.get_health()
    assert "plugin_registry" in health_info["services"]
    assert health_info["services"]["plugin_registry"]["healthy"] is True

    status_info = client.service_registry.get_status()
    assert "plugin_registry" in status_info["services"]

    # Initializing all runtime services should initialize the registered plugins too
    client.service_registry.initialize_services()
    assert client.get_plugin_state("dummy") == "LOADED"


def test_event_bus_integration():
    client = YasinCoreClient()
    events_received = []

    def handle_event(event: Event):
        events_received.append(event)

    client.event_bus.subscribe("plugin_registered", handle_event)
    client.event_bus.subscribe("plugin_loaded", handle_event)
    client.event_bus.subscribe("plugin_started", handle_event)
    client.event_bus.subscribe("plugin_stopped", handle_event)
    client.event_bus.subscribe("plugin_unloaded", handle_event)

    dummy = DummyPlugin()
    client.register_plugin(dummy)
    client.load_plugin("dummy")
    client.start_plugin("dummy")
    client.stop_plugin("dummy")
    client.unload_plugin("dummy")

    event_names = [e.name for e in events_received]
    assert "plugin_registered" in event_names
    assert "plugin_loaded" in event_names
    assert "plugin_started" in event_names
    assert "plugin_stopped" in event_names
    assert "plugin_unloaded" in event_names

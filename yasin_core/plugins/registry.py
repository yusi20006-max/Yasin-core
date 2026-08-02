import os
import sys
import importlib.util
import threading
from typing import Dict, List, Any, Optional
from enum import Enum

from yasin_core.plugins.base import YasinPlugin
from yasin_core.plugins.exceptions import (
    PluginError,
    PluginDependencyError,
    PluginVersionError,
    PluginNotFoundError,
    PluginStateError,
)
from yasin_core.runtime.interfaces import BaseService
from yasin_core.version import VERSION

# Dynamic event registration constants (or we can import if defined)
PLUGIN_REGISTERED = "plugin_registered"
PLUGIN_LOADED = "plugin_loaded"
PLUGIN_UNLOADED = "plugin_unloaded"
PLUGIN_STARTED = "plugin_started"
PLUGIN_STOPPED = "plugin_stopped"
PLUGIN_FAILED = "plugin_failed"


class PluginState(Enum):
    REGISTERED = "REGISTERED"
    LOADED = "LOADED"
    ACTIVE = "ACTIVE"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


class PluginRegistry(BaseService):
    """
    PluginRegistry manages the lifecycle, version compatibility, dependency validation,
    discovery, and status reporting of plugins within the Yasin-Core ecosystem.
    It integrates fully with the Runtime Service Manager and the Event Bus.
    """

    def __init__(self, event_bus=None):
        self.plugins: Dict[str, YasinPlugin] = {}
        self.states: Dict[str, PluginState] = {}
        self.errors: Dict[str, str] = {}
        self.event_bus = event_bus
        self._lock = threading.RLock()

    def register(self, plugin: YasinPlugin) -> None:
        """Register a plugin instance."""
        with self._lock:
            name = plugin.name
            # Ensure attributes exist for backward compatibility with basic/mock plugins
            if not hasattr(plugin, "version"):
                plugin.version = "1.0.0"
            if not hasattr(plugin, "dependencies"):
                plugin.dependencies = []
            if not hasattr(plugin, "core_version_compat"):
                plugin.core_version_compat = "*"

            self.plugins[name] = plugin
            self.states[name] = PluginState.REGISTERED
            if name in self.errors:
                del self.errors[name]

            self._publish(PLUGIN_REGISTERED, {"plugin_name": name, "version": plugin.version})

    def unregister(self, name: str) -> None:
        """Unregister a plugin, stopping and unloading it if necessary."""
        with self._lock:
            if name not in self.plugins:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")

            # Validate that other plugins do not depend on this plugin
            dependents = []
            for other_name, other_plugin in self.plugins.items():
                if other_name == name:
                    continue
                deps = getattr(other_plugin, "dependencies", [])
                if name in deps:
                    dependents.append(other_name)

            if dependents:
                raise PluginDependencyError(
                    f"Cannot unregister '{name}' because other plugins depend on it: {dependents}"
                )

            # Bring down the plugin gracefully
            state = self.states.get(name)
            if state == PluginState.ACTIVE:
                try:
                    self.stop_plugin(name)
                except Exception:
                    pass
            if state in (PluginState.ACTIVE, PluginState.LOADED, PluginState.STOPPED):
                try:
                    self.unload_plugin(name)
                except Exception:
                    pass

            del self.plugins[name]
            if name in self.states:
                del self.states[name]
            if name in self.errors:
                del self.errors[name]

    def get(self, name: str) -> Optional[YasinPlugin]:
        """Retrieve a registered plugin by name."""
        with self._lock:
            return self.plugins.get(name)

    def list(self) -> List[str]:
        """List names of all registered plugins."""
        with self._lock:
            return list(self.plugins.keys())

    def get_state(self, name: str) -> PluginState:
        """Get the current lifecycle state of a plugin."""
        with self._lock:
            if name not in self.plugins:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")
            return self.states.get(name, PluginState.REGISTERED)

    def check_version_compatibility(self, compat_expr: str, core_version: str) -> bool:
        """
        Check if a given core version meets the semver compatibility expression.
        Supports operators: >=, <=, >, <, ==, !=, ^, or wildcard *.
        """
        if not compat_expr or compat_expr == "*":
            return True

        # Clean spaces and normalize
        expr = compat_expr.strip()

        # Parse versions to lists of ints for easy comparison
        def parse_version(v_str: str) -> List[int]:
            # extract only numeric digits/dots
            cleaned = "".join(c for c in v_str if c.isdigit() or c == ".")
            parts = [int(p) for p in cleaned.split(".") if p.isdigit()]
            while len(parts) < 3:
                parts.append(0)
            return parts[:3]

        core_parsed = parse_version(core_version)

        # Handle carat (^) range (e.g., ^1.6.0 means >= 1.6.0 and < 2.0.0)
        if expr.startswith("^"):
            req_version = expr[1:].strip()
            req_parsed = parse_version(req_version)
            if core_parsed[0] != req_parsed[0]:
                return False
            return core_parsed >= req_parsed

        # Parse comparison operators
        operators = [">=", "<=", ">", "<", "==", "!="]
        op = None
        ver_part = expr
        for o in operators:
            if expr.startswith(o):
                op = o
                ver_part = expr[len(o):].strip()
                break

        req_parsed = parse_version(ver_part)

        if op == ">=":
            return core_parsed >= req_parsed
        elif op == "<=":
            return core_parsed <= req_parsed
        elif op == ">":
            return core_parsed > req_parsed
        elif op == "<":
            return core_parsed < req_parsed
        elif op == "==":
            return core_parsed == req_parsed
        elif op == "!=":
            return core_parsed != req_parsed

        # Default fallback to exact match or prefix check
        return core_version.startswith(expr) or core_parsed == req_parsed

    def validate_dependencies(self, name: str, visited: Optional[set] = None, stack: Optional[set] = None) -> None:
        """
        Validate dependencies for the plugin recursively to detect missing
        and circular dependencies.
        """
        if visited is None:
            visited = set()
        if stack is None:
            stack = set()

        if name in stack:
            raise PluginDependencyError(f"Circular dependency detected containing plugin '{name}'.")

        if name in visited:
            return

        with self._lock:
            plugin = self.get(name)
            if not plugin:
                raise PluginDependencyError(f"Dependency '{name}' is not registered.")

            # Validate version compatibility with Core
            compat = getattr(plugin, "core_version_compat", "*")
            if not self.check_version_compatibility(compat, VERSION):
                raise PluginVersionError(
                    f"Plugin '{name}' version {getattr(plugin, 'version', '1.0.0')} is incompatible "
                    f"with Core version {VERSION} (requires '{compat}')."
                )

            stack.add(name)
            dependencies = getattr(plugin, "dependencies", [])
            for dep in dependencies:
                self.validate_dependencies(dep, visited, stack)
            stack.remove(name)
            visited.add(name)

    def load_plugin(self, name: str) -> None:
        """Load a plugin after validating version and dependencies."""
        with self._lock:
            plugin = self.get(name)
            if not plugin:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")

            state = self.states.get(name, PluginState.REGISTERED)
            if state != PluginState.REGISTERED:
                # Already loaded or beyond registered state
                return

            try:
                # Validate dependencies & version compatibility
                self.validate_dependencies(name)

                # Recursively load dependencies first if they are not loaded
                dependencies = getattr(plugin, "dependencies", [])
                for dep in dependencies:
                    dep_state = self.states.get(dep, PluginState.REGISTERED)
                    if dep_state == PluginState.REGISTERED:
                        self.load_plugin(dep)

                # Execute initialize
                if hasattr(plugin, "initialize"):
                    plugin.initialize()

                # Execute load
                if hasattr(plugin, "load"):
                    plugin.load()

                self.states[name] = PluginState.LOADED
                if name in self.errors:
                    del self.errors[name]
                self._publish(PLUGIN_LOADED, {"plugin_name": name})

            except Exception as e:
                self.states[name] = PluginState.FAILED
                self.errors[name] = str(e)
                self._publish(PLUGIN_FAILED, {"plugin_name": name, "error": str(e), "stage": "load"})
                raise PluginError(f"Failed to load plugin '{name}': {e}") from e

    def unload_plugin(self, name: str) -> None:
        """Unload a plugin, releasing its resources."""
        with self._lock:
            plugin = self.get(name)
            if not plugin:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")

            state = self.states.get(name, PluginState.REGISTERED)
            if state not in (PluginState.LOADED, PluginState.STOPPED, PluginState.FAILED):
                if state == PluginState.ACTIVE:
                    self.stop_plugin(name)
                else:
                    return

            try:
                if hasattr(plugin, "unload"):
                    plugin.unload()
                self.states[name] = PluginState.REGISTERED
                self._publish(PLUGIN_UNLOADED, {"plugin_name": name})
            except Exception as e:
                self.states[name] = PluginState.FAILED
                self.errors[name] = str(e)
                self._publish(PLUGIN_FAILED, {"plugin_name": name, "error": str(e), "stage": "unload"})
                raise PluginError(f"Failed to unload plugin '{name}': {e}") from e

    def start_plugin(self, name: str) -> None:
        """Start a plugin, loading it first if necessary."""
        with self._lock:
            plugin = self.get(name)
            if not plugin:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")

            state = self.states.get(name, PluginState.REGISTERED)
            if state == PluginState.ACTIVE:
                return

            if state == PluginState.REGISTERED:
                self.load_plugin(name)

            # Recursively start dependencies if they are not active
            dependencies = getattr(plugin, "dependencies", [])
            for dep in dependencies:
                dep_state = self.states.get(dep, PluginState.REGISTERED)
                if dep_state != PluginState.ACTIVE:
                    self.start_plugin(dep)

            try:
                if hasattr(plugin, "start"):
                    plugin.start()
                self.states[name] = PluginState.ACTIVE
                self._publish(PLUGIN_STARTED, {"plugin_name": name})
            except Exception as e:
                self.states[name] = PluginState.FAILED
                self.errors[name] = str(e)
                self._publish(PLUGIN_FAILED, {"plugin_name": name, "error": str(e), "stage": "start"})
                raise PluginError(f"Failed to start plugin '{name}': {e}") from e

    def stop_plugin(self, name: str) -> None:
        """Stop an active plugin."""
        with self._lock:
            plugin = self.get(name)
            if not plugin:
                raise PluginNotFoundError(f"Plugin '{name}' is not registered.")

            state = self.states.get(name, PluginState.REGISTERED)
            if state != PluginState.ACTIVE:
                return

            try:
                if hasattr(plugin, "stop"):
                    plugin.stop()
                self.states[name] = PluginState.STOPPED
                self._publish(PLUGIN_STOPPED, {"plugin_name": name})
            except Exception as e:
                self.states[name] = PluginState.FAILED
                self.errors[name] = str(e)
                self._publish(PLUGIN_FAILED, {"plugin_name": name, "error": str(e), "stage": "stop"})
                raise PluginError(f"Failed to stop plugin '{name}': {e}") from e

    # --- Runtime Service Manager Compatibility ---

    def initialize(self) -> None:
        """Initialize all registered plugins in dependency order."""
        with self._lock:
            # First, check dependencies and top-sort them to find startup order
            visited = set()
            for name in list(self.plugins.keys()):
                try:
                    self.validate_dependencies(name)
                    self.load_plugin(name)
                except Exception as e:
                    # Log and set to failed
                    self.states[name] = PluginState.FAILED
                    self.errors[name] = str(e)

    def shutdown(self) -> None:
        """Shutdown and unload all plugins in reverse dependency order."""
        with self._lock:
            # Gather all non-registered/non-failed plugins to stop and unload
            for name in reversed(list(self.plugins.keys())):
                try:
                    if self.states.get(name) == PluginState.ACTIVE:
                        self.stop_plugin(name)
                    if self.states.get(name) in (PluginState.LOADED, PluginState.STOPPED):
                        self.unload_plugin(name)
                except Exception:
                    pass

    def reload(self) -> None:
        """Reload all active plugins."""
        with self._lock:
            active_plugins = [name for name, state in self.states.items() if state == PluginState.ACTIVE]
            self.shutdown()
            self.initialize()
            for name in active_plugins:
                if name in self.plugins and self.states.get(name) != PluginState.FAILED:
                    try:
                        self.start_plugin(name)
                    except Exception:
                        pass

    def health(self) -> Dict[str, Any]:
        """Report on the health of the plugins managed by the registry."""
        with self._lock:
            failed_plugins = {name: self.errors[name] for name, state in self.states.items() if state == PluginState.FAILED}
            healthy = len(failed_plugins) == 0
            return {
                "status": "healthy" if healthy else "unhealthy",
                "healthy": healthy,
                "failed_plugins": failed_plugins,
            }

    def status(self) -> Dict[str, Any]:
        """Report execution status of the service manager."""
        with self._lock:
            plugins_status = {}
            for name, plugin in self.plugins.items():
                plugins_status[name] = {
                    "state": self.states.get(name, PluginState.REGISTERED).value,
                    "version": getattr(plugin, "version", "1.0.0"),
                    "dependencies": getattr(plugin, "dependencies", []),
                    "core_version_compat": getattr(plugin, "core_version_compat", "*"),
                    "description": getattr(plugin, "description", ""),
                    "error": self.errors.get(name),
                }
            return {
                "state": "active",
                "plugin_count": len(self.plugins),
                "plugins": plugins_status,
            }

    def discover(self, plugins_dir: str = "plugins") -> None:
        """Discover and auto-register YasinPlugin classes from a directory."""
        if not os.path.exists(plugins_dir):
            return

        if plugins_dir not in sys.path:
            sys.path.insert(0, plugins_dir)

        for item in os.listdir(plugins_dir):
            item_path = os.path.join(plugins_dir, item)
            module_name = None

            if os.path.isfile(item_path) and item.endswith(".py") and not item.startswith("_"):
                module_name = item[:-3]
            elif os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py")):
                module_name = item

            if module_name:
                try:
                    spec = importlib.util.spec_from_file_location(
                        module_name,
                        os.path.join(plugins_dir, item if os.path.isfile(item_path) else f"{item}/__init__.py")
                    )
                    if spec and spec.loader:
                        module = importlib.util.module_from_spec(spec)
                        sys.modules[module_name] = module
                        spec.loader.exec_module(module)

                        # Inspect the module for classes inheriting from YasinPlugin
                        for attr_name in dir(module):
                            attr = getattr(module, attr_name)
                            if (
                                isinstance(attr, type)
                                and issubclass(attr, YasinPlugin)
                                and attr is not YasinPlugin
                            ):
                                try:
                                    plugin_instance = attr()
                                    self.register(plugin_instance)
                                except Exception:
                                    # Skip if instantiation fails due to constructor parameters
                                    pass
                except Exception:
                    # Ignore failures of individual plugin files so the system is resilient
                    pass

    # --- Private Helpers ---

    def _publish(self, event_name: str, payload: Dict[str, Any]) -> None:
        """Publish events to the Event Bus if it is present."""
        if self.event_bus:
            try:
                self.event_bus.publish(event_name, data=payload)
            except Exception:
                pass

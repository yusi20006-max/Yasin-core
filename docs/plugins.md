# Yasin Plugin System

Yasin-Core features a modular Plugin System that allows future ecosystem components and third-party extensions to register capabilities without modifying the Core architecture.

## Modular Architecture

The Plugin System is designed on top of a clean separation of concerns:
- **`YasinPlugin`**: An abstract contract/base class that defines plugin metadata and lifecycle operations.
- **`PluginRegistry`**: A thread-safe, centralized manager responsible for dynamic plugin discovery, validation (version compatibility and recursive dependency checks), lifecycle transition orchestrations, and integration with the wider Yasin ecosystem.
- **`YasinCoreClient`**: The public SDK layer exposing high-level plugin registration, lookup, state querying, and execution bridge interfaces.

---

## Metadata Configuration

Plugins define metadata fields directly as class/instance attributes:

```python
from yasin_core.plugins import YasinPlugin

class MyAwesomePlugin(YasinPlugin):
    name = "my_awesome_plugin"
    version = "1.2.0"
    description = "Provides advanced natural language formatting capabilities."
    dependencies = ["core_utility_plugin"]
    core_version_compat = "^1.6.0"

    def start(self):
        pass

    def stop(self):
        pass
```

- **`name`** (`str`): Unique identifier of the plugin.
- **`version`** (`str`): The plugin release version (default: `"1.0.0"`).
- **`description`** (`str`): Human-readable summary of the plugin's responsibilities.
- **`dependencies`** (`List[str]`): List of other plugin names that must be loaded prior to this plugin.
- **`core_version_compat`** (`str`): Core version compatibility constraint range (default: `"*"`).

---

## Lifecycle State Transitions

Each plugin transitions through a deterministic sequence of states managed by the registry:

```
[ REGISTERED ] ──(load_plugin)──> [ LOADED ] ──(start_plugin)──> [ ACTIVE ]
      │                              │                             │
      └───────<───(unload_plugin)────┴───────<───(stop_plugin)─────┘
```

1. **`REGISTERED`**: The plugin is registered but not initialized or loaded.
2. **`LOADED`**: Version and dependencies are verified, and the plugin has been initialized/loaded.
3. **`ACTIVE`**: The plugin has been started and is actively processing or listening.
4. **`STOPPED`**: The active plugin has been gracefully stopped.
5. **`FAILED`**: The plugin failed during dependency check, load, or start operations.

---

## Compatibility Checking Rules

Compatibility constraint string supports standard semver ranges:
- **Wildcard**: `*` (any version is compatible).
- **Exact match**: `1.6.0`
- **Operators**: `>=`, `<=`, `>`, `<`, `==`, `!=` (e.g., `>=1.6.0`).
- **Carat range**: `^1.6.0` (means `>=1.6.0` and `< 2.0.0`, satisfying non-breaking major versions).

If a plugin's `core_version_compat` constraint is violated by the running `VERSION` of Yasin-Core, a `PluginVersionError` is raised, and the plugin transitions to the `FAILED` state.

---

## Dependency & Circular Validation

Before loading a plugin:
1. All referenced dependencies must be registered. If any dependency is missing, a `PluginDependencyError` is raised.
2. The dependency graph is dynamically traversed using depth-first search (DFS).
3. If any circular reference is detected (e.g., Plugin A -> Plugin B -> Plugin A), a circular dependency error is raised, preventing deadlocks or infinite loops.
4. When a plugin is loaded/started, its dependencies are automatically initialized, loaded, and started in topological order.

---

## Event Bus Integration

The plugin lifecycle publishes high-level lifecycle events to the central `EventBus`:

- **`plugin_registered`**: Fired when a plugin is registered.
- **`plugin_loaded`**: Fired when a plugin has finished loading.
- **`plugin_unloaded`**: Fired when a plugin is unloaded.
- **`plugin_started`**: Fired when a plugin transitions to active state.
- **`plugin_stopped`**: Fired when a plugin is stopped.
- **`plugin_failed`**: Fired when a plugin fails at any lifecycle stage.

---

## Public SDK APIs

External ecosystem components interact with the Plugin System using the following methods on `YasinCoreClient`:

- **`register_plugin(plugin)`**: Registers a plugin instance.
- **`unregister_plugin(name)`**: Gracefully unregisters, stopping, and unloading the plugin.
- **`get_plugin(name)`**: Retrieves a registered plugin instance by name.
- **`list_plugins()`**: Returns a list of all registered plugin names.
- **`discover_plugins(plugins_dir)`**: Automatically scans and registers compatible plugins from a folder.
- **`load_plugin(name)`**: Loads a registered plugin and resolves its dependencies.
- **`unload_plugin(name)`**: Unloads a plugin and cleans up resources.
- **`start_plugin(name)`**: Starts a plugin and recursively starts its dependencies.
- **`stop_plugin(name)`**: Stops an active plugin.
- **`get_plugin_state(name)`**: Returns the current lifecycle state (string representation).
- **`get_plugin_status()`**: Returns a dictionary representing the status and metadata of all plugins.

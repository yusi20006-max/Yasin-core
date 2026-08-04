# Yasin-Core Migration & Compatibility Layer (v3.2)

This document outlines the architecture, features, and usage guidelines for the **Yasin-Core Compatibility Framework**. The framework guarantees safe upgrades and seamless interaction between `Yasin-Core` and previous SDK clients, agents, external registries, and other ecosystem services.

---

## 1. Version Negotiation & SemVer Support

The compatibility layer includes robust Semantic Version (SemVer) parsing, checking, and negotiation classes that do not depend on external libraries.

### Version Checking
You can compare versions using standard comparison operators, wildcard expressions, or caret ranges (`^`).
- `*` allows any version.
- `^1.6.0` matches `>= 1.6.0` and `< 2.0.0`.
- `^0.5.0` matches `>= 0.5.0` and `< 0.6.0`.

```python
from yasin_core.sdk import Version, is_compatible

v1 = Version("1.6.0")
v2 = Version("1.7.2-beta")

print(v1 < v2)  # True

# Check caret ranges
print(is_compatible("^1.6.0", "1.7.0"))  # True
print(is_compatible("^1.6.0", "2.0.0"))  # False
```

### Version Negotiation
When an external SDK/CLI client initiates a handshake with Core services, they can negotiate the best mutually compatible version.

```python
from yasin_core.sdk import VersionNegotiator

negotiator = VersionNegotiator()
server_supported = ["1.5.0", "1.6.0", "1.7.0"]

# Negotiates highest compatible version
best_version = negotiator.negotiate(client_version_expr="^1.5.0", server_versions=server_supported)
print(best_version)  # "1.7.0"
```

---

## 2. API Compatibility Checker

Inspect targets dynamically at runtime using `APICompatibilityChecker` to ensure they conform to required method names and parameter signatures before triggering actions.

```python
from yasin_core.sdk import APICompatibilityChecker

checker = APICompatibilityChecker()

# Define expected API structure
expected_api = {
    "execute_task": ["task"],  # Must possess execute_task which accepts 'task' parameter
    "status": [],              # Must possess status method
    "id": "attribute"          # Must possess attribute 'id'
}

class SampleAgent:
    def __init__(self):
        self.id = "agent-1"
    def execute_task(self, task):
        pass
    def status(self):
        return "active"

agent = SampleAgent()
report = checker.check_compatibility(agent, expected_api)
print(report["compatible"])  # True
```

---

## 3. Deprecation Management

Keep core code clean while guiding developers when APIs are deprecated or updated.

### Decorator `@deprecated`
Use the decorator to flag obsolete methods, classes, or functions. This automatically logs a structured warning and triggers a Python `DeprecationWarning`.

```python
from yasin_core.sdk import deprecated

@deprecated(since="1.6.0", instead="execute_task")
def run_agent_task(task):
    pass
```

### Deprecation Manager
You can track overall deprecations triggered during a system run:

```python
from yasin_core.compatibility.warnings import _manager

print(_manager.warnings_count)  # Returns number of triggered deprecation warnings
```

---

## 4. Legacy API Adapters

If a core API signature, method name, or class structure is modified, wrap the modern object with `LegacyAPIAdapter` to support old clients without polluting core classes.

```python
from yasin_core.sdk import LegacyAPIAdapter

class ModernService:
    def execute_task(self, task):
        return f"Processed {task}"

# Suppose legacy clients expect `execute(task_id)` instead of `execute_task(task)`
alias_map = {"execute": "execute_task"}

legacy_adapter = LegacyAPIAdapter(ModernService(), alias_mapping=alias_map)

# Calls 'execute_task' under the hood and triggers deprecation warning
result = legacy_adapter.execute("task-1")
print(result)  # "Processed task-1"
```

---

## 5. Schema, Config, and Data Migration Support

### Chained Schema Migrator
Register versioned schema transitions. The migrator automatically finds the path (e.g. 1.0 -> 3.0 via 1.0->2.0->3.0) and chains execution.

```python
from yasin_core.sdk import SchemaMigrator

migrator = SchemaMigrator()

# Register migrations
migrator.register_migration("1.0", "2.0", lambda data: {**data, "v2_field": data["v1_field"] * 2})
migrator.register_migration("2.0", "3.0", lambda data: {**data, "v3_field": f"V3: {data['v2_field']}"})

old_schema = {"v1_field": 5}
new_schema = migrator.migrate(old_schema, current_version="1.0", target_version="3.0")
print(new_schema)  # {"v1_field": 5, "v2_field": 10, "v3_field": "V3: 10"}
```

### Configuration Migrator
Upgrade older configurations with simple renames and default injections.

```python
from yasin_core.sdk import ConfigurationMigrator

old_config = {"old_db_host": "localhost"}
new_config = ConfigurationMigrator.migrate_config(
    old_config,
    key_renames={"old_db_host": "database.host"},
    default_injects={"database.port": 5432}
)
print(new_config)  # {"database": {"host": "localhost", "port": 5432}}
```

---

## 6. Ecosystem & Runtime Validation

Verify integration health across the ecosystem.

```python
from yasin_core.sdk import (
    AgentCompatibilityValidator,
    HubCompatibilityValidator,
    RelayCompatibilityValidator,
    CLICompatibilityValidator,
    RuntimeCompatibilityChecker,
    YasinCoreClient
)

# Validate Agent
agent_report = AgentCompatibilityValidator.validate(my_agent)
print(agent_report["compatible"])

# Validate Hub metadata
hub_report = HubCompatibilityValidator.validate({"id": "hub-pkg", "version": "1.0.0", "core_version_compat": "^1.6.0"})
print(hub_report["compatible"])

# Full active runtime check
client = YasinCoreClient()
checker = RuntimeCompatibilityChecker(client)
runtime_report = checker.check_runtime_compatibility()
print(runtime_report["compatible"])  # True/False status across Config, Services, Storage, and DI container
```

# Yasin AI Ecosystem - Dependency Rules

This document establishes the official and strict architectural and dependency rules that all developers and future code generations MUST adhere to within the Yasin AI Ecosystem.

---

## 1. Allowed and Forbidden Imports

### Rule 1: No Upstream Imports (Forbidden Direction)
Under no circumstances may a package or file in `Yasin-Core` (`yasin_core/` namespace) import from any of the following projects:
-   `yasinrelay`
-   `yasin_agent`
-   `yasinai`
-   `yasinhub`
-   `yasinfeed`

This is a strict **one-way boundary**: Core provides infrastructure; adjacent projects consume Core. Importing upstream projects into Core will trigger immediate build failure and circular dependencies.

### Rule 2: Allowed SDK Consumptions
Projects such as `YasinRelay`, `YasinFeed`, and `Yasin-Agent` must consume `Yasin-Core` **strictly** via the public-facing SDK layer:
```python
# ALLOWED
from yasin_core.sdk import YasinCoreClient, BaseAgent, Task, active_context
```

### Rule 3: No Direct Core Internal Imports
External projects must NEVER directly import internal core packages outside of the SDK:
```python
# FORBIDDEN (Will result in lint errors and build failure)
from yasin_core.agents.runtime import AgentRuntime
from yasin_core.context.engine import ContextEngine
from yasin_core.memory.in_memory import InMemoryShortTermMemory
from yasin_core.security.manager import SecurityManager
```

---

## 2. Public API vs. Private Implementation

-   **Public API**: Contained entirely within the public SDK contract (`yasin_core/sdk/`). The SDK is the stable surface of Yasin-Core. It is guaranteed to remain stable, backward-compatible, and well-documented.
-   **Private Implementation**: Any module outside the SDK directory (e.g., `yasin_core/agents/`, `yasin_core/di/`, `yasin_core/core/`). These implementation details can be heavily refactored, optimization-modified, or completely re-written without breaking adjacent ecosystem apps, provided they adhere to the interfaces registered in the public SDK client.

---

## 3. Soft-Dependency Policy

In various cross-project environments, some optional integration libraries (such as `yasinhub`) might not be installed or present on disk.
Adjacent packages must utilize a **Dynamic Soft-Dependency import check** before executing such calls, with appropriate file-based or mock fallback procedures.

### Reference Integration Pattern (YasinHub Status Sync):
Refer to `yasinrelay/hub_integration.py` for the standard implementation style:

```python
def report_hub_status(success: bool, message: str) -> None:
    # 1. Attempt to import optional integration package dynamically
    try:
        from yasinhub.status_store import write_status
        write_status("yasinrelay", success=success, message=message)
        logger.info("Sync succeeded via Hub SDK")
        return
    except ImportError:
        logger.debug("yasinhub not found on path, falling back to JSON directory writing")

    # 2. Robust fallback when integration is not installed
    try:
        # Standard ecosystem environment configuration override
        status_dir = os.environ.get("YASIN_STATUS_DIR") or Path.home() / ".yasin_status"
        # Write directly to JSON fallback file
        ...
    except Exception as e:
        logger.error(f"Fallback write failed: {e}")
```

---

## 4. Duplication Policy

### 1. General Principles
-   We prioritize **reusability** over duplication. Overlapping definitions should eventually be unified under Yasin-Core.
-   If a function or abstraction is required by more than one adjacent project (e.g., Eitaa publishers, media resizing, or state machines), it should be promoted to a shared-package wrapper or registered directly as a core-supported plugin.

### 2. The Core/Relay Exception
-   During this stabilization phase, the duplicated Agent system within `yasinrelay/agent/` **must not be removed or altered**.
-   This duplication is temporarily preserved to prevent any production behavior regressions or pipeline instability.
-   **Consolidation Rule**: Once the Go feed-fetch processes are fully stabilized in subsequent tasks, a migration will be scheduled to replace all of `yasinrelay/agent/` classes with direct public imports from `yasin_core.sdk`.

---

## 5. Guidelines for Introducing New Implementations

If a developer needs to introduce a new `Agent`, `Memory`, `Context`, or `Security` pattern:

1.  **Do Not Create Local Overlaps**: Never create custom subclasses/wrappers inside project modules (like `YasinRelay` or `Yasin-Agent`) that reinvent thread safety or context propagation.
2.  **Submit as core extension**:
    *   If the feature is highly generic, implement it inside the private `yasin_core/` folders.
    *   Expose it securely through the public-facing SDK v2 namespaces (`client.v2`).
    *   Register it inside the core Dependency Injection (DI) container or Runtime Service Manager.
3.  **Deploy as plugin**:
    *   If the custom model is specialized or project-specific, register it as a dynamic plugin via `PluginRegistry` so it can be dynamically discovered at runtime without polluting the kernel source tree.

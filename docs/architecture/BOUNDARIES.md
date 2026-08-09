# Yasin AI Ecosystem - Architectural Boundaries

This document defines the canonical ownership, allowed dependency directions, known overlaps, and required future decisions for all major architectural concepts within the complete Yasin AI Ecosystem.

---

## 1. Architectural Concept Matrix

| Concept | Canonical Owner | Current Implementations | Primary Consumers | Allowed Dependency Direction | Known Overlap | Future Decision Required |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Runtime** | `Yasin-Core` | `yasin_core/core/runtime.py` (`YasinRuntime`), `yasin_core/core/orchestrator.py` (`RuntimeOrchestrator`) | SDK Client, adjacent runtimes (YasinRelay, Yasin-Agent) | Core internal to Core runtime. No project imports. | Core has some simple console routing overlapping with CLI. | Decide if `YasinCLI` commands should go strictly through `RuntimeOrchestrator.execute_command`. |
| **SDK** | `Yasin-Core` | `yasin_core/sdk/client.py` (`YasinCoreClient`), `yasin_core/sdk/async_client.py` (`AsyncYasinCoreClient`) | YasinRelay, Yasin-Agent, YasinHub, YasinFeed | SDK imports `yasin_core` subsystems; external components import strictly from `yasin_core.sdk`. | None. This is the official and only entry point. | Keep SDK 100% backward-compatible with legacy client APIs. |
| **Agent** | `Yasin-Agent` | `yasin_core.sdk.BaseAgent` | Yasin-Agent Platform (`agent_platform`), developer scripts | `Yasin-Agent` imports Core SDK to subclass `BaseAgent`. | `yasinrelay/agent/` duplicates agent structure locally. | Decide how to deprecate YasinRelay's internal light agent code in favor of Yasin-Core SDK. |
| **Agent Runtime** | `Yasin-Core` | `yasin_core/agents/runtime.py` (`AgentRuntime`), `yasin_core/agents/manager.py` | `YasinCoreClient.agent_runtime` | Inside Core. Discovers and tracks registered custom `BaseAgent` instances. | Overlaps with local executors in Yasin-Agent workspace. | Merge Yasin-Agent specialized workflows into core runtime registries. |
| **Memory** | `Yasin-Core` | `yasin_core/memory/` (`InMemoryShortTermMemory`, `InMemoryLongTermMemory`, `StorageBackedLongTermMemory`) | Core services, runtime agents, SDK consumers | Core internal subsystems to Memory API. | `yasinrelay/agent/memory.py` defines duplicated memory classes. | Keep Core Memory as the only canonical store; refactor YasinRelay to use core-backed memory. |
| **Context** | `Yasin-Core` | `yasin_core/context/engine.py` (`ContextEngine`), `yasin_core/context/manager.py` | Core security, Task Engine, SDK client flows | Core internal subsystems to Context variables. | `yasinrelay/agent/context.py` duplicates context management. | Enforce Core thread-local contextvars for ALL components. |
| **Security** | `Yasin-Core` | `yasin_core/security/` (`SecurityManager`, `@require_permission`, policy engines, symmetric XOR data protectors) | API Gateway, SDK wrappers, Admin interfaces | Inside Core. No direct adjacent project calls allowed. | `YasinAI` features independent security platforms. | Standardize external developer authentications strictly via API Gateway authenticators. |
| **Relay / Transport** | `YasinRelay` | `yasinrelay/pipeline.py`, `yasinrelay/eitaa_publisher.py` | Core social feeds, messaging integration channels | YasinRelay imports Core SDK. | None. Core does not do feed publishing. | Keep publishing modules isolated inside YasinRelay. |
| **Feed / Ingestion** | `YasinFeed` / `YasinRelay` | Go scraper `fetcher/openfeed-fetch`, `yasinrelay/fetch_engine.py` | YasinRelay pipeline | YasinRelay imports Go binary. | RESOLVED (Aug 2026): the duplicated `fetcher/` Go source and `yasinrelay/` package were removed from Yasin-Core; canonical source is the standalone `YasinRelay` repo. | Closed. |
| **Hub / Integration** | `YasinHub` | `yasinhub/status_store.py` (see `YasinRelay` repo for `yasinrelay/hub_integration.py`, `report_hub_status`) | YasinRelay execution monitoring | External projects to `yasinhub`. Soft-import handles import failures. | Local JSON status tracking overlapping with Hub SDK APIs. | Establish formal caret semver-matched schemas in YasinHub status store. |
| **CLI** | `YasinCLI` | Prototype CLI scripts | System administrators, cron tasks | CLI imports Core SDK. | Basic argparse inside Core. | Build dedicated YasinCLI package that consumes SDK. |
| **Deployment** | `YasinHub` / DevOps | Docker, Systemd service templates | Platform maintainers | Deployment files reference project execution scripts. | None. | Standardize environment variables like `YASIN_STATUS_DIR` across all runs. |
| **Knowledge / Graph** | `YasinAI` | `knowledge_platform` | Advanced developer platforms | stand-alone independent research platforms | None. Core does not feature knowledge graphs. | Address integration paths via non-breaking bridge plugins. |

---

## 2. In-Depth Boundary Specifications

### Yasin-Core Key Subsystems

1.  **`yasin_core.agents`**: Provides the foundational runtime abstractions (`IAgentRuntime`, `BaseAgent`, `Task`, planners, and registries). It registers and tracks agents. It is NOT responsible for defining complex developer-facing workflows, prompts, or LLM-specific agent chains.
2.  **`yasin_core.context`**: The thread-local and reentrant lock-protected context management engine (`ContextEngine`). This must remain the absolute owner of current execution states (such as active authorization tokens, requests IDs, and system variables).
3.  **`yasin_core.memory`**: Handles structures for keeping track of both short-term and long-term state. It has fallback mechanisms to storage and integrates with the Event Bus.
4.  **`yasin_core.security`**: Central Security & Permission Layer containing authorization controllers (RBAC), XOR-based symmetric encryption helpers, and asterisk masking configurations. It protects configurations and logs audit events.

### Yasin-Agent Boundaries

1.  **`agent_platform`**: Defines advanced agent schemas, templates, and multi-agent interaction systems. It must consume `Yasin-Core` only through the public `yasin_core.sdk` interface.
2.  **Rule**: Yasin-Agent must never redefine `BaseAgent` or `Task` subclasses that bypass core `AgentRuntime` registration, nor should it import `yasin_core.agents` internals.

### YasinAI Boundaries

1.  **`developer_platform` / `knowledge_platform` / `security_platform`**:
    *   Currently completely independent of the other five projects.
    *   **CRITICAL CONSTRAINT**: YasinAI is NOT merged into Yasin-Core during this stabilization. YasinAI's custom Security/Memory/Context/Agent patterns must remain self-contained.
    *   **Future Decision**: A formal adapter layer or bridge plugin will eventually be introduced in Yasin-Core to consume YasinAI's Knowledge Platform services securely without creating cyclic imports or structural overlap.

---

## 3. Allowed Dependency Direction

Subsystems must follow a strict downward hierarchy. No parent component may import an upstream implementation:

```
┌────────────────────────────────────────────────────────┐
│                        YasinHub                        │
└───────────────────────────┬────────────────────────────┘
                            │ (Consumes)
                            ▼
┌────────────────────────────────────────────────────────┐
│             YasinRelay / Yasin-Agent / CLI             │
└───────────────────────────┬────────────────────────────┘
                            │ (Consumes via SDK)
                            ▼
┌────────────────────────────────────────────────────────┐
│                       Yasin-Core                       │
└────────────────────────────────────────────────────────┘
```

1.  **Core Internal Isolation**: `yasin_core` internal subsystems must NEVER import `yasinrelay`, `yasin_agent`, `yasinai`, or `yasinhub` under any circumstances.
2.  **SDK Dependency Direction**: SDK Client (`yasin_core.sdk`) depends on core internal modules. It translates internal exceptions and aliases internal namespaces safely.
3.  **Third-Party and Adjacent Modules**: Adjacent projects depend strictly on `yasin_core.sdk`. Direct imports of `yasin_core/agents`, `yasin_core/context`, `yasin_core/memory`, or `yasin_core/security` are **explicitly forbidden**.

# Yasin Core Architecture


## Overview

Yasin Core is the central runtime layer of the Yasin AI Ecosystem.


## Main Components


### Runtime

Responsible for:

- Starting system
- Managing lifecycle
- Providing core services


### Event Bus

Yasin-Core v1.5 introduces a centralized, thread-safe, and modular **Event Bus architecture** under `yasin_core.events` (and exposed publicly via the SDK `yasin_core.sdk` and `client.event_bus`).

The Event Bus allows decoupled, event-driven communication across Yasin ecosystem components, facilitating reactive pipelines, future plugin updates, and distributed system integrations.

#### Key Capabilities

- **Separation of Concerns**: Event models (`Event`) are completely decoupled from transport and delivery logic (`EventBus`).
- **Standard Event Model (`Event`)**: Standardizes event fields including a unique `event_id` (UUID format), standard creation `timestamp` (datetime format), custom `metadata`, and arbitrary `payload`.
- **Absolute Backward Compatibility**: The `Event` class subclasses `dict` and implements custom `__eq__` checks against its payload, enabling older systems/callbacks expecting plain dictionary payloads or raw strings/objects to work seamlessly without modification.
- **Filtering Support**: Subscribers can register callbacks with a dedicated `filter_func: Callable[[Event], bool]` argument to consume only events matching specific criteria.
- **Asynchronous & Synchronous Handling**:
  - Standard synchronous event handling.
  - Asynchronous handlers (`async def` or callbacks registered with `async_handle=True`) are supported. Sync handlers are dispatched to a background thread pool (`ThreadPoolExecutor`), while coroutines are seamlessly scheduled on the active event loop.
- **Error Isolation**: Each subscriber invocation is individually isolated. Exceptions raised in subscriber callbacks are caught, logged, and isolated from other listeners and the publisher.
- **Configurable Event History**: Stores a bounded queue of recently published events, exposing retrieval APIs (`get_history(limit, event_name)`) and clear functions.
- **Runtime and DI Integration**: The central `EventBus` instance is registered within the `YasinRuntime` and injected directly as a singleton into the DI Container (`EventBus` and `"event_bus"`), enabling zero-config service injection.

#### Usage Example

```python
from yasin_core.sdk import YasinCoreClient, Event

# Initialize Client
client = YasinCoreClient()
bus = client.event_bus

# Define standard subscription
def on_agent_registered(event: Event):
    print(f"Agent Registered: {event['agent_name']} (Event ID: {event.event_id})")

bus.subscribe("agent_registered", on_agent_registered)

# Define a subscription with filtering
def on_critical_alert(event: Event):
    print(f"CRITICAL Alert: {event['message']}")

bus.subscribe(
    "system_alert",
    on_critical_alert,
    filter_func=lambda evt: evt.get("severity") == "critical"
)

# Publish an event
bus.publish("agent_registered", {"agent_name": "Assistant-Agent"})
bus.publish("system_alert", {"message": "Memory threshold reached"}, severity="critical")
```


### Plugin System

Allows extending Yasin Core without changing the kernel.


### Provider Layer

Provides a robust, unified abstraction for AI models and external LLM services.

**Key Components (v0.5):**
- **`AIProvider`**: Abstract base class defining the standard interface for all AI models (with the main abstract method `generate(prompt)`).
- **`MockProvider`**: A standard provider implementation that returns mock responses, highly useful for testing and offline/local development.
- **`LocalProvider`**: A default provider implementation simulating local model generation.
- **`ProviderRegistry`**: Internal registry that holds, manages, and structures registered providers.
- **`ProviderManager`**: Central management system that orchestrates provider registration, retrieval, and logger auditing, pre-registering standard default providers during initialization.

**SDK Client Integration:**
- **`register_provider(provider)`**: Register any custom AI provider with the client instance.
- **`get_provider(name)`**: Retrieve a registered AI provider by name.
- **`list_providers()`**: List names of all currently registered AI providers (includes `local` and `mock` by default).
- **`generate(provider_name, prompt)`**: Convenience method on `YasinCoreClient` to execute text generation directly through a designated provider.


## Dependency Injection Container

Yasin-Core v1.4 introduces a thread-safe, lightweight **Dependency Injection (DI) Container** under `yasin_core.di` (and exposed publicly via the SDK `yasin_core.sdk` and `client.di_container`).

The DI container facilitates clean modular service composition and reduces coupling across Yasin-Core modules by serving as a centralized composition root.

### Key Capabilities

- **Lifetime Management**: Support for `SINGLETON` (cached and reused) and `TRANSIENT` (newly constructed per resolve) service lifetimes.
- **Constructor Injection**: Automatically parses constructor parameters (`__init__`) using type hints and parameter names to inject resolved dependencies.
- **Autowiring**: Supports resolving and constructing concrete, unregistered classes dynamically by autowiring their dependencies.
- **Cycle Detection**: Detects circular dependencies at resolution time and throws a descriptive `CircularDependencyError`.
- **Missing Dependency Detection**: Emits clean `DependencyResolutionError` exceptions when a parameter cannot be resolved.

For detailed usage guide and examples, see [Dependency Injection Documentation](dependency_injection.md).


## Memory Architecture

The Memory Architecture in Yasin Core v0.2 provides memory, context, and storage infrastructure while preserving the existing v0.1 architecture. It is designed around a layered flow where data and execution state flow from the top-level runtime down to persistent storage:

```
Runtime
    |
Context
    |
Memory
    |
Storage
```

### Flow and Component Layers

1. **Runtime**:
   The `YasinRuntime` acts as the orchestrator of the system. When executing tasks or handling requests, it boots up and initializes the current execution context.

2. **Context**:
   The `Context` object manages the active session/state. Using `contextvars` under the hood, it isolates state across threads/tasks without requiring components to explicitly pass state parameters. It serves as a secure, isolated repository for passing active state between the **Runtime**, **Plugins**, and **Providers**.

3. **Memory**:
   The Memory layer provides structured abstraction for keeping track of both short-term and long-term state.
   - **ShortTermMemory** (e.g., `InMemoryShortTermMemory`): Used to store temporary session-specific variables, conversation history, and short-lived execution context.
   - **LongTermMemory** (e.g., `InMemoryLongTermMemory` or `StorageBackedLongTermMemory`): Used to store persistent information across sessions, user profiles, or learned behaviors.

4. **Storage**:
   The Storage layer is responsible for actual serialization and physical persistence of data.
   - The **BaseStorage** interface decouples the memory classes from concrete database technologies.
   - **JSONFileStorage** provides standard, out-of-the-box local filesystem storage.
   - The backend selection interface allows substituting database backends later without modifying callers.


### Interaction with Core Infrastructure

- **Event Bus**:
  Components can publish/subscribe to memory-related events (such as `MEMORY_UPDATED` or `CONTEXT_CHANGED`) via the Event Bus to trigger reactions elsewhere in the ecosystem, ensuring reactive architecture.

- **Plugin System**:
  Plugins utilize the active `Context` to read or append execution metadata (e.g., modifying pipeline parameters) and can interface with memory instances to store custom state or leverage long-term historical records.

- **Provider Layer**:
  AI Providers query the memory layer to retrieve past message histories or relevant context documents (using short-term and long-term storage) to inject into prompt generation, enriching model completions.


## Agent Runtime Architecture

Yasin-Core v0.3 introduces the execution layer designed to manage AI Agents, Tasks, and execution workflows. The system is designed with a decoupling flow of execution components:

```
Runtime
   │
Agent Manager
   │
Planner
   │
Executor
   │
Agents
```

### Component Flow

1. **Runtime**:
   Acts as the orchestrator of the system, setting up the environments and lifecycle of agents, plugins, contexts, and providers.

2. **Agent Manager**:
   Comprises the `AgentRegistry` and `AgentManager`. Handles registration, removal, listing, starting, and stopping of agents. It ensures agent instances are kept in memory and are ready to execute tasks on demand.

3. **Planner**:
   The `Planner` abstract interface and its concrete `SimplePlanner` analyze a `Task` object to translate it into a structured plan payload, determining which specific agent should handle the task and mapping required input fields.

4. **Executor**:
   The `TaskExecutor` (aliased as `Executor`) executes a task using the workflow:
   - Takes a `Task` object.
   - Delegates planning to a `Planner`.
   - Locates and ensures the required agent is started via the `AgentManager`.
   - Dispatches payload to the target `Agent`.
   - Obtains the final outcome and records it back onto the `Task`.

5. **Agents**:
   Implementing the `BaseAgent` ABC, concrete agents perform local execution or can interface with external layers like the Provider Layer to fulfill actions.


### Integration with Core Infrastructure

- **Memory**:
  Agents query and store state dynamically using `ShortTermMemory` and `LongTermMemory` systems, preserving history across multiple task cycles.

- **Context**:
  Execution context is preserved and isolated across tasks/threads using the standard `Context` manager, ensuring variables, credentials, and configurations remain thread-safe.

- **Event Bus**:
  Workflow transitions (e.g., Task Completion, Failure, Agent Registration) can emit corresponding events onto the `EventBus` so external components (like YasinRelay) can react dynamically.

- **Plugin System**:
  Plugins can hook into the Agent registry to dynamically inject new agents, or wrap the Executor to intercept and enrich planner tasks.

- **Provider Layer**:
  When executing, agents utilize the AI `Provider` interface to generate completions, access LLM intelligence, or execute complex tasks.


## SDK Integration Layer

The SDK Integration Layer is the public entry point for external Yasin ecosystem projects (such as Yasin-Agent, YasinRelay, YasinCoder, YasinPress, and YasinHub). It exposes standard clients and interfaces to interact with the core runtime, events, memory, context, and other internal systems, isolating the core implementation details and providing backward-compatible APIs.


### SDK Integration & Interaction Flow

External applications interact directly with the `YasinCoreClient` to perform agent tasks, manage execution context, and store or retrieve system memories. This shields external developers from internal changes to underlying agent registries, planners, memory managers, and AI model providers.

The hierarchy of interaction and state flow is as follows:

```
External Application
        │
        ▼
 YasinCoreClient
        │
        ▼
  Agent Runtime
        │
        ▼
     Memory
        │
        ▼
    Context
        │
        ▼
   Providers
```

- **External Application**: Initiates agent execution, sets configurations, and queries context/memory through the public client API.
- **YasinCoreClient**: Acts as the single unified SDK interface, orchestrating the creation of execution tasks, propagation of contexts, and retention of state records.
- **Agent Runtime**: Dispatches execution payloads to agents and retrieves responses. During execution, it coordinates with the memory and context components.
- **Memory**: Retains both short-term conversational context and storage-backed long-term memories. It feeds historical state to runtime agents.
- **Context**: Thread-safely propagates active state, system configurations, and operational flags down the execution hierarchy.
- **Providers**: AI models and tool integrations leverage the isolated active context and memories to generate context-rich completions.


## Plugin Runtime Integration

The Agent Runtime integrates seamlessly with the Plugin System using public SDK and Plugin interfaces, allowing automated plugin execution and dynamic capability extension.

### Interaction Flow

The interaction flow during a plugin execution is structured as follows:

```
Agent
  ↓
Plugin Runtime
  ↓
Plugin
  ↓
Result
```

1. **Agent**: The `PluginExecutionBridge` acts as an Agent in the Agent Runtime. When the client executes a task targeting this bridge, the agent takes the input payload.
2. **Plugin Runtime**: The bridge looks up the targeted plugin from the `PluginRegistry`.
3. **Plugin**: The bridge dynamically invokes the standard execution method (e.g. `execute`, `run`, or call) on the plugin instance.
4. **Result**: The plugin performs its logic and returns the output result, which the bridge updates on the execution `Task`.

### Core System Integration

- **Event Bus**: Transitions in plugin execution (such as `TASK_STARTED`, `TASK_COMPLETED`, and `TASK_FAILED`) emit corresponding events to the `EventBus` allowing external subscribers to audit and trace executions.
- **Memory**: During execution, plugins and agents can query and save states to the `InMemoryShortTermMemory` or `InMemoryLongTermMemory` instances via the client.
- **Context**: State, metadata, and variables are propagated down through thread-safe `active_context` variables.
- **SDK**: The `YasinCoreClient` exposes clean, public APIs (`register_plugin`, `get_plugin`, `list_plugins`, `discover_plugins`) to manage the complete plugin lifecycle from a single entry point.


## Context Engine

The **Context Engine** is a centralized, thread-safe context management system that manages runtime execution context shared across the Yasin ecosystem.

### Key Capabilities

1. **Context Creation & Isolation**:
   The engine creates and tracks isolated `RuntimeContext` instances. Each context is assigned a unique ID (UUID format) to ensure absolute uniqueness across concurrent threads.

2. **Hierarchical Propagation (Parent-Child Fallback)**:
   Contexts can be created as children of existing contexts. If a key is requested from a child context but not found locally, the query automatically propagates/falls back to the parent context.

3. **Lifecycle Management**:
   The engine tracks and manages the active/inactive state of contexts. Deleting a context deactivates it and removes it from active tracking.

4. **Serialization and Deserialization**:
   Supports native dictionary-based serialization (`serialize()`) and deserialization (`deserialize()`) of context states (ID, Parent ID, Data payload, Metadata, Active state), facilitating state persistence and cross-network propagation.

5. **Runtime and SDK Integration**:
   - **`YasinRuntime`**: Integrates a dedicated `ContextEngine` into the core runtime, exposing the context status in the overall runtime status report.
   - **`YasinCoreClient`**: Exposes the context engine directly through the public SDK interface (`client.context_engine`).

### Usage Example

```python
from yasin_core.sdk import YasinCoreClient, RuntimeContext

# Initialize Client
client = YasinCoreClient()

# Create a Parent Context with global properties
parent_ctx = client.context_engine.create_context(
    data={"env": "production", "debug": False},
    metadata={"owner": "platform-team"}
)

# Create a Child Context with local overrides and parent linkage
child_ctx = client.context_engine.create_context(
    data={"debug": True, "task_id": "999"},
    parent_id=parent_ctx.id
)

# Fallback/Propagation check
print(child_ctx.get("env"))       # Returns "production" (falls back to parent)
print(child_ctx.get("debug"))     # Returns True (retrieved from local override)
print(child_ctx.get("task_id"))   # Returns "999" (retrieved from local)

# Serialization
payload = child_ctx.serialize()

# Deserialization
restored_ctx = RuntimeContext.deserialize(payload, engine=client.context_engine)
```


## Task Execution Engine (v2.1)

Yasin-Core v2.1 introduces a centralized, thread-safe, and modular **Task Execution Engine** under `yasin_core.execution` (exposed publicly via `yasin_core.sdk` and `client.execution`).

The Task Execution Engine facilitates high-performance, background, asynchronous task/job execution across the Yasin ecosystem with full support for priority scheduling, retry logic, timeout handling, cooperative cancellation, event bus broadcasting, and memory/context propagation.

### Key Capabilities

1. **Task Model Definition (`Job` / `ExecutionTask`)**:
   Standardized `Job` (aliased as `ExecutionTask`) containing properties like:
   - `id`: Unique identifier (UUID).
   - `name`: Human-readable identifier.
   - `status`: Lifecycle state (`pending`, `queued`, `running`, `completed`, `failed`, `cancelled`).
   - `priority`: Int or Enum (`LOW`=10, `NORMAL`=20, `HIGH`=30, `CRITICAL`=40).
   - `retries`: Max retry attempts.
   - `timeout`: Maximum execution time in seconds.
   - `context_id`: Propagated execution context ID.
   - `result` & `error`: Storage of outcome details.

2. **Priority-Based Execution**:
   A thread-safe `JobQueue` backed by a priority queue that processes jobs sorted by:
   - Priority (highest value first, e.g. CRITICAL first).
   - Time of creation (oldest first, FIFO fallback for equal priorities).
   - A unique counter (strict tie-breaker to prevent comparison errors on `Job` instances).

3. **Background Worker Abstraction**:
   Dedicated worker threads (`JobWorker`) pull tasks from the priority queue, execute them inside their propagated active contexts, handle cooperative cancellations, timeouts (via futures), and schedule retries on failures.

4. **Robust Target Resolution**:
   Supports executing multiple types of workloads out-of-the-box:
   - **Arbitrary Callable Targets**: Standard Python functions or callable objects.
   - **Agent Workloads**: Executes registered agents (e.g. string agent names) using their standardized runtimes.
   - **Plugin Tasks**: Invokes registered plugins seamlessly by identifying executable entry points.

5. **Ecosystem-Wide Integration**:
   - **Event Bus Integration**: Emits detailed standard lifecycle events (`job_queued`, `job_started`, `job_completed`, `job_failed`, `job_cancelled`, `job_retrying`).
   - **Context Propagation**: Automatically runs jobs inside the active context of the submitting thread.
   - **Memory Integration**: Auto-persists task outcomes and metadata to the short-term memory system.
   - **Runtime Orchestrator**: Registered under the service name `"execution"` so background workers start/stop gracefully with the system.

### Usage Example

```python
from yasin_core.sdk import YasinCoreClient, Job, JobPriority

# 1. Initialize SDK Client and Start Orchestrator
client = YasinCoreClient()
client.start()

# 2. Define a workload function
def process_data(x: int, y: int) -> int:
    return x * y

# 3. Create and submit a Job
job = client.create_job(
    target=process_data,
    args=(10, 5),
    priority=JobPriority.HIGH,
    retries=3,
    timeout=5.0
)

# 4. Wait for completion or check status
import time
while job.status == "queued" or job.status == "running":
    time.sleep(0.1)

print(f"Job Status: {job.status}")
print(f"Result: {job.result}")

# 5. Stop Orchestrator on shutdown
client.stop()
```

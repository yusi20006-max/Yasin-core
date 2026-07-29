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

Provides internal communication between modules.


Example:

YasinRelay

emits:

NEW_CONTENT


YasinPress

receives event.


### Plugin System

Allows extending Yasin Core without changing the kernel.


### Provider Layer

Provides abstraction for AI models.


Future providers:

- OpenAI
- Ollama
- HuggingFace
- Local Models


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

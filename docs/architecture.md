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

The Agent Runtime Architecture in Yasin Core v0.3 introduces a structured, declarative layer to manage AI Agents, tasks, and planning and execution workflows. The system is designed as a flow starting from the high-level system orchestration down to individual agent task execution:

```
Runtime
   ↓
Agent Manager
   ↓
Planner
   ↓
Executor
   ↓
Agents
```

### Component Flow

1. **Runtime**:
   Acts as the central orchestrator that instantiates and runs the `AgentManager` and execution pipeline.

2. **Agent Manager**:
   Manages the lifecycle of all registered agents (register, remove, get, list, start, stop). It provides a unified gateway for the system to discover and trigger active agents.

3. **Planner**:
   Takes a raw task and determines the execution plan (e.g., matching the appropriate agent based on the input specifications, setting up preconditions, or decomposing complex tasks).

4. **Executor**:
   Executes the planned task. It verifies that the assigned agent is active and running, changes the task status, handles execution safely, captures outputs/errors, and updates the task status to completed/failed.

5. **Agents**:
   The concrete execution units that inherit from `BaseAgent` and execute specific business logic, tools, or model interactions.


### Integration and Connections

- **Memory**:
  Agents query the memory system to load past contexts (ShortTermMemory) or user preferences and global rules (LongTermMemory). The executor/agents can save task execution traces or outcomes to persistent long-term storage for future reference.

- **Context**:
  The entire workflow runs inside isolated execution scopes using the `Context` manager. Plugins and agents pass internal states and thread-safe session variables through contextvars.

- **Event Bus**:
  The task life cycle stages (e.g., `TASK_PLANNED`, `TASK_STARTED`, `TASK_COMPLETED`, `TASK_FAILED`) can emit events onto the Event Bus to trigger external processes (such as saving reports, sending notifications, or logging).

- **Plugins**:
  Plugins can dynamically register custom agents, intercept execution stages, or extend agent capabilities by injecting custom tools or prompt templates.

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

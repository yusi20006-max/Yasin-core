# Yasin-Agent Integration Contract v0.1

This document defines the first stable integration contract between **Yasin-Core** and external agent runtimes, specifically **Yasin-Agent**.

As Yasin-Core serves as the central runtime and infrastructure layer of the Yasin AI Ecosystem, external systems must adhere to these contracts to ensure seamless interoperability, lifecycle management, context propagation, and state persistence.

---

## 1. Agent Registration

External systems and agents register themselves with the Yasin-Core runtime using the `BaseAgent`, `AgentRegistry`, and `AgentManager` APIs.

### Interface Definitions

#### `BaseAgent` (Abstract Base Class)
Any agent implementing this contract must inherit from `yasin_core.agents.base.BaseAgent`:

```python
class BaseAgent(ABC):
    def __init__(self, name: str, description: str = ""):
        self.name = name
        self.description = description
        self.running = False

    @abstractmethod
    def start(self) -> None:
        """Initialize resources and mark agent as running."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Clean up resources and mark agent as stopped."""
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any:
        """Perform the agent's action given input data."""
        pass
```

#### `AgentManager`
The central registry and lifecycle controller is `yasin_core.agents.manager.AgentManager`.

```python
class AgentManager:
    def __init__(self, registry: Optional[AgentRegistry] = None):
        ...
    def register_agent(self, agent: BaseAgent) -> None: ...
    def remove_agent(self, name: str) -> Optional[BaseAgent]: ...
    def get_agent(self, name: str) -> Optional[BaseAgent]: ...
    def list_agents(self) -> List[str]: ...
    def start_agents(self) -> None: ...
    def stop_agents(self) -> None: ...
```

### Registration Flow & Code Example

To register an external agent with Yasin-Core:

1. Create a class that inherits from `BaseAgent`.
2. Register the instance using the shared `AgentManager`.

```python
from typing import Any, Dict
from yasin_core.agents.base import BaseAgent
from yasin_core.agents.manager import AgentManager

# 1. Define custom external Agent
class CustomExternalAgent(BaseAgent):
    def start(self) -> None:
        self.running = True
        # Initialize custom models, connections, or state here

    def stop(self) -> None:
        self.running = False
        # Clean up resources

    def execute(self, input_data: Dict[str, Any]) -> Any:
        # Business logic goes here
        query = input_data.get("query", "")
        return f"Processed query: {query}"

# 2. Register the agent
manager = AgentManager()
my_agent = CustomExternalAgent(name="custom-agent", description="An external agent")
manager.register_agent(my_agent)

# 3. Core manages the lifecycle
manager.start_agents()
assert my_agent.running is True
```

---

## 2. Task Execution

The execution layer in Yasin-Core handles workflow orchestrations using three core components: `Task`, `Planner`, and `TaskExecutor`.

```
Task (Input) ──> Planner ──> Executable Plan ──> Executor ──> Target Agent ──> Task (Output)
```

### Interface Definitions

#### `Task`
Represents the unit of work submitted to the system:

```python
class Task:
    def __init__(
        self,
        id: str,
        name: str,
        input_data: Dict[str, Any] = None,
        status: str = "pending",
        result: Optional[Any] = None,
        error: Optional[str] = None
    ): ...
```

#### `Planner` & `SimplePlanner`
Converts tasks into actionable payloads. `SimplePlanner` uses the task `name` as the default target agent name:

```python
class Planner(ABC):
    @abstractmethod
    def plan(self, task: Task) -> Dict[str, Any]: ...
```

#### `TaskExecutor` (or `Executor`)
Executes the target agent on the plan payload:

```python
class TaskExecutor:
    def __init__(self, agent_manager: AgentManager, planner: Optional[Planner] = None): ...
    def execute_task(self, task: Task) -> Task: ...
```

### Task Execution Flow & Code Example

```python
from yasin_core.agents.task import Task
from yasin_core.agents.executor import TaskExecutor
from yasin_core.agents.planner import SimplePlanner

# 1. Instantiate the Task
# The name of the task dictates the target agent in SimplePlanner
task = Task(
    id="task-001",
    name="custom-agent",
    input_data={"query": "Hello Yasin!"}
)

# 2. Setup Planner and Executor
planner = SimplePlanner()
executor = TaskExecutor(agent_manager=manager, planner=planner)

# 3. Execute the Task
executed_task = executor.execute_task(task)

# 4. Verify output
assert executed_task.status == "completed"
assert executed_task.result == "Processed query: Hello Yasin!"
```

---

## 3. Memory Access

Yasin-Core provides a structured, multi-tiered memory abstraction layer separating short-term and long-term state.

```
+--------------------------------------------------------+
|                      BaseMemory                        |
+--------------------------------------------------------+
                           |
            +--------------+--------------+
            |                             |
+-----------------------+     +-----------------------+
|    ShortTermMemory    |     |    LongTermMemory     |
+-----------------------+     +-----------------------+
            |                             |
+-----------------------+     +-----------------------+
|InMemoryShortTermMemory|     |InMemoryLongTermMemory |
+-----------------------+     +-----------------------+
                                          |
                              +-----------------------+
                              |StorageBackedLongTermMemory
                              +-----------------------+
```

### Interface Definitions

#### `BaseMemory`
All memory backends must implement the following API:

```python
class BaseMemory(ABC):
    @abstractmethod
    def get(self, key: Any, default: Any = None) -> Any: ...
    @abstractmethod
    def set(self, key: Any, value: Any) -> None: ...
    @abstractmethod
    def delete(self, key: Any) -> None: ...
    @abstractmethod
    def clear(self) -> None: ...
```

### Memory Retrieval and Storage Flow & Code Example

Agents can use `ShortTermMemory` for conversation session states and `LongTermMemory` (which can be backed by physical JSON or database storage) for permanent persistence.

```python
from yasin_core.memory import InMemoryShortTermMemory, InMemoryLongTermMemory
from yasin_core.memory.persistent import StorageBackedLongTermMemory
from yasin_core.storage.json_file import JSONFileStorage

# 1. Short-Term Session-specific Memory
session_memory = InMemoryShortTermMemory()
session_memory.set("current_conversation_id", "conv_abc_123")
session_memory.set("history", ["user: Hi", "agent: Hello! How can I help you?"])

# 2. Persistent Long-Term Memory
# Initialize a physical storage adapter (e.g., local JSON storage)
storage = JSONFileStorage(filepath="data/long_term_memory.json")
long_term_memory = StorageBackedLongTermMemory(storage=storage)

# Store persistent agent settings or learned facts
long_term_memory.set("agent_profile_name", "YasinHelper")
long_term_memory.set("user_preference_theme", "dark")
```

---

## 4. Context Usage

Yasin-Core leverages `contextvars` to isolate and propagate session context across execution flows, threads, or asynchronous tasks without polluting function signatures.

```
       [ YasinRuntime ]
              │
    [ active_context(Context) ]
              │
     ┌────────┴────────┐
     ▼                 ▼
[ Plugin ]        [ Provider ]  (Query active_context thread-safely)
```

### Interface Definitions

#### `Context`
Manages standard dictionary key-value access to context properties:

```python
class Context:
    def __init__(self, data: Dict[str, Any] = None): ...
    def get(self, key: str, default: Any = None) -> Any: ...
    def set(self, key: str, value: Any) -> None: ...
    def delete(self, key: str) -> None: ...
    def clear(self) -> None: ...
    def to_dict(self) -> Dict[str, Any]: ...
```

#### Context Scope Utility Context Manager

- `active_context(context: Context)`: Context manager to set active scope.
- `get_current_context() -> Context`: Retrieves the currently active Context.

### Runtime Context Propagation Flow & Code Example

External callers or plugins wrap executions in an `active_context` block. Any component down the execution tree can query this context.

```python
from yasin_core.context import Context, active_context, get_current_context

def deep_nested_service():
    # 2. Access variables thread-safely anywhere downstream
    context = get_current_context()
    auth_token = context.get("auth_token")
    request_id = context.get("request_id")
    return f"Request {request_id} processed using Auth token {auth_token}"

# 1. Bind Context inside execution thread
run_context = Context({
    "auth_token": "bearer_super_secret_token_abc123",
    "request_id": "req-999"
})

with active_context(run_context):
    result = deep_nested_service()
    assert result == "Request req-999 processed using Auth token bearer_super_secret_token_abc123"
```

---

## 5. Provider Integration

AI Providers abstract external LLM and Cognitive models. While integration with concrete providers like OpenAI, Ollama, or HuggingFace will connect in future releases, they will all conform to the `AIProvider` base contract.

### Interface Definitions

#### `AIProvider`

```python
class AIProvider(ABC):
    name: str = "base"

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """Submit prompt to LLM and return the model completion string."""
        pass
```

### Provider Flow & Future Integration Example

External cognitive integrations will define custom subclasses of `AIProvider`. The agent instances query these providers to obtain completions, while reading and writing back to Core short-term and long-term memory.

```python
from yasin_core.providers.base import AIProvider

# Concrete implementation example for a custom LLM Provider
class OllamaAIProvider(AIProvider):
    name = "ollama"

    def __init__(self, model_name: str = "llama3"):
        self.model_name = model_name

    def generate(self, prompt: str) -> str:
        # In actual integration:
        # 1. Fetch current_context for system instructions or api_keys
        # 2. Make REST/SDK call to Ollama instance
        # 3. Return generated text completion
        return f"[Ollama {self.model_name}] Completion for: '{prompt}'"

# Usage of provider inside an agent's execute loop
class CognitionAgent(BaseAgent):
    def __init__(self, name: str, provider: AIProvider):
        super().__init__(name)
        self.provider = provider

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        prompt = input_data.get("prompt", "")
        return self.provider.generate(prompt)
```

---

## Architecture Flow Overview

```
                          ┌──────────────────────────┐
                          │       YasinRuntime       │
                          └─────────────┬────────────┘
                                        │ (Boots up)
                                        ▼
                          ┌──────────────────────────┐
                          │      Active Context      │
                          └─────────────┬────────────┘
                                        │ (Propagates vars)
                                        ▼
                          ┌──────────────────────────┐
                          │      Task Executor       │
                          └─────────────┬────────────┘
                                        │ (Runs Task)
                                        ▼
                          ┌──────────────────────────┐
                          │       BaseAgent          │
                          └───────┬─────┬─────┬──────┘
                                  │     │     │
            ┌─────────────────────┘     │     └─────────────────────┐
            ▼                           ▼                           ▼
 ┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
 │    Memory Layer     │     │   AIProvider Layer  │     │    Event Bus/PubSub │
 │ (Session/Persist)   │     │ (LLM/Completions)   │     │ (State transition)  │
 └─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

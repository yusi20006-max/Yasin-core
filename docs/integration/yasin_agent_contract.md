# Yasin-Agent Integration Contract v1.0

This document defines the stable integration contract between **Yasin-Core** and external agent runtimes, specifically **Yasin-Agent**, utilizing the **Yasin-Core SDK v1.0**.

As Yasin-Core serves as the central runtime and infrastructure layer of the Yasin AI Ecosystem, external systems must adhere to these public SDK contracts to ensure seamless interoperability, lifecycle management, context propagation, and state persistence.

---

## 1. SDK Client Initialization

External systems and agents interact with the Yasin-Core runtime using the public `YasinCoreClient` client. This shields external developers from internal changes to underlying agent registries, planners, memory managers, and AI model providers.

### Initialization Flow

```python
from yasin_core.sdk import YasinCoreClient

# Initialize the public SDK Client
client = YasinCoreClient()
```

---

## 2. Agent Registration & Lifecycle Management

Agents are created using the public `BaseAgent` class and registered directly using `YasinCoreClient`.

### Interface Definitions

#### `BaseAgent` (Abstract Base Class)
Any agent implementing this contract must inherit from `BaseAgent`, imported from `yasin_core.sdk`:

```python
from yasin_core.sdk import BaseAgent

class CustomAgent(BaseAgent):
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
```

### Registration & Lifecycle Flow

To register and manage an external agent with Yasin-Core:

```python
# 1. Register the agent
my_agent = CustomAgent(name="custom-agent", description="An external agent")
client.register_agent(my_agent)

# 2. Control agent lifecycle
client.start_agents()
assert my_agent.running is True

client.stop_agents()
assert my_agent.running is False
```

---

## 3. Task Execution

The task execution layer in Yasin-Core handles workflow orchestrations. External applications submit, track, and execute tasks via the client SDK.

### Interface Definitions

#### `Task`
Represents the unit of work submitted to the system:

```python
from yasin_core.sdk import Task
```

### Task Execution Flow & Code Example

```python
# 1. Instantiate the Task using the SDK client
task = client.create_task(
    id="task-001",
    name="custom-agent",
    input_data={"query": "Hello Yasin!"}
)

# 2. Execute the Task via the client
executed_task = client.execute_task(task)

# 3. Verify output
assert executed_task.status == "completed"
assert executed_task.result == "Processed query: Hello Yasin!"
```

---

## 4. Memory Access

Yasin-Core provides a structured memory abstraction layer separating short-term and long-term state. All memory reads and writes are performed through the public SDK client.

### Memory Retrieval and Storage Flow & Code Example

```python
# 1. Short-Term Memory
client.save_memory("current_conversation_id", "conv_abc_123", category="short-term")
assert client.get_memory("current_conversation_id", category="short-term") == "conv_abc_123"

# 2. Long-Term Memory
client.save_memory("agent_profile_name", "YasinHelper", category="long-term")
assert client.get_memory("agent_profile_name", category="long-term") == "YasinHelper"
```

---

## 5. Context Usage

Yasin-Core leverages thread-local contextvars to isolate and propagate session context across execution flows. Applications wrap execution flows in an `active_context` block using context propagation utilities imported from `yasin_core.sdk`.

### Context Propagation Flow & Code Example

```python
from yasin_core.sdk import active_context, get_current_context

# 1. Bind Context inside execution thread
run_context = client.create_context({
    "auth_token": "bearer_super_secret_token_abc123",
    "request_id": "req-999"
})

def deep_nested_service():
    # Access variables thread-safely anywhere downstream
    context = get_current_context()
    auth_token = context.get("auth_token")
    request_id = context.get("request_id")
    return f"Request {request_id} processed using Auth token {auth_token}"

with active_context(run_context):
    result = deep_nested_service()
    assert result == "Request req-999 processed using Auth token bearer_super_secret_token_abc123"
```

# Agent Runtime Integration Layer (Yasin-Core v3.0)

The Agent Runtime Integration Layer in Yasin-Core v3.0 defines a stable, thread-safe, and unified contract allowing Yasin-Agent and other third-party ecosystem components to register, manage, and execute agents through standard public SDK APIs.

## Architecture & Design

```
+-------------------------------------------------------------+
|                      YasinCoreClient                        |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                    IAgentRuntime Interface                  |
+-------------------------------------------------------------+
                              |
                              v
+-------------------------------------------------------------+
|                       AgentRuntime                          |
+-------------------------------------------------------------+
     |                  |               |                |
     v                  v               v                v
+----------+     +------------+   +-----------+    +------------+
| Security |     | ContextVar |   | Memory ST |    | Metrics /  |
| (RBAC)   |     | Contexts   |   | & LT      |    | Monitoring |
+----------+     +------------+   +-----------+    +------------+
```

### Key Components

1. **`IAgentRuntime` & `AgentRuntime`**: Defined in `yasin_core/agents/runtime.py`, this is registered inside `RuntimeServiceRegistry` and `DIContainer` during client construction. It exposes a set of thread-safe methods for registering, removing, and executing agents.
2. **Backward-Compatible `BaseAgent` Extensions**: The baseline `BaseAgent` is extended with:
   - `capabilities`: List of string tags for capability-based agent discovery.
   - `permissions`: List of required security permissions.
   - `state`: Internal state dictionary, persisted cleanly via standard storage backend.
   - `inbox`: Thread-safe `queue.Queue` allowing asynchronous message passing between agents.

---

## Public SDK API Reference

### Accessing the Runtime
The agent runtime is exposed on the public client:
```python
from yasin_core.sdk import YasinCoreClient

client = YasinCoreClient()
runtime = client.agent_runtime
```

### Registration & Discovery
```python
# Register an agent
runtime.register_agent(agent)

# List names of all registered agents
agents = runtime.list_agents()

# Retrieve a specific agent
agent = runtime.get_agent("my-agent")

# Discover agents possessing a capability
agents_with_math = runtime.discover_agents_by_capability("math")
```

### State Management
Persist and restore agent internal state dictionaries seamlessly through the standard storage backend:
```python
# Save state to persistent/in-memory storage
runtime.save_agent_state("my-agent")

# Restore state from storage
runtime.load_agent_state("my-agent")
```

### Communication Layer (Agent Messaging)
Agents can communicate safely across threads:
```python
# Send a message to another agent's inbox
runtime.send_agent_message(sender="agent-a", receiver="agent-b", message="Hello Agent B!")

# Retrieve (drain) messages for an agent
messages = runtime.retrieve_agent_messages("agent-b")
```

### Execution, Metrics, & Context
```python
# Execute task with active context propagation and auto-memory persistence
context = client.create_context({"prefix": "Prefix"})
with active_context(context):
    task = client.create_task(id="task-1", name="my-agent", input_data={"data": "hi"})
    executed_task = client.execute_task(task)
```
During execution:
- Execution metrics (`agent_execution_total`, `agent_execution_duration`) are automatically tracked via the Observability subsystem.
- Outcome values are automatically saved into short-term and long-term memory.
- RBAC permissions are validated prior to execution.

import pytest
from typing import Any, Dict

from yasin_core.sdk import YasinCoreClient, BaseAgent, Task, active_context, get_current_context


class E2ETestAgent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        # Check current context if available
        context = get_current_context()
        prefix = context.get("prefix", "E2E Result")
        data = input_data.get("data", "")
        return f"{prefix}: {data}"


def test_agent_runtime_e2e():
    # Initialize public SDK client
    client = YasinCoreClient()

    # 1. Create a simple test Agent using the existing BaseAgent interface.
    agent = E2ETestAgent(name="e2e-agent", description="Agent for End-to-End integration test")

    # 2. Register the Agent using YasinCoreClient.
    client.register_agent(agent)

    # Verify agent is initially stopped
    assert not agent.running

    # Verify agent lifecycle works (start/stop) through YasinCoreClient
    client.start_agents()
    assert agent.running
    client.stop_agents()
    assert not agent.running

    # 3. Create a Task through the SDK client.
    task = client.create_task(id="task-e2e-1", name="e2e-agent", input_data={"data": "success"})
    assert task.status == "pending"

    # Use active context to supply contextual information to the execution
    context = client.create_context({"prefix": "Custom Prefix"})
    with active_context(context):
        # 4. Execute the Task using Executor through YasinCoreClient.
        executed_task = client.execute_task(task)

        # 5. Verify:
        # - Task status changes correctly.
        assert executed_task.status == "completed"
        # - Result is returned.
        assert executed_task.result == "Custom Prefix: success"
        assert executed_task.error is None

        # - Agent lifecycle works (the executor should auto-start the agent if it was stopped)
        assert agent.running

    # Stop agents after testing
    client.stop_agents()
    assert not agent.running

    # - Memory can store the result.
    client.save_memory(executed_task.id, executed_task.result, category="short-term")
    client.save_memory(executed_task.id, executed_task.result, category="long-term")

    # - Stored memory can be retrieved.
    assert client.get_memory(executed_task.id, category="short-term") == "Custom Prefix: success"
    assert client.get_memory(executed_task.id, category="long-term") == "Custom Prefix: success"


def test_sdk_integration_explicit():
    # Verify SDK client initialization
    client = YasinCoreClient()
    assert client is not None

    # Verify agent registration
    agent = E2ETestAgent(name="explicit-test-agent", description="Explicit integration test agent")
    client.register_agent(agent)
    assert "explicit-test-agent" in client.list_agents()
    assert client.get_agent("explicit-test-agent") == agent

    # Verify task execution
    task = client.create_task(id="task-explicit", name="explicit-test-agent", input_data={"data": "explicit"})
    executed_task = client.execute_task(task)
    assert executed_task.status == "completed"
    assert executed_task.result == "E2E Result: explicit"

    # Verify memory access through SDK
    client.save_memory("explicit_key", "explicit_value", category="short-term")
    assert client.get_memory("explicit_key", category="short-term") == "explicit_value"

    client.save_memory("explicit_long_key", "explicit_long_value", category="long-term")
    assert client.get_memory("explicit_long_key", category="long-term") == "explicit_long_value"

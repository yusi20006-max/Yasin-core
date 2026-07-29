import pytest
from typing import Any, Dict

from yasin_core.agents.base import BaseAgent
from yasin_core.agents.manager import AgentManager
from yasin_core.agents.task import Task
from yasin_core.agents.planner import SimplePlanner
from yasin_core.agents.executor import TaskExecutor
from yasin_core.memory import InMemoryShortTermMemory, InMemoryLongTermMemory
from yasin_core.context import Context, active_context, get_current_context


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
    # 1. Create a simple test Agent using the existing BaseAgent interface.
    agent = E2ETestAgent(name="e2e-agent", description="Agent for End-to-End integration test")

    # 2. Register the Agent using AgentManager.
    manager = AgentManager()
    manager.register_agent(agent)

    # Verify agent is initially stopped
    assert not agent.running

    # Verify agent lifecycle works (start/stop)
    manager.start_agents()
    assert agent.running
    manager.stop_agents()
    assert not agent.running

    # 3. Create a Task.
    task = Task(id="task-e2e-1", name="e2e-agent", input_data={"data": "success"})
    assert task.status == "pending"

    # Use active context to supply contextual information to the execution
    context = Context({"prefix": "Custom Prefix"})
    with active_context(context):
        # 4. Pass the Task through Planner.
        planner = SimplePlanner()
        plan = planner.plan(task)
        assert plan["agent_name"] == "e2e-agent"
        assert plan["payload"] == {"data": "success"}

        # 5. Execute the Task using Executor.
        executor = TaskExecutor(agent_manager=manager, planner=planner)
        executed_task = executor.execute_task(task)

        # 6. Verify:
        # - Task status changes correctly.
        assert executed_task.status == "completed"
        # - Result is returned.
        assert executed_task.result == "Custom Prefix: success"
        assert executed_task.error is None

        # - Agent lifecycle works (the executor should auto-start the agent if it was stopped)
        assert agent.running

    # Stop agents after testing
    manager.stop_agents()
    assert not agent.running

    # - Memory can store the result.
    short_term_mem = InMemoryShortTermMemory()
    long_term_mem = InMemoryLongTermMemory()

    short_term_mem.set(executed_task.id, executed_task.result)
    long_term_mem.set(executed_task.id, executed_task.result)

    # - Stored memory can be retrieved.
    assert short_term_mem.get(executed_task.id) == "Custom Prefix: success"
    assert long_term_mem.get(executed_task.id) == "Custom Prefix: success"

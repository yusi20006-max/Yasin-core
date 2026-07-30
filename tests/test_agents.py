import pytest
from typing import Any, Dict
from yasin_core.agents.base import BaseAgent
from yasin_core.agents.task import Task
from yasin_core.agents.manager import AgentRegistry, AgentManager
from yasin_core.agents.planner import SimplePlanner
from yasin_core.agents.executor import TaskExecutor, Executor


class DummyAgent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        if input_data.get("fail", False):
            raise ValueError("Intentional failure")
        return f"Processed: {input_data.get('data', '')}"


def test_agent_registration():
    registry = AgentRegistry()
    agent = DummyAgent(name="dummy", description="A dummy agent for testing")

    # Registration
    registry.register(agent)
    assert "dummy" in registry.list()
    assert registry.get("dummy") == agent

    # Manager integration
    manager = AgentManager(registry)
    assert manager.get_agent("dummy") == agent
    assert "dummy" in manager.list_agents()

    # Removal
    removed = manager.remove_agent("dummy")
    assert removed == agent
    assert "dummy" not in manager.list_agents()


def test_agent_lifecycle():
    manager = AgentManager()
    agent = DummyAgent(name="dummy")
    manager.register_agent(agent)

    # Initially stopped
    assert not agent.running

    # Start agents
    manager.start_agents()
    assert agent.running

    # Stop agents
    manager.stop_agents()
    assert not agent.running


def test_task_creation():
    task = Task(id="task-1", name="dummy", input_data={"data": "hello"})
    assert task.id == "task-1"
    assert task.name == "dummy"
    assert task.input_data == {"data": "hello"}
    assert task.status == "pending"
    assert task.result is None
    assert task.error is None

    # Conversion to dict
    d = task.to_dict()
    assert d["id"] == "task-1"
    assert d["status"] == "pending"


def test_task_execution_success():
    manager = AgentManager()
    agent = DummyAgent(name="dummy")
    manager.register_agent(agent)

    executor = TaskExecutor(agent_manager=manager)
    task = Task(id="task-1", name="dummy", input_data={"data": "hello"})

    executed_task = executor.execute_task(task)
    assert executed_task.status == "completed"
    assert executed_task.result == "Processed: hello"
    assert executed_task.error is None
    # Verify the executor auto-started the agent if it was stopped
    assert agent.running


def test_task_execution_failure_agent_error():
    manager = AgentManager()
    agent = DummyAgent(name="dummy")
    manager.register_agent(agent)

    executor = TaskExecutor(agent_manager=manager)
    task = Task(id="task-2", name="dummy", input_data={"fail": True})

    executed_task = executor.execute_task(task)
    assert executed_task.status == "failed"
    assert executed_task.result is None
    assert "Intentional failure" in executed_task.error


def test_task_execution_failure_missing_agent():
    manager = AgentManager()
    executor = TaskExecutor(agent_manager=manager)
    task = Task(id="task-3", name="nonexistent")

    executed_task = executor.execute_task(task)
    assert executed_task.status == "failed"
    assert "Agent 'nonexistent' not found." in executed_task.error


def test_planner_flow():
    planner = SimplePlanner()
    task = Task(id="task-4", name="dummy", input_data={"agent_name": "special-agent", "data": "custom"})
    plan = planner.plan(task)

    assert plan["agent_name"] == "special-agent"
    assert plan["payload"] == {"agent_name": "special-agent", "data": "custom"}

    # Fallback to task name if agent_name is not in input_data
    task_no_agent = Task(id="task-5", name="fallback-agent", input_data={"data": "custom"})
    plan_no_agent = planner.plan(task_no_agent)
    assert plan_no_agent["agent_name"] == "fallback-agent"


def test_executor_alias():
    manager = AgentManager()
    agent = DummyAgent(name="dummy")
    manager.register_agent(agent)

    # Use 'Executor' class alias
    executor = Executor(agent_manager=manager)
    task = Task(id="task-6", name="dummy", input_data={"data": "alias"})

    executed_task = executor.execute_task(task)
    assert executed_task.status == "completed"
    assert executed_task.result == "Processed: alias"

import pytest
from yasin_core.agents import (
    BaseAgent,
    Task,
    AgentManager,
    SimplePlanner,
    TaskExecutor,
)


class MockAgent(BaseAgent):


    def execute(self, task: Task):

        if task.input_data.get("should_fail"):

            raise ValueError("Intentional execution error")

        return f"Hello, {task.name}! Processed input: {task.input_data.get('data')}"


def test_agent_registration():

    manager = AgentManager()

    agent1 = MockAgent("Agent1", "First mock agent")

    agent2 = MockAgent("Agent2", "Second mock agent")


    # Register
    manager.register_agent(agent1)

    manager.register_agent(agent2)


    # Retrieve
    assert manager.get_agent("Agent1") == agent1

    assert manager.get_agent("Agent2") == agent2

    assert len(manager.list_agents()) == 2


    # Remove
    manager.remove_agent("Agent1")

    assert manager.get_agent("Agent1") is None

    assert len(manager.list_agents()) == 1


def test_agent_lifecycle():

    manager = AgentManager()

    agent = MockAgent("LifecycleAgent")

    manager.register_agent(agent)


    assert agent.running is False


    # Start single
    manager.start_agent("LifecycleAgent")

    assert agent.running is True


    # Stop single
    manager.stop_agent("LifecycleAgent")

    assert agent.running is False


    # Start all / Stop all
    manager.start_all()

    assert agent.running is True


    manager.stop_all()

    assert agent.running is False


def test_task_creation():

    task = Task("TestTask", {"data": "my_input"})

    assert task.name == "TestTask"

    assert task.input_data == {"data": "my_input"}

    assert task.status == "pending"

    assert task.id is not None

    assert task.result is None

    assert task.error is None


def test_planner_flow():

    manager = AgentManager()

    agent = MockAgent("AutoAgent")

    manager.register_agent(agent)


    planner = SimplePlanner()

    task = Task("PlanTask", {"data": "some_data"})


    # Planning should auto-assign the first registered agent if none is provided
    planned_task = planner.plan(task, manager)

    assert planned_task.status == "planned"

    assert planned_task.input_data["agent_name"] == "AutoAgent"


def test_task_execution_success():

    manager = AgentManager()

    agent = MockAgent("SuccessAgent")

    manager.register_agent(agent)

    manager.start_all()


    task = Task("GreetTask", {"agent_name": "SuccessAgent", "data": "yes"})

    executor = TaskExecutor()


    executed_task = executor.execute(task, manager)

    assert executed_task.status == "completed"

    assert executed_task.result == "Hello, GreetTask! Processed input: yes"

    assert executed_task.error is None


def test_task_execution_failure_handling():

    manager = AgentManager()

    agent = MockAgent("FailAgent")

    manager.register_agent(agent)

    manager.start_all()


    executor = TaskExecutor()


    # 1. Failure: Agent not found
    task1 = Task("Task1", {"agent_name": "NonExistentAgent"})

    executed1 = executor.execute(task1, manager)

    assert executed1.status == "failed"

    assert "not found" in executed1.error


    # 2. Failure: Agent is not running
    manager.stop_agent("FailAgent")

    task2 = Task("Task2", {"agent_name": "FailAgent"})

    executed2 = executor.execute(task2, manager)

    assert executed2.status == "failed"

    assert "is not running" in executed2.error


    # 3. Failure: Agent throws exception during execution
    manager.start_agent("FailAgent")

    task3 = Task("Task3", {"agent_name": "FailAgent", "should_fail": True})

    executed3 = executor.execute(task3, manager)

    assert executed3.status == "failed"

    assert "Intentional execution error" in executed3.error


    # 4. Failure: No agent name assigned
    task4 = Task("Task4")

    executed4 = executor.execute(task4, manager)

    assert executed4.status == "failed"

    assert "No agent assigned" in executed4.error

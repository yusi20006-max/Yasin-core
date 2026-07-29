from typing import Dict, Any
from yasin_core.sdk import YasinCoreClient
from yasin_core.agents import BaseAgent, Task


class DummyAgent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        if input_data.get("fail", False):
            raise ValueError("Intentional failure")
        return f"Processed: {input_data.get('data', '')}"


def test_sdk_import_and_creation():
    client = YasinCoreClient()
    assert client is not None


def test_sdk_version_methods():
    client = YasinCoreClient()
    assert client.get_version() == "0.4.1"
    assert client.version == "0.4.1"


def test_sdk_info_methods():
    client = YasinCoreClient()
    info_dict = client.get_info()
    assert info_dict["name"] == "Yasin Core SDK Client"
    assert info_dict["version"] == "0.4.1"
    info_dict_alt = client.info()
    assert info_dict_alt == info_dict


def test_sdk_agent_operations():
    client = YasinCoreClient()
    agent = DummyAgent(name="test-agent", description="A test agent via SDK")

    # register agent through SDK
    client.register_agent(agent)
    assert "test-agent" in client.list_agents()

    # retrieve agent through SDK
    retrieved_agent = client.get_agent("test-agent")
    assert retrieved_agent == agent


def test_sdk_task_operations():
    client = YasinCoreClient()
    agent = DummyAgent(name="test-agent", description="A test agent via SDK")
    client.register_agent(agent)

    # create task through SDK
    task = client.create_task(id="task-100", name="test-agent", input_data={"data": "sdk-test"})
    assert isinstance(task, Task)
    assert task.id == "task-100"
    assert task.name == "test-agent"
    assert task.input_data == {"data": "sdk-test"}
    assert task.status == "pending"

    # execute task through SDK
    executed_task = client.execute_task(task)
    assert executed_task.status == "completed"
    assert executed_task.result == "Processed: sdk-test"
    assert executed_task.error is None

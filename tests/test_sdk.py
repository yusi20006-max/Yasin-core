from typing import Dict, Any
import pytest
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
    assert client.get_version() == "3.0.0"
    assert client.version == "3.0.0"


def test_sdk_info_methods():
    client = YasinCoreClient()
    info_dict = client.get_info()
    assert info_dict["name"] == "Yasin Core SDK Client"
    assert info_dict["version"] == "3.0.0"
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


def test_sdk_memory_operations():
    client = YasinCoreClient()

    # Test short-term memory write and read
    client.save_memory("short_key", "short_val")
    assert client.get_memory("short_key") == "short_val"
    assert client.get_memory("short_key", category="short-term") == "short_val"

    # Test long-term memory write and read
    client.save_memory("long_key", "long_val", category="long-term")
    assert client.get_memory("long_key", category="long-term") == "long_val"

    # Check default values
    assert client.get_memory("nonexistent") is None
    assert client.get_memory("nonexistent", default="fallback") == "fallback"
    assert client.get_memory("nonexistent", category="long-term") is None
    assert client.get_memory("nonexistent", default="fallback", category="long-term") == "fallback"


def test_sdk_memory_custom_backends():
    from yasin_core.memory import InMemoryShortTermMemory, InMemoryLongTermMemory

    custom_short = InMemoryShortTermMemory()
    custom_long = InMemoryLongTermMemory()

    client = YasinCoreClient(short_term_memory=custom_short, long_term_memory=custom_long)

    client.save_memory("k", "v", category="short-term")
    assert custom_short.get("k") == "v"

    client.save_memory("kl", "vl", category="long-term")
    assert custom_long.get("kl") == "vl"


def test_sdk_context_operations():
    client = YasinCoreClient()

    # Create context without initial data
    ctx = client.create_context()
    assert ctx is not None
    assert ctx.to_dict() == {}

    # Create context with initial data
    initial_data = {"user_id": "user-123", "session_id": "sess-456"}
    ctx_with_data = client.create_context(data=initial_data)
    assert ctx_with_data is not None
    assert ctx_with_data.get("user_id") == "user-123"
    assert ctx_with_data.to_dict() == initial_data

    # Test context data passing / operations
    ctx_with_data.set("new_key", "new_val")
    assert ctx_with_data.get("new_key") == "new_val"

    ctx_with_data.delete("user_id")
    assert ctx_with_data.get("user_id") is None

    ctx_with_data.clear()
    assert ctx_with_data.to_dict() == {}


def test_sdk_context_propagation():
    from yasin_core.context import active_context, get_current_context
    client = YasinCoreClient()

    ctx = client.create_context({"env": "production", "debug": False})

    with active_context(ctx):
        current_ctx = get_current_context()
        assert current_ctx.get("env") == "production"
        assert current_ctx.get("debug") is False


def test_sdk_memory_invalid_category():
    client = YasinCoreClient()
    with pytest.raises(ValueError):
        client.save_memory("k", "v", category="invalid")

    with pytest.raises(ValueError):
        client.get_memory("k", category="invalid")

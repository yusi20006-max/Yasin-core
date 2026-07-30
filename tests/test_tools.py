# Progress: [██████████] 100%

import pytest
from typing import Dict, Any, List
from yasin_core.sdk import YasinCoreClient, BaseAgent
from yasin_core.agents.tool import BaseTool, FunctionTool, tool, ToolRegistry, ToolManager


# 1. Custom tool subclass for testing
class AddTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="add_tool",
            description="Adds two numbers together",
            args_schema={"a": "number", "b": "number"}
        )

    def execute(self, a: int, b: int) -> int:
        return a + b


def test_base_tool_contract():
    add = AddTool()
    assert add.name == "add_tool"
    assert add.description == "Adds two numbers together"
    assert add.args_schema == {"a": "number", "b": "number"}

    # Execute directly
    assert add.execute(5, 7) == 12

    # Execute via __call__ fallback
    assert add(10, 20) == 30


# 2. Tool decorator tests
def test_tool_decorator_no_args():
    @tool
    def greet(name: str) -> str:
        """Greets the user by name."""
        return f"Hello, {name}!"

    assert isinstance(greet, FunctionTool)
    assert greet.name == "greet"
    assert greet.description == "Greets the user by name."
    assert greet.args_schema == {}
    assert greet("Yasin") == "Hello, Yasin!"


def test_tool_decorator_with_args():
    @tool(name="custom_multiply", description="Multiplies numbers", args_schema={"x": "int", "y": "int"})
    def multiply(x: int, y: int) -> int:
        return x * y

    assert isinstance(multiply, FunctionTool)
    assert multiply.name == "custom_multiply"
    assert multiply.description == "Multiplies numbers"
    assert multiply.args_schema == {"x": "int", "y": "int"}
    assert multiply(3, 4) == 12


# 3. Tool registry and manager tests
def test_tool_registry_and_manager():
    registry = ToolRegistry()
    manager = ToolManager(registry=registry)

    # Register
    add = AddTool()
    manager.register_tool(add)
    assert "add_tool" in manager.list_tools()
    assert manager.get_tool("add_tool") == add

    # Execute tool
    result = manager.execute_tool("add_tool", a=10, b=15)
    assert result == 25

    # Remove tool
    removed = manager.remove_tool("add_tool")
    assert removed == add
    assert "add_tool" not in manager.list_tools()

    # Executing removed tool should raise ValueError
    with pytest.raises(ValueError):
        manager.execute_tool("add_tool", a=1, b=2)


# 4. YasinCoreClient integration tests
def test_sdk_client_tool_operations():
    client = YasinCoreClient()

    # Check tool list initially empty
    assert client.list_tools() == []

    # Register tool
    @tool(name="echo")
    def echo_text(text: str) -> str:
        return text

    client.register_tool(echo_text)
    assert "echo" in client.list_tools()
    assert client.get_tool("echo") == echo_text

    # Execute tool via SDK client
    assert client.execute_tool("echo", text="test-sdk") == "test-sdk"


# 5. Backward compatibility for BaseAgent with tools parameter
class DummyAgent(BaseAgent):
    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        return "done"


def test_base_agent_tools_compatibility():
    # 1. Without tools parameter (legacy usage)
    agent_legacy = DummyAgent(name="legacy-agent", description="No tools")
    assert agent_legacy.name == "legacy-agent"
    assert agent_legacy.tools == []

    # 2. With tools parameter
    my_tool = AddTool()
    agent_with_tools = DummyAgent(name="tool-agent", description="With tools", tools=[my_tool])
    assert agent_with_tools.name == "tool-agent"
    assert agent_with_tools.tools == [my_tool]

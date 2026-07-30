import os
import tempfile
import pytest
from typing import Dict, Any
from yasin_core.sdk import YasinCoreClient, PluginExecutionBridge, Task
from yasin_core.plugins import YasinPlugin


# Define some test plugins
class TestMathPlugin(YasinPlugin):
    name = "test_math"

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        return input_data.get("a", 0) + input_data.get("b", 0)


class TestNonExecutablePlugin(YasinPlugin):
    name = "test_invalid"

    def start(self):
        pass

    def stop(self):
        pass


def test_plugin_registration_and_lookup():
    client = YasinCoreClient()
    plugin = TestMathPlugin()

    # Register
    client.register_plugin(plugin)

    # Lookup
    retrieved = client.get_plugin("test_math")
    assert retrieved == plugin
    assert "test_math" in client.list_plugins()


def test_plugin_execution_via_bridge():
    client = YasinCoreClient()
    plugin = TestMathPlugin()
    client.register_plugin(plugin)

    # Setup the bridge as an Agent
    bridge = PluginExecutionBridge(
        name="math-agent",
        plugin_registry=client._plugin_registry,
        plugin_name="test_math"
    )
    client.register_agent(bridge)

    # Execute a task using the agent execution pipeline
    task = client.create_task(
        id="t-plugin-exec",
        name="math-agent",
        input_data={"a": 5, "b": 7}
    )
    executed_task = client.execute_task(task)

    assert executed_task.status == "completed"
    assert executed_task.result == 12


def test_plugin_discovery():
    client = YasinCoreClient()

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a sample plugin file in the temp directory
        plugin_code = """
from yasin_core.plugins import YasinPlugin

class AutoDiscoveredPlugin(YasinPlugin):
    name = "auto_discovered"

    def start(self):
        pass

    def stop(self):
        pass

    def execute(self, input_data):
        return f"Auto: {input_data.get('text', '')}"
"""
        plugin_filepath = os.path.join(tmpdir, "discovered_plugin.py")
        with open(plugin_filepath, "w", encoding="utf-8") as f:
            f.write(plugin_code)

        # Run discovery on the temp directory
        client.discover_plugins(plugins_dir=tmpdir)

        # Confirm the plugin was auto-discovered and registered
        discovered = client.get_plugin("auto_discovered")
        assert discovered is not None
        assert discovered.name == "auto_discovered"

        # Verify execution
        bridge = PluginExecutionBridge(
            name="auto-agent",
            plugin_registry=client._plugin_registry,
            plugin_name="auto_discovered"
        )
        client.register_agent(bridge)

        task = client.create_task(
            id="t-auto-exec",
            name="auto-agent",
            input_data={"text": "hello"}
        )
        executed = client.execute_task(task)
        assert executed.status == "completed"
        assert executed.result == "Auto: hello"


def test_plugin_execution_errors():
    client = YasinCoreClient()

    # 1. Missing plugin execution error
    bridge = PluginExecutionBridge(
        name="missing-agent",
        plugin_registry=client._plugin_registry,
        plugin_name="does_not_exist"
    )
    client.register_agent(bridge)

    task = client.create_task(
        id="t-err-1",
        name="missing-agent",
        input_data={}
    )
    executed = client.execute_task(task)
    assert executed.status == "failed"
    assert "not found" in executed.error

    # 2. Non-executable plugin execution error
    non_exec_plugin = TestNonExecutablePlugin()
    client.register_plugin(non_exec_plugin)

    invalid_bridge = PluginExecutionBridge(
        name="invalid-agent",
        plugin_registry=client._plugin_registry,
        plugin_name="test_invalid"
    )
    client.register_agent(invalid_bridge)

    task2 = client.create_task(
        id="t-err-2",
        name="invalid-agent",
        input_data={}
    )
    executed2 = client.execute_task(task2)
    assert executed2.status == "failed"
    assert "is not executable" in executed2.error

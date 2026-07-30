from typing import Dict, Any
from yasin_core.agents.base import BaseAgent


class PluginExecutionBridge(BaseAgent):
    """Bridge that allows executing a Plugin through the Agent Runtime."""

    def __init__(self, name: str, plugin_registry, plugin_name: str, description: str = ""):
        super().__init__(name=name, description=description)
        self.plugin_registry = plugin_registry
        self.plugin_name = plugin_name

    def start(self) -> None:
        self.running = True
        plugin = self.plugin_registry.get(self.plugin_name)
        if plugin and hasattr(plugin, "start"):
            plugin.start()

    def stop(self) -> None:
        self.running = False
        plugin = self.plugin_registry.get(self.plugin_name)
        if plugin and hasattr(plugin, "stop"):
            plugin.stop()

    def execute(self, input_data: Dict[str, Any]) -> Any:
        plugin = self.plugin_registry.get(self.plugin_name)
        if not plugin:
            raise ValueError(f"Plugin '{self.plugin_name}' not found in registry.")

        if hasattr(plugin, "execute"):
            return plugin.execute(input_data)
        elif hasattr(plugin, "run"):
            return plugin.run(input_data)
        elif callable(plugin):
            return plugin(input_data)
        else:
            raise AttributeError(
                f"Plugin '{self.plugin_name}' is not executable (no execute/run method and not callable)."
            )

# Progress: [████████░░] 80%

from typing import Optional, List, Dict, Any
from yasin_core.version import VERSION
from yasin_core.agents import AgentManager, Task, TaskExecutor, BaseAgent
from yasin_core.providers import AIProvider, ProviderManager
from yasin_core.agents.tool import BaseTool, ToolManager


class YasinCoreClient:
    def __init__(self, short_term_memory=None, long_term_memory=None):
        self._version = VERSION
        self._agent_manager = AgentManager()
        self._executor = TaskExecutor(agent_manager=self._agent_manager)
        self._provider_manager = ProviderManager()
        self._tool_manager = ToolManager()

        from yasin_core.memory import InMemoryShortTermMemory, InMemoryLongTermMemory
        self._short_term_memory = short_term_memory or InMemoryShortTermMemory()
        self._long_term_memory = long_term_memory or InMemoryLongTermMemory()

    @property
    def version(self) -> str:
        return self._version

    def get_version(self) -> str:
        return self._version

    def info(self) -> dict:
        return self.get_info()

    def get_info(self) -> dict:
        return {
            "name": "Yasin Core SDK Client",
            "version": self._version
        }

    # Agent Operations
    def register_agent(self, agent: BaseAgent) -> None:
        """Register a new agent with the internal AgentManager."""
        self._agent_manager.register_agent(agent)

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Retrieve a registered agent by name."""
        return self._agent_manager.get_agent(name)

    def list_agents(self) -> List[str]:
        """List names of all registered agents."""
        return self._agent_manager.list_agents()

    def start_agents(self) -> None:
        """Start all registered agents."""
        self._agent_manager.start_agents()

    def stop_agents(self) -> None:
        """Stop all registered agents."""
        self._agent_manager.stop_agents()

    # Task Operations
    def create_task(self, id: str, name: str, input_data: Optional[Dict[str, Any]] = None) -> Task:
        """Create a new Task instance."""
        return Task(id=id, name=name, input_data=input_data)

    def execute_task(self, task: Task) -> Task:
        """Execute the task using the internal TaskExecutor."""
        return self._executor.execute_task(task)

    # Memory Operations
    def save_memory(self, key: str, value: Any, category: str = "short-term") -> None:
        """Save a memory entry into short-term or long-term memory."""
        if category == "short-term":
            self._short_term_memory.set(key, value)
        elif category == "long-term":
            self._long_term_memory.set(key, value)
        else:
            raise ValueError(f"Unsupported memory category: {category}. Support: 'short-term' or 'long-term'")

    def get_memory(self, key: str, default: Any = None, category: str = "short-term") -> Any:
        """Retrieve a memory entry from short-term or long-term memory."""
        if category == "short-term":
            return self._short_term_memory.get(key, default)
        elif category == "long-term":
            return self._long_term_memory.get(key, default)
        else:
            raise ValueError(f"Unsupported memory category: {category}. Support: 'short-term' or 'long-term'")

    # Context Operations
    def create_context(self, data: Optional[Dict[str, Any]] = None):
        """Create a new execution context."""
        from yasin_core.context import Context
        return Context(data)

    # Provider Operations
    def register_provider(self, provider: AIProvider) -> None:
        """Register a new AI provider."""
        self._provider_manager.register_provider(provider)

    def get_provider(self, name: str) -> Optional[AIProvider]:
        """Retrieve a registered AI provider by name."""
        return self._provider_manager.get_provider(name)

    def list_providers(self) -> List[str]:
        """List names of all registered AI providers."""
        return self._provider_manager.list_providers()

    def generate(self, provider_name: str, prompt: str) -> str:
        """Convenience method to trigger generation on a specific provider."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' is not registered.")
        return provider.generate(prompt)

    # Tool Operations
    def register_tool(self, tool: BaseTool) -> None:
        """Register a new agent tool."""
        self._tool_manager.register_tool(tool)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Retrieve a registered agent tool by name."""
        return self._tool_manager.get_tool(name)

    def list_tools(self) -> List[str]:
        """List names of all registered agent tools."""
        return self._tool_manager.list_tools()

    def execute_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a registered agent tool by name with arguments."""
        return self._tool_manager.execute_tool(name, *args, **kwargs)

    @property
    def tool_manager(self) -> ToolManager:
        """Expose the ToolManager instance."""
        return self._tool_manager

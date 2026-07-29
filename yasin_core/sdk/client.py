from typing import Optional, List, Dict, Any
from yasin_core.version import VERSION
from yasin_core.agents import AgentManager, Task, TaskExecutor, BaseAgent


class YasinCoreClient:
    def __init__(self):
        self._version = VERSION
        self._agent_manager = AgentManager()
        self._executor = TaskExecutor(agent_manager=self._agent_manager)

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

    # Task Operations
    def create_task(self, id: str, name: str, input_data: Optional[Dict[str, Any]] = None) -> Task:
        """Create a new Task instance."""
        return Task(id=id, name=name, input_data=input_data)

    def execute_task(self, task: Task) -> Task:
        """Execute the task using the internal TaskExecutor."""
        return self._executor.execute_task(task)

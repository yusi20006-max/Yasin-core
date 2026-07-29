from abc import ABC, abstractmethod
from yasin_core.agents.task import Task
from yasin_core.agents.manager import AgentManager


class BasePlanner(ABC):


    @abstractmethod
    def plan(self, task: Task, agent_manager: AgentManager) -> Task:

        pass


class SimplePlanner(BasePlanner):


    def plan(self, task: Task, agent_manager: AgentManager) -> Task:

        if "agent_name" not in task.input_data:

            agents = agent_manager.list_agents()

            if agents:

                task.input_data["agent_name"] = agents[0].name

        task.status = "planned"

        return task

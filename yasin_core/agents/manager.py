from typing import Dict, List, Optional
from yasin_core.agents.base import BaseAgent


class AgentRegistry:


    def __init__(self):

        self._agents: Dict[str, BaseAgent] = {}


    def register(self, agent: BaseAgent):

        self._agents[agent.name] = agent


    def remove(self, name: str):

        if name in self._agents:

            del self._agents[name]


    def get(self, name: str) -> Optional[BaseAgent]:

        return self._agents.get(name)


    def list_all(self) -> List[BaseAgent]:

        return list(self._agents.values())


class AgentManager:


    def __init__(self):

        self.registry = AgentRegistry()


    def register_agent(self, agent: BaseAgent):

        self.registry.register(agent)


    def remove_agent(self, name: str):

        self.registry.remove(name)


    def get_agent(self, name: str) -> Optional[BaseAgent]:

        return self.registry.get(name)


    def list_agents(self) -> List[BaseAgent]:

        return self.registry.list_all()


    def start_agent(self, name: str):

        agent = self.get_agent(name)

        if agent:

            agent.start()


    def stop_agent(self, name: str):

        agent = self.get_agent(name)

        if agent:

            agent.stop()


    def start_all(self):

        for agent in self.list_agents():

            agent.start()


    def stop_all(self):

        for agent in self.list_agents():

            agent.stop()

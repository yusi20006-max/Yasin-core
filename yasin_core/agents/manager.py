from typing import Dict, List, Optional, Any
from yasin_core.agents.base import BaseAgent
from yasin_core.utils.logger import get_logger
from yasin_core.events import (
    AGENT_REGISTERED,
    AGENT_REMOVED,
    AGENT_STARTED,
    AGENT_STOPPED,
)


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def remove(self, name: str) -> Optional[BaseAgent]:
        return self._agents.pop(name, None)

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def list(self) -> List[str]:
        return list(self._agents.keys())


class AgentManager:
    def __init__(self, registry: Optional[AgentRegistry] = None, event_bus: Optional[Any] = None):
        self.registry = registry if registry is not None else AgentRegistry()
        self.event_bus = event_bus
        self.logger = get_logger("AGENT-MANAGER")

    def register_agent(self, agent: BaseAgent) -> None:
        self.registry.register(agent)
        self.logger.info(f"Agent '{agent.name}' registered.")
        if self.event_bus:
            self.event_bus.publish(AGENT_REGISTERED, {"agent_name": agent.name})

    def remove_agent(self, name: str) -> Optional[BaseAgent]:
        agent = self.registry.remove(name)
        if agent:
            self.logger.info(f"Agent '{name}' removed.")
            if self.event_bus:
                self.event_bus.publish(AGENT_REMOVED, {"agent_name": name})
        return agent

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.registry.get(name)

    def list_agents(self) -> List[str]:
        return self.registry.list()

    def start_agents(self) -> None:
        self.logger.info("Starting registered agents...")
        for name in self.registry.list():
            agent = self.registry.get(name)
            if agent and not agent.running:
                agent.start()
                self.logger.info(f"Agent '{name}' started.")
                if self.event_bus:
                    self.event_bus.publish(AGENT_STARTED, {"agent_name": name})

    def stop_agents(self) -> None:
        self.logger.info("Stopping registered agents...")
        for name in self.registry.list():
            agent = self.registry.get(name)
            if agent and agent.running:
                agent.stop()
                self.logger.info(f"Agent '{name}' stopped.")
                if self.event_bus:
                    self.event_bus.publish(AGENT_STOPPED, {"agent_name": name})

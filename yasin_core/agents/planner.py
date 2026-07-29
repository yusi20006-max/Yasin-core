from abc import ABC, abstractmethod
from typing import Any, Dict
from yasin_core.agents.task import Task


class Planner(ABC):
    @abstractmethod
    def plan(self, task: Task) -> Dict[str, Any]:
        """Convert tasks into executable agent actions or plan payloads."""
        pass


class SimplePlanner(Planner):
    def plan(self, task: Task) -> Dict[str, Any]:
        # Simple local planner that maps the task name as target agent name
        # and passes task input_data as agent execution parameters
        return {
            "agent_name": task.input_data.get("agent_name", task.name),
            "payload": task.input_data
        }

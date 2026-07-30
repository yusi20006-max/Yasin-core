# Progress: [█████░░░░░] 50%

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from yasin_core.agents.tool import BaseTool


class BaseAgent(ABC):
    def __init__(self, name: str, description: str = "", tools: Optional[List[BaseTool]] = None):
        self.name = name
        self.description = description
        self.running = False
        self.tools = tools or []

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any:
        pass

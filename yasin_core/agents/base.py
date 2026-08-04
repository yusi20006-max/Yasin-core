import queue
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List


class BaseAgent(ABC):
    def __init__(
        self,
        name: str,
        description: str = "",
        tools: Optional[List[Any]] = None,
        capabilities: Optional[List[str]] = None,
        permissions: Optional[List[str]] = None,
    ):
        self.name = name
        self.description = description
        self.running = False
        self.tools = tools or []
        self.capabilities = capabilities or []
        self.permissions = permissions or []
        self.state: Dict[str, Any] = {}
        self.inbox: queue.Queue = queue.Queue()

    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def execute(self, input_data: Dict[str, Any]) -> Any:
        pass

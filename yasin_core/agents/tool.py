# Progress: [██░░░░░░░░] 20%

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Callable
from yasin_core.utils.logger import get_logger


class BaseTool(ABC):
    """Abstract base class for all Agent Tools in Yasin-Core."""

    def __init__(self, name: str, description: str = "", args_schema: Optional[Dict[str, Any]] = None):
        self.name = name
        self.description = description
        self.args_schema = args_schema or {}

    @abstractmethod
    def execute(self, *args: Any, **kwargs: Any) -> Any:
        """Execute the tool's primary action."""
        pass

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Allow calling the tool instance directly."""
        return self.execute(*args, **kwargs)


class FunctionTool(BaseTool):
    """A wrapper to convert any standard Python function into a Yasin-Core Tool."""

    def __init__(
        self,
        func: Callable[..., Any],
        name: Optional[str] = None,
        description: Optional[str] = None,
        args_schema: Optional[Dict[str, Any]] = None,
    ):
        self.func = func
        tool_name = name or func.__name__
        tool_description = description or func.__doc__ or ""
        super().__init__(name=tool_name, description=tool_description, args_schema=args_schema)

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self.func(*args, **kwargs)


def tool(
    arg: Optional[Callable[..., Any]] = None,
    *,
    name: Optional[str] = None,
    description: Optional[str] = None,
    args_schema: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Decorator to register a function as a Tool.
    Supports both:
        @tool
        def my_func(...): ...

    And:
        @tool(name="custom_name", description="custom_description")
        def my_func(...): ...
    """
    if callable(arg):
        return FunctionTool(arg)

    def decorator(func: Callable[..., Any]) -> FunctionTool:
        return FunctionTool(func, name=name, description=description, args_schema=args_schema)

    return decorator


class ToolRegistry:
    """Internal registry that holds, manages, and structures registered tools."""

    def __init__(self) -> None:
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        self._tools[tool.name] = tool

    def remove(self, name: str) -> Optional[BaseTool]:
        return self._tools.pop(name, None)

    def get(self, name: str) -> Optional[BaseTool]:
        return self._tools.get(name)

    def list(self) -> List[str]:
        return list(self._tools.keys())


class ToolManager:
    """Central management system that orchestrates tool registration, retrieval, and execution."""

    def __init__(self, registry: Optional[ToolRegistry] = None) -> None:
        self.registry = registry if registry is not None else ToolRegistry()
        self.logger = get_logger("TOOL-MANAGER")

    def register_tool(self, tool: BaseTool) -> None:
        self.registry.register(tool)
        self.logger.info(f"Tool '{tool.name}' registered.")

    def remove_tool(self, name: str) -> Optional[BaseTool]:
        tool = self.registry.remove(name)
        if tool:
            self.logger.info(f"Tool '{name}' removed.")
        return tool

    def get_tool(self, name: str) -> Optional[BaseTool]:
        return self.registry.get(name)

    def list_tools(self) -> List[str]:
        return self.registry.list()

    def execute_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        tool_instance = self.get_tool(name)
        if not tool_instance:
            raise ValueError(f"Tool '{name}' is not registered.")
        return tool_instance.execute(*args, **kwargs)

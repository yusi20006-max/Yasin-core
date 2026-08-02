from abc import ABC, abstractmethod
from enum import Enum
from typing import Any, Callable, Type, Union

class ServiceLifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"


class IDIContainer(ABC):
    """
    Abstract interface for the Dependency Injection Container.
    """

    @abstractmethod
    def register_instance(self, key: Union[Type, str], instance: Any) -> None:
        """Register an existing instance directly as a singleton."""
        pass

    @abstractmethod
    def register_singleton(
        self, key: Union[Type, str], factory_or_class: Union[Type, Callable[..., Any]]
    ) -> None:
        """Register a singleton class or factory function."""
        pass

    @abstractmethod
    def register_transient(
        self, key: Union[Type, str], factory_or_class: Union[Type, Callable[..., Any]]
    ) -> None:
        """Register a transient (factory) class or factory function."""
        pass

    @abstractmethod
    def resolve(self, key: Union[Type, str]) -> Any:
        """Resolve and return the requested service instance."""
        pass

    @abstractmethod
    def has(self, key: Union[Type, str]) -> bool:
        """Check if a service is registered for the given key."""
        pass

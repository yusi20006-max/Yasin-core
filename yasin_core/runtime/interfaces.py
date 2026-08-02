from abc import ABC, abstractmethod
from typing import Dict, Any

class IService(ABC):
    """
    Interface for services managed by the RuntimeServiceManager.
    """
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the service."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the service."""
        pass

    @abstractmethod
    def reload(self) -> None:
        """Reload the service configuration."""
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        """Return the health status of the service."""
        pass

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        """Return the execution status of the service."""
        pass


class BaseService(IService):
    """
    A base class providing default no-op implementations for managed services.
    """
    def initialize(self) -> None:
        pass

    def shutdown(self) -> None:
        pass

    def reload(self) -> None:
        pass

    def health(self) -> Dict[str, Any]:
        return {"status": "healthy"}

    def status(self) -> Dict[str, Any]:
        return {"state": "active"}

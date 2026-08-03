from abc import ABC, abstractmethod
from typing import Any, Dict
from yasin_core.runtime.interfaces import IService


class BaseStorage(IService, ABC):
    """
    Unified base storage interface implementing the standard IService lifecycle and health checking.
    """

    def initialize(self) -> None:
        """Initialize the storage provider."""
        pass

    def shutdown(self) -> None:
        """Shutdown the storage provider."""
        pass

    def reload(self) -> None:
        """Reload the storage provider configuration."""
        pass

    def health(self) -> Dict[str, Any]:
        """Return the health status of the storage provider."""
        return {"status": "healthy", "healthy": True}

    def status(self) -> Dict[str, Any]:
        """Return the execution status of the storage provider."""
        return {"state": "active", "metadata": self.metadata}

    @property
    def metadata(self) -> Dict[str, Any]:
        """Return storage metadata like provider capabilities."""
        return {
            "backend_type": "unknown",
            "persistent": False,
            "key_value": True,
        }

    @abstractmethod
    def get(self, key, default=None):
        pass

    @abstractmethod
    def set(self, key, value):
        pass

    @abstractmethod
    def delete(self, key):
        pass

    @abstractmethod
    def clear(self):
        pass

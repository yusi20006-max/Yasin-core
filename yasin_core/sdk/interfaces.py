from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class ISDKClient(ABC):
    """Abstract interface for Yasin SDK client (for both sync and async implementations)."""
    @abstractmethod
    def start(self) -> None:
        pass

    @abstractmethod
    def stop(self) -> None:
        pass

    @abstractmethod
    def health(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def status(self) -> Dict[str, Any]:
        pass


class ISDKAuthenticator(ABC):
    """Abstract client-side authentication interface."""
    @abstractmethod
    def get_auth_headers(self) -> Dict[str, str]:
        pass

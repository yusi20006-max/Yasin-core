from abc import ABC, abstractmethod
from typing import List


class YasinPlugin(ABC):

    name = "base"
    version = "1.0.0"
    description = ""
    dependencies: List[str] = []
    core_version_compat = "*"

    def initialize(self) -> None:
        """Initialize the plugin before loading dependencies."""
        pass

    def load(self) -> None:
        """Load resources and establish plugin-level configurations."""
        pass

    @abstractmethod
    def start(self) -> None:
        """Start the plugin execution or register active listeners."""
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop the plugin execution or release active listeners."""
        pass

    def unload(self) -> None:
        """Clean up and release resources allocated during load."""
        pass

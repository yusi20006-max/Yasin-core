# Progress:
# [x] 100%

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from yasin_core.utils.logger import get_logger


class AIProvider(ABC):


    name = "base"


    @abstractmethod
    def generate(
        self,
        prompt
    ):

        pass


class MockProvider(AIProvider):


    name = "mock"


    def __init__(self, default_response: str = "Mock response"):
        self.default_response = default_response


    def generate(self, prompt: str) -> str:
        return f"{self.default_response}: {prompt}"


class LocalProvider(AIProvider):


    name = "local"


    def generate(self, prompt: str) -> str:
        return f"Local response to: {prompt}"


class ProviderRegistry:


    def __init__(self):
        self._providers: Dict[str, AIProvider] = {}


    def register(self, provider: AIProvider) -> None:
        self._providers[provider.name] = provider


    def remove(self, name: str) -> Optional[AIProvider]:
        return self._providers.pop(name, None)


    def get(self, name: str) -> Optional[AIProvider]:
        return self._providers.get(name)


    def list(self) -> List[str]:
        return list(self._providers.keys())


class ProviderManager:


    def __init__(self, registry: Optional[ProviderRegistry] = None):
        self.registry = registry if registry is not None else ProviderRegistry()
        self.logger = get_logger("PROVIDER-MANAGER")
        # Automatically register standard default providers
        self.register_provider(LocalProvider())
        self.register_provider(MockProvider())


    def register_provider(self, provider: AIProvider) -> None:
        self.registry.register(provider)
        self.logger.info(f"Provider '{provider.name}' registered.")


    def remove_provider(self, name: str) -> Optional[AIProvider]:
        provider = self.registry.remove(name)
        if provider:
            self.logger.info(f"Provider '{name}' removed.")
        return provider


    def get_provider(self, name: str) -> Optional[AIProvider]:
        return self.registry.get(name)


    def list_providers(self) -> List[str]:
        return self.registry.list()

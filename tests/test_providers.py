import pytest
from yasin_core.sdk import YasinCoreClient
from yasin_core.providers import AIProvider, MockProvider, LocalProvider


class CustomTestProvider(AIProvider):
    name = "custom_test"

    def generate(self, prompt: str) -> str:
        return f"Custom response: {prompt}"


def test_provider_manager_and_registry():
    client = YasinCoreClient()

    # Check default registered providers
    providers = client.list_providers()
    assert "local" in providers
    assert "mock" in providers

    # Retrieve local provider and test generation
    local_provider = client.get_provider("local")
    assert isinstance(local_provider, LocalProvider)
    assert local_provider.generate("hello") == "Local response to: hello"

    # Retrieve mock provider and test generation
    mock_provider = client.get_provider("mock")
    assert isinstance(mock_provider, MockProvider)
    assert mock_provider.generate("hello") == "Mock response: hello"


def test_custom_provider_registration_via_sdk():
    client = YasinCoreClient()
    custom_prov = CustomTestProvider()

    # Register custom provider
    client.register_provider(custom_prov)

    # Check that it exists in list
    assert "custom_test" in client.list_providers()
    assert client.get_provider("custom_test") == custom_prov

    # Test generation through convenience method on client
    res = client.generate("custom_test", "hello world")
    assert res == "Custom response: hello world"


def test_unregistered_provider_error():
    client = YasinCoreClient()
    with pytest.raises(ValueError):
        client.generate("nonexistent_provider", "prompt")

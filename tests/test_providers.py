import pytest
import time
from unittest.mock import Mock, patch
from typing import Iterator

from yasin_core.sdk import (
    YasinCoreClient,
    AIProvider,
    MockProvider,
    LocalProvider,
    AIChatMessage,
    AIRequest,
    AIResponse,
    AIResponseChunk,
    AIProviderError,
    AIProviderConnectionError,
    AIProviderAuthError,
    AIProviderRateLimitError,
    OpenAICompatibleProvider,
    ProviderManager,
)


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


# --- New Comprehensive Tests for AI Provider Abstraction Layer ---

def test_models_serialization():
    # AIChatMessage serialization
    msg = AIChatMessage(role="user", content="hello")
    assert msg.to_dict() == {"role": "user", "content": "hello"}
    msg2 = AIChatMessage.from_dict({"role": "system", "content": "act as assistant"})
    assert msg2.role == "system"
    assert msg2.content == "act as assistant"

    # AIRequest serialization
    req = AIRequest(
        prompt="explain recursion",
        messages=[msg],
        model="gpt-4o",
        temperature=0.7,
        max_tokens=100,
        stream=True,
        extra_params={"top_p": 0.9}
    )
    req_dict = req.to_dict()
    assert req_dict["prompt"] == "explain recursion"
    assert len(req_dict["messages"]) == 1
    assert req_dict["messages"][0]["content"] == "hello"
    assert req_dict["model"] == "gpt-4o"
    assert req_dict["temperature"] == 0.7
    assert req_dict["max_tokens"] == 100
    assert req_dict["stream"] is True
    assert req_dict["extra_params"]["top_p"] == 0.9

    # AIResponse serialization
    resp = AIResponse(text="Recursion is...", model="gpt-4o", usage={"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}, raw_response={"id": "123"})
    resp_dict = resp.to_dict()
    assert resp_dict["text"] == "Recursion is..."
    assert resp_dict["model"] == "gpt-4o"
    assert resp_dict["usage"]["total_tokens"] == 30
    assert resp_dict["raw_response"] == "{'id': '123'}"


def test_provider_registry_and_service_integration():
    client = YasinCoreClient()

    # Verify ProviderManager is registered as a runtime service
    assert "providers" in client.service_registry.list_services()

    # Verify ProviderManager is in Dependency Injection container
    di_pm = client.di_container.resolve("providers")
    assert isinstance(di_pm, ProviderManager)
    assert di_pm == client.providers

    # Verify service state is registered/active
    status = client.providers.status()
    assert status["state"] == "active"
    assert "local" in status["registered_providers"]
    assert "mock" in status["registered_providers"]
    assert "openai" in status["registered_providers"]


def test_configuration_loading_and_security():
    client = YasinCoreClient()

    # Trigger service initialization to register schemas
    client.providers.initialize()

    # Check that schemas are loaded in config manager
    assert client.config.has("providers.default")
    assert client.config.has("providers.openai.base_url")

    # Secure api key masking test
    client.config.set("providers.openai.api_key", "sk-1234567890abcdef")
    config_status = client.config.status()
    # Key should be masked in the status dictionary
    masked_key = config_status["configuration"]["providers"]["openai"]["api_key"]
    assert masked_key == "******"


def test_routing_and_fallbacks():
    client = YasinCoreClient()
    client.providers.initialize()

    # Route request by model name prefix (e.g. "openai/gpt-4" should route to openai provider)
    req = AIRequest(prompt="hello", model="openai/gpt-4")
    provider = client.providers.route_request(req)
    assert provider.name == "openai"

    # Route request by extra_params override
    req2 = AIRequest(prompt="hello", extra_params={"provider": "local"})
    provider2 = client.providers.route_request(req2)
    assert provider2.name == "local"

    # Fallback chaining: if an unconfigured provider fails, it tries alternative providers
    # Let's create a custom provider that always fails
    class FailingProvider(AIProvider):
        name = "failing"
        def generate(self, prompt):
            raise AIProviderError("Endpoint unreachable")

    client.register_provider(FailingProvider())

    # Try generating a response via failing provider with fallback to mock
    req3 = AIRequest(prompt="test prompt", extra_params={"provider": "failing"})
    # Let's verify that fallback chain catches FailingProviderError and returns the MockProvider response
    res = client.generate_response(req3, fallback_chain=["mock"])
    assert "mock" in res.text.lower()
    assert res.model == "mock-model"


def test_streaming_responses():
    client = YasinCoreClient()

    # Test streaming using string prompt
    stream = client.generate_stream("hello local stream", provider_name="local")
    chunks = list(stream)
    assert len(chunks) > 0
    full_text = "".join(chunks)
    assert "Local response to" in full_text

    # Test streaming using AIRequest explicitly routed to mock
    req = AIRequest(prompt="hello mock stream", model="mock", extra_params={"provider": "mock"})
    stream2 = client.generate_stream(req)
    chunks2 = list(stream2)
    assert len(chunks2) > 0
    assert isinstance(chunks2[0], AIResponseChunk)
    full_text2 = "".join([c.text for c in chunks2])
    assert "Mock response" in full_text2


@patch("requests.post")
def test_openai_compatible_provider_http_handling(mock_post):
    # Setup mock HTTP response for OpenAI chat/completions endpoint
    mock_resp = Mock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Hello from OpenAI API Compatible endpoint!"
                }
            }
        ],
        "usage": {
            "prompt_tokens": 15,
            "completion_tokens": 10,
            "total_tokens": 25
        }
    }
    mock_post.return_value = mock_resp

    provider = OpenAICompatibleProvider(api_key="real_key", base_url="http://mock-url/v1")
    req = AIRequest(prompt="test message", model="gpt-4o")

    res = provider.generate_response(req)
    assert res.text == "Hello from OpenAI API Compatible endpoint!"
    assert res.model == "gpt-4o"
    assert res.usage["total_tokens"] == 25


@patch("requests.post")
def test_openai_errors_handling(mock_post):
    # Setup mock HTTP responses for different errors
    provider = OpenAICompatibleProvider(api_key="real_key", base_url="http://mock-url/v1")
    req = AIRequest(prompt="test error", model="gpt-4o")

    # 401 Unauthorized
    mock_resp_401 = Mock()
    mock_resp_401.status_code = 401
    mock_resp_401.text = "Invalid API Key"
    mock_post.return_value = mock_resp_401
    with pytest.raises(AIProviderAuthError):
        provider.generate_response(req)

    # 429 Rate Limit
    mock_resp_429 = Mock()
    mock_resp_429.status_code = 429
    mock_resp_429.text = "Too many requests"
    mock_post.return_value = mock_resp_429
    with pytest.raises(AIProviderRateLimitError):
        provider.generate_response(req)


def test_observability_metrics_and_health():
    client = YasinCoreClient()
    client.providers.initialize()

    # Set mock key and re-initialize to ensure openai provider health checks as healthy
    client.config.set("providers.openai.api_key", "mock_key")
    client.providers.initialize()

    # Trigger generation to record metrics
    req = AIRequest(prompt="test metrics", model="mock")
    client.generate_response(req)

    # Health check integration
    health_status = client.providers.health()
    assert health_status["status"] == "healthy"
    assert health_status["providers"]["mock"]["healthy"] is True

    # Retrieve metrics registered by ProviderManager
    metrics = client.observability.metrics.get_all_metrics()
    metric_names = [m.name for m in metrics]

    assert "yasin_ai_generation_requests_total" in metric_names
    assert "yasin_ai_generation_duration_seconds" in metric_names
    assert "yasin_ai_token_usage_total" in metric_names

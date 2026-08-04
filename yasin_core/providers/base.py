from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union, Iterator
import time
from yasin_core.utils.logger import get_logger
from yasin_core.runtime.interfaces import BaseService

# --- Custom Exceptions ---

class AIProviderError(Exception):
    """Base exception for all AI provider errors."""
    pass

class AIProviderConnectionError(AIProviderError):
    """Raised when there is a connection issue with the AI provider."""
    pass

class AIProviderAuthError(AIProviderError):
    """Raised when authentication with the AI provider fails."""
    pass

class AIProviderRateLimitError(AIProviderError):
    """Raised when the AI provider rate limits the requests."""
    pass


# --- Models ---

class AIChatMessage:
    def __init__(self, role: str, content: str):
        self.role = role
        self.content = content

    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}

    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> "AIChatMessage":
        return cls(role=data.get("role", "user"), content=data.get("content", ""))


class AIRequest:
    def __init__(
        self,
        prompt: Optional[str] = None,
        messages: Optional[List[AIChatMessage]] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
        extra_params: Optional[Dict[str, Any]] = None,
    ):
        self.prompt = prompt
        self.messages = messages or []
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.stream = stream
        self.extra_params = extra_params or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "messages": [m.to_dict() for m in self.messages],
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "stream": self.stream,
            "extra_params": self.extra_params,
        }


class AIResponse:
    def __init__(
        self,
        text: str,
        model: str,
        usage: Optional[Dict[str, int]] = None,
        raw_response: Any = None,
    ):
        self.text = text
        self.model = model
        self.usage = usage or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        self.raw_response = raw_response

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model": self.model,
            "usage": self.usage,
            "raw_response": str(self.raw_response) if self.raw_response else None,
        }


class AIResponseChunk:
    def __init__(
        self,
        text: str,
        usage: Optional[Dict[str, int]] = None,
        is_last: bool = False,
    ):
        self.text = text
        self.usage = usage
        self.is_last = is_last

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "usage": self.usage,
            "is_last": self.is_last,
        }


# --- Abstract Base Interface ---

class AIProvider(ABC):
    name: str = "base"

    def initialize(self, config_manager: Optional[Any] = None) -> None:
        """Initialize the provider with configuration from ConfigurationManager."""
        pass

    @abstractmethod
    def generate(self, prompt: Union[str, AIRequest], **kwargs) -> Union[str, AIResponse]:
        """
        Generate a text completion.
        To maintain backward compatibility:
        - If prompt is a string, returns a string.
        - If prompt is an AIRequest, returns an AIResponse.
        """
        pass

    def generate_response(self, request: AIRequest) -> AIResponse:
        """Generate structured response for an AIRequest."""
        res = self.generate(request)
        if isinstance(res, str):
            return AIResponse(text=res, model=request.model or "unknown")
        return res

    def generate_stream(self, request: Union[str, AIRequest]) -> Iterator[Union[str, AIResponseChunk]]:
        """Generate a stream of completions/responses."""
        # Simple default non-streaming fallback
        if isinstance(request, str):
            yield self.generate(request)
        else:
            yield self.generate_response(request)

    def health(self) -> Dict[str, Any]:
        """Check provider health and connectivity."""
        return {"status": "healthy", "healthy": True}

    def get_capabilities(self) -> Dict[str, Any]:
        """Report provider model capabilities (e.g. streaming, chat, completions)."""
        return {
            "chat": True,
            "completion": True,
            "streaming": True,
            "embeddings": False,
        }

    def get_models(self) -> List[Dict[str, Any]]:
        """Return a list of supported models with their metadata."""
        return []


# --- Registry and Manager ---

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


class ProviderManager(BaseService):
    def __init__(self, registry: Optional[ProviderRegistry] = None, client: Optional[Any] = None):
        super().__init__()
        self.registry = registry if registry is not None else ProviderRegistry()
        self.client = client
        self.logger = get_logger("PROVIDER-MANAGER")

        # Automatically register standard default providers on instantiation
        from yasin_core.providers.adapters import LocalProvider, MockProvider, OpenAICompatibleProvider
        self.register_provider(LocalProvider())
        self.register_provider(MockProvider())
        self.register_provider(OpenAICompatibleProvider())

    def initialize(self) -> None:
        # Initialize registered providers with config
        config_mgr = None
        if self.client and hasattr(self.client, "config"):
            config_mgr = self.client.config
            # Register configuration schemas with ConfigurationManager
            try:
                config_mgr.register_schema("providers.default", str, required=False, default="local", description="Default AI provider")
                config_mgr.register_schema("providers.fallbacks", list, required=False, default=["mock"], description="Fallback provider list")
                config_mgr.register_schema("providers.openai.api_key", str, required=False, default="", description="OpenAI API key", sensitive=True)
                config_mgr.register_schema("providers.openai.base_url", str, required=False, default="https://api.openai.com/v1", description="OpenAI Base URL")
                config_mgr.register_schema("providers.openai.default_model", str, required=False, default="gpt-4o-mini", description="OpenAI Default Model")
            except Exception as e:
                self.logger.warning(f"Failed to register provider schemas: {e}")

        for name in self.list_providers():
            provider = self.get_provider(name)
            if provider:
                try:
                    provider.initialize(config_mgr)
                except Exception as e:
                    self.logger.error(f"Failed to initialize provider '{name}': {e}")

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

    def route_request(self, request: AIRequest) -> AIProvider:
        """
        Determines the target provider based on model, request parameters, or default config.
        """
        # 1. Check explicit provider override in extra_params
        if request.extra_params and "provider" in request.extra_params:
            provider_name = request.extra_params["provider"]
            provider = self.get_provider(provider_name)
            if provider:
                return provider

        # 2. Check model name prefix (e.g. "openai/gpt-4" -> "openai")
        if request.model and "/" in request.model:
            prefix = request.model.split("/")[0]
            provider = self.get_provider(prefix)
            if provider:
                return provider

        # 3. Check default provider in configuration
        if self.client and hasattr(self.client, "config"):
            default_p = self.client.config.get("providers.default")
            if default_p:
                provider = self.get_provider(default_p)
                if provider:
                    return provider

        # 4. Fallback to 'mock' or first available provider
        provider = self.get_provider("mock")
        if provider:
            return provider

        providers = self.list_providers()
        if providers:
            return self.get_provider(providers[0])

        raise AIProviderError("No registered AI providers found.")

    def generate(self, provider_name: str, prompt: str) -> str:
        """Convenience method to trigger generation on a specific provider (backward-compatible)."""
        provider = self.get_provider(provider_name)
        if not provider:
            raise ValueError(f"Provider '{provider_name}' is not registered.")
        return provider.generate(prompt)

    def generate_response(self, request: AIRequest, fallback_chain: Optional[List[str]] = None) -> AIResponse:
        """
        Routes the request, calls the chosen provider, collects observability metrics,
        and implements fallback chaining on failure.
        """
        # Determine initial provider
        try:
            provider = self.route_request(request)
        except Exception as e:
            raise AIProviderError(f"Routing failed: {e}")

        # Construct candidate list for fallbacks (avoiding duplicates)
        chain = []
        if fallback_chain:
            chain.extend(fallback_chain)
        else:
            # Load default fallbacks from configuration
            if self.client and hasattr(self.client, "config"):
                chain.extend(self.client.config.get("providers.fallbacks", []))

        # Build the sequence of providers to try
        try_providers = [provider]
        for name in chain:
            p = self.get_provider(name)
            if p and p not in try_providers:
                try_providers.append(p)

        last_error = None
        for p in try_providers:
            start_time = time.time()
            try:
                # Perform the generation call
                res = p.generate_response(request)
                duration = time.time() - start_time

                # Record metrics on success
                self._record_metrics(
                    provider_name=p.name,
                    model=request.model or "unknown",
                    duration=duration,
                    prompt_tokens=res.usage.get("prompt_tokens", 0),
                    completion_tokens=res.usage.get("completion_tokens", 0),
                    total_tokens=res.usage.get("total_tokens", 0),
                    success=True
                )
                return res
            except Exception as e:
                duration = time.time() - start_time
                self.logger.warning(f"Generation failed on provider '{p.name}': {e}. Trying fallback if available.")
                last_error = e
                # Record error metrics
                self._record_metrics(
                    provider_name=p.name,
                    model=request.model or "unknown",
                    duration=duration,
                    prompt_tokens=0,
                    completion_tokens=0,
                    total_tokens=0,
                    success=False,
                    error_type=type(e).__name__
                )

        # All providers failed
        raise last_error or AIProviderError("AI Provider generation failed on all attempted providers.")

    def generate_stream(self, request: Union[str, AIRequest], provider_name: Optional[str] = None) -> Iterator[Union[str, AIResponseChunk]]:
        """
        Generate stream of chunks. Metrics are logged at completion.
        """
        # Resolve provider
        if provider_name:
            provider = self.get_provider(provider_name)
        elif isinstance(request, AIRequest):
            provider = self.route_request(request)
        else:
            # Wrap standard string in a dummy request for routing
            dummy = AIRequest(prompt=request)
            provider = self.route_request(dummy)

        if not provider:
            raise AIProviderError("No AI provider resolved for streaming.")

        start_time = time.time()
        full_text = []
        try:
            for chunk in provider.generate_stream(request):
                yield chunk
                if isinstance(chunk, AIResponseChunk):
                    full_text.append(chunk.text)
                else:
                    full_text.append(chunk)

            duration = time.time() - start_time
            # Record basic metrics on successful stream completion (approximate token counts)
            tokens = len("".join(full_text)) // 4  # heuristic
            self._record_metrics(
                provider_name=provider.name,
                model=getattr(request, "model", None) or "unknown",
                duration=duration,
                prompt_tokens=0,
                completion_tokens=tokens,
                total_tokens=tokens,
                success=True
            )
        except Exception as e:
            duration = time.time() - start_time
            self._record_metrics(
                provider_name=provider.name,
                model=getattr(request, "model", None) or "unknown",
                duration=duration,
                prompt_tokens=0,
                completion_tokens=0,
                total_tokens=0,
                success=False,
                error_type=type(e).__name__
            )
            raise e

    def _record_metrics(
        self,
        provider_name: str,
        model: str,
        duration: float,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        success: bool,
        error_type: Optional[str] = None
    ) -> None:
        """
        Helper to log observability metrics using client's observability service.
        """
        if not self.client or not hasattr(self.client, "observability") or not self.client.observability:
            return

        obs = self.client.observability
        labels = {"provider": provider_name, "model": model}

        try:
            # 1. Total requests
            obs.metrics.counter(
                name="yasin_ai_generation_requests_total",
                description="Total number of AI generation requests",
                labels=labels
            ).inc()

            # 2. Failure count
            if not success:
                err_labels = dict(labels)
                err_labels["error_type"] = error_type or "unknown"
                obs.metrics.counter(
                    name="yasin_ai_generation_errors_total",
                    description="Total number of AI generation failures",
                    labels=err_labels
                ).inc()

            # 3. Request duration
            obs.metrics.histogram(
                name="yasin_ai_generation_duration_seconds",
                description="Duration of AI generation requests in seconds",
                labels=labels
            ).observe(duration)

            # 4. Token metrics (prompt, completion, total)
            if success and total_tokens > 0:
                for t_type, t_val in [("prompt", prompt_tokens), ("completion", completion_tokens), ("total", total_tokens)]:
                    tok_labels = dict(labels)
                    tok_labels["token_type"] = t_type
                    obs.metrics.counter(
                        name="yasin_ai_token_usage_total",
                        description="Total number of AI tokens used",
                        labels=tok_labels
                    ).inc(float(t_val))
        except Exception as e:
            self.logger.warning(f"Failed to record AI generation metrics: {e}")

    # --- Service Interface Methods ---

    def health(self) -> Dict[str, Any]:
        """Consolidate health status across all registered providers."""
        providers_health = {}
        overall_healthy = True

        for name in self.list_providers():
            provider = self.get_provider(name)
            if provider:
                try:
                    p_health = provider.health()
                    providers_health[name] = p_health
                    if not p_health.get("healthy", True):
                        overall_healthy = False
                except Exception as e:
                    providers_health[name] = {"status": "unhealthy", "healthy": False, "error": str(e)}
                    overall_healthy = False

        return {
            "status": "healthy" if overall_healthy else "degraded",
            "healthy": overall_healthy,
            "providers": providers_health
        }

    def status(self) -> Dict[str, Any]:
        """Expose manager status, listing registered providers, models, capabilities."""
        providers_status = {}
        for name in self.list_providers():
            provider = self.get_provider(name)
            if provider:
                providers_status[name] = {
                    "capabilities": provider.get_capabilities(),
                    "models": provider.get_models()
                }

        return {
            "state": "active",
            "registered_providers": self.list_providers(),
            "providers_details": providers_status
        }

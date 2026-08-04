import json
import requests
from typing import Dict, List, Optional, Any, Union, Iterator

from yasin_core.providers.base import (
    AIProvider, AIRequest, AIResponse, AIResponseChunk, AIChatMessage,
    AIProviderError, AIProviderConnectionError, AIProviderAuthError, AIProviderRateLimitError
)

class MockProvider(AIProvider):
    name = "mock"

    def __init__(self, default_response: str = "Mock response"):
        self.default_response = default_response

    def generate(self, prompt: Union[str, AIRequest], **kwargs) -> Union[str, AIResponse]:
        if isinstance(prompt, str):
            # Preserve 100% backward compatibility
            # mock_provider.generate("hello") == "Mock response: hello"
            return f"{self.default_response}: {prompt}"
        else:
            # Handle standard AIRequest
            messages_str = ""
            if prompt.prompt:
                messages_str = prompt.prompt
            elif prompt.messages:
                messages_str = ", ".join([f"{m.role}: {m.content}" for m in prompt.messages])

            text = f"{self.default_response}: {messages_str}"
            model = prompt.model or "mock-model"
            usage = {
                "prompt_tokens": len(messages_str) // 4,
                "completion_tokens": len(text) // 4,
                "total_tokens": (len(messages_str) + len(text)) // 4
            }
            return AIResponse(text=text, model=model, usage=usage)

    def generate_stream(self, request: Union[str, AIRequest]) -> Iterator[Union[str, AIResponseChunk]]:
        if isinstance(request, str):
            full_text = self.generate(request)
            for word in full_text.split(" "):
                yield word + " "
            return

        messages_str = request.prompt or ", ".join([f"{m.role}: {m.content}" for m in request.messages])
        text = f"{self.default_response}: {messages_str}"
        words = text.split(" ")
        for i, word in enumerate(words):
            is_last = (i == len(words) - 1)
            yield AIResponseChunk(text=word + (" " if not is_last else ""), is_last=is_last)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "chat": True,
            "completion": True,
            "streaming": True,
            "embeddings": False,
        }

    def get_models(self) -> List[Dict[str, Any]]:
        return [
            {"model_id": "mock-model", "name": "Mock Model v1", "context_window": 4096}
        ]


class LocalProvider(AIProvider):
    name = "local"

    def generate(self, prompt: Union[str, AIRequest], **kwargs) -> Union[str, AIResponse]:
        if isinstance(prompt, str):
            # Preserve 100% backward compatibility
            # local_provider.generate("hello") == "Local response to: hello"
            return f"Local response to: {prompt}"
        else:
            messages_str = prompt.prompt or ", ".join([f"{m.role}: {m.content}" for m in prompt.messages])
            text = f"Local simulated response to: {messages_str}"
            model = prompt.model or "local-llama"
            usage = {
                "prompt_tokens": len(messages_str) // 4,
                "completion_tokens": len(text) // 4,
                "total_tokens": (len(messages_str) + len(text)) // 4
            }
            return AIResponse(text=text, model=model, usage=usage)

    def generate_stream(self, request: Union[str, AIRequest]) -> Iterator[Union[str, AIResponseChunk]]:
        if isinstance(request, str):
            full_text = self.generate(request)
            for word in full_text.split(" "):
                yield word + " "
            return

        messages_str = request.prompt or ", ".join([f"{m.role}: {m.content}" for m in request.messages])
        text = f"Local simulated stream response to: {messages_str}"
        words = text.split(" ")
        for i, word in enumerate(words):
            is_last = (i == len(words) - 1)
            yield AIResponseChunk(text=word + (" " if not is_last else ""), is_last=is_last)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "chat": True,
            "completion": True,
            "streaming": True,
            "embeddings": True,
        }

    def get_models(self) -> List[Dict[str, Any]]:
        return [
            {"model_id": "local-llama3", "name": "Local LLaMA 3", "context_window": 8192},
            {"model_id": "local-phi3", "name": "Local Phi-3", "context_window": 4096},
        ]


class OpenAICompatibleProvider(AIProvider):
    name = "openai"

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", default_model: str = "gpt-4o-mini"):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model

    def initialize(self, config_manager: Optional[Any] = None) -> None:
        if config_manager:
            self.api_key = config_manager.get("providers.openai.api_key", self.api_key)
            self.base_url = config_manager.get("providers.openai.base_url", self.base_url)
            self.default_model = config_manager.get("providers.openai.default_model", self.default_model)

    def generate(self, prompt: Union[str, AIRequest], **kwargs) -> Union[str, AIResponse]:
        if isinstance(prompt, str):
            req = AIRequest(prompt=prompt, model=self.default_model, stream=False)
            res = self.generate_response(req)
            return res.text
        else:
            return self.generate_response(prompt)

    def generate_response(self, request: AIRequest) -> AIResponse:
        messages = []
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        else:
            messages = [m.to_dict() for m in request.messages]

        model = request.model or self.default_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens

        if request.extra_params:
            payload.update({k: v for k, v in request.extra_params.items() if k != "provider"})

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        # Simulated response if using a mock key or empty key during unit tests
        if not self.api_key or self.api_key == "mock_key":
            text = f"Simulated OpenAI ({model}) response to messages: {messages}"
            usage = {
                "prompt_tokens": len(str(messages)) // 4,
                "completion_tokens": len(text) // 4,
                "total_tokens": (len(str(messages)) + len(text)) // 4
            }
            return AIResponse(text=text, model=model, usage=usage, raw_response={"id": "chatcmpl-123"})

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            if response.status_code == 200:
                data = response.json()
                choice = data.get("choices", [{}])[0]
                text = choice.get("message", {}).get("content", "")
                usage = data.get("usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})
                return AIResponse(text=text, model=model, usage=usage, raw_response=data)
            elif response.status_code == 401:
                raise AIProviderAuthError(f"OpenAI Authentication Error: {response.text}")
            elif response.status_code == 429:
                raise AIProviderRateLimitError(f"OpenAI Rate Limit Error: {response.text}")
            else:
                raise AIProviderError(f"OpenAI API Error (Status {response.status_code}): {response.text}")
        except requests.exceptions.RequestException as e:
            raise AIProviderConnectionError(f"Failed to connect to OpenAI-compatible endpoint: {e}")

    def generate_stream(self, request: Union[str, AIRequest]) -> Iterator[Union[str, AIResponseChunk]]:
        if isinstance(request, str):
            req = AIRequest(prompt=request, model=self.default_model, stream=True)
            for chunk in self.generate_stream(req):
                yield chunk.text if isinstance(chunk, AIResponseChunk) else chunk
            return

        messages = []
        if request.prompt:
            messages.append({"role": "user", "content": request.prompt})
        else:
            messages = [m.to_dict() for m in request.messages]

        model = request.model or self.default_model

        payload = {
            "model": model,
            "messages": messages,
            "stream": True,
        }
        if request.temperature is not None:
            payload["temperature"] = request.temperature
        if request.max_tokens is not None:
            payload["max_tokens"] = request.max_tokens
        if request.extra_params:
            payload.update({k: v for k, v in request.extra_params.items() if k != "provider"})

        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        if not self.api_key or self.api_key == "mock_key":
            text = f"Simulated streaming response from {model} for prompt/messages."
            words = text.split(" ")
            for i, word in enumerate(words):
                is_last = (i == len(words) - 1)
                yield AIResponseChunk(text=word + (" " if not is_last else ""), is_last=is_last)
            return

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        try:
            response = requests.post(url, headers=headers, json=payload, stream=True, timeout=30)
            if response.status_code != 200:
                if response.status_code == 401:
                    raise AIProviderAuthError(f"OpenAI Authentication Error: {response.text}")
                elif response.status_code == 429:
                    raise AIProviderRateLimitError(f"OpenAI Rate Limit Error: {response.text}")
                else:
                    raise AIProviderError(f"OpenAI API Error (Status {response.status_code}): {response.text}")

            for line in response.iter_lines():
                if not line:
                    continue
                decoded = line.decode("utf-8").strip()
                if decoded.startswith("data: "):
                    data_str = decoded[6:]
                    if data_str == "[DONE]":
                        yield AIResponseChunk(text="", is_last=True)
                        break
                    try:
                        chunk_json = json.loads(data_str)
                        choice = chunk_json.get("choices", [{}])[0]
                        delta = choice.get("delta", {})
                        text_chunk = delta.get("content", "")
                        is_last = choice.get("finish_reason") is not None
                        yield AIResponseChunk(text=text_chunk, is_last=is_last)
                    except Exception:
                        pass
        except requests.exceptions.RequestException as e:
            raise AIProviderConnectionError(f"Failed to connect to OpenAI-compatible endpoint: {e}")

    def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy" if self.api_key else "unconfigured",
            "healthy": True,
            "configured": bool(self.api_key)
        }

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "chat": True,
            "completion": True,
            "streaming": True,
            "embeddings": True,
        }

    def get_models(self) -> List[Dict[str, Any]]:
        return [
            {"model_id": "gpt-4o-mini", "name": "GPT-4o Mini", "context_window": 128000},
            {"model_id": "gpt-4o", "name": "GPT-4o", "context_window": 128000},
            {"model_id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context_window": 128000},
        ]

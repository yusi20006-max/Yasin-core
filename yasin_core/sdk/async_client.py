import asyncio
from typing import Optional, List, Dict, Any, Union, Iterator
from .client import YasinCoreClient
from yasin_core.agents.base import BaseAgent
from yasin_core.agents.task import Task
from yasin_core.providers import AIRequest, AIResponse, AIResponseChunk

class AsyncYasinCoreClient:
    """
    Asynchronous version of the Yasin SDK Client.
    Integrates with standard Python asyncio loop, running synchronous blockages inside thread pool.
    """
    def __init__(self, sync_client: Optional[YasinCoreClient] = None, **kwargs):
        self._client = sync_client or YasinCoreClient(**kwargs)

    @property
    def sync_client(self) -> YasinCoreClient:
        return self._client

    @property
    def version(self) -> str:
        return self._client.version

    async def initialize(self) -> None:
        await asyncio.to_thread(self._client.initialize)

    async def start(self) -> None:
        await asyncio.to_thread(self._client.start)

    async def stop(self) -> None:
        await asyncio.to_thread(self._client.stop)

    async def health(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._client.health)

    async def status(self) -> Dict[str, Any]:
        return await asyncio.to_thread(self._client.status)

    async def execute_task(self, task: Task) -> Task:
        return await asyncio.to_thread(self._client.execute_task, task)

    async def generate_response(self, request: AIRequest, fallback_chain: Optional[List[str]] = None) -> AIResponse:
        return await asyncio.to_thread(self._client.generate_response, request, fallback_chain)

    async def save_memory(
        self, key: str, value: Any, category: str = "short-term", metadata: Optional[Dict[str, Any]] = None, ttl: Optional[int] = None
    ) -> None:
        await asyncio.to_thread(self._client.save_memory, key, value, category, metadata, ttl)

    async def get_memory(
        self, key: str, default: Any = None, category: str = "short-term"
    ) -> Any:
        return await asyncio.to_thread(self._client.get_memory, key, default, category)

    async def execute_tool(self, name: str, *args: Any, **kwargs: Any) -> Any:
        return await asyncio.to_thread(self._client.execute_tool, name, *args, **kwargs)

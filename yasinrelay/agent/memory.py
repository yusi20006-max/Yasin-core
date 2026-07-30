"""
memory.py
معماری حافظه برای پلتفرم ایجنت شامل انواع حافظه‌های موقت و محاوره‌ای.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from yasin_core.sdk import YasinCoreClient


class BaseMemory(ABC):
    """رابط پایه‌ی سیستم‌های حافظه."""

    @abstractmethod
    def store(self, key: str, value: Any) -> None:
        """ذخیره مقدار در حافظه."""
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Any:
        """بازیابی مقدار از حافظه."""
        pass

    @abstractmethod
    def clear(self) -> None:
        """پاک‌سازی کامل حافظه."""
        pass


class TaskMemory(BaseMemory):
    """حافظه کوتاه‌مدت متمرکز روی یک تسک مشخص."""

    def __init__(self) -> None:
        self._client = YasinCoreClient()

    def store(self, key: str, value: Any) -> None:
        self._client.save_memory(key, value, category="short-term")

    def retrieve(self, key: str) -> Any:
        return self._client.get_memory(key, category="short-term")

    def clear(self) -> None:
        self._client = YasinCoreClient()


class SessionMemory(BaseMemory):
    """حافظه بلندمدت‌تر که در طول یک جلسه اجرایی زنده می‌ماند."""

    def __init__(self) -> None:
        self._client = YasinCoreClient()

    def store(self, key: str, value: Any) -> None:
        self._client.save_memory(key, value, category="long-term")

    def retrieve(self, key: str) -> Any:
        return self._client.get_memory(key, category="long-term")

    def clear(self) -> None:
        self._client = YasinCoreClient()


class ConversationMemory(BaseMemory):
    """حافظه تخصصی برای نگه‌داری سابقه گفتگوها (نوبت‌های مکالمه)."""

    def __init__(self) -> None:
        self._client = YasinCoreClient()
        self._client.save_memory("messages", [], category="long-term")

    def store(self, key: str, value: Any) -> None:
        # در حافظه گفتگو، key می‌تواند نقش فرستنده (مانند user یا assistant) و value متن پیام باشد.
        messages = self._client.get_memory("messages", default=[], category="long-term")
        messages.append({"role": key, "content": str(value)})
        self._client.save_memory("messages", messages, category="long-term")

    def retrieve(self, key: str) -> Any:
        # بازیابی پیام‌ها؛ در صورتی که کلید 'all' باشد، تمام پیام‌ها برگردانده می‌شود.
        messages = self._client.get_memory("messages", default=[], category="long-term")
        if key == "all":
            return messages
        return [msg for msg in messages if msg["role"] == key]

    def clear(self) -> None:
        self._client.save_memory("messages", [], category="long-term")

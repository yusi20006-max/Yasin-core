"""
ai_processor.py
پردازش محتوای دریافت‌شده با AI: ترجمه، خلاصه‌سازی، بهبود متن.

رابط‌های پردازش محتوا و پیاده‌سازی‌های مربوطه.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any

from .fetch_engine import Post
from yasin_core.sdk import YasinCoreClient, BaseAgent, Task, active_context

logger = logging.getLogger(__name__)


@dataclass
class ProcessedContent:
    """خروجی پردازش‌شده‌ی یک Post، آماده برای انتشار."""

    source_post: Post
    text: str
    summary: Optional[str] = None


class ContentProcessor(ABC):
    """رابط پایه‌ی پردازشگر محتوا."""

    @abstractmethod
    def process(self, post: Post) -> ProcessedContent:
        raise NotImplementedError


class AIProcessor(ContentProcessor):
    """رابط ارتقایافته برای پردازشگران مبتنی بر هوش مصنوعی."""

    @abstractmethod
    def summarize(self, text: str) -> str:
        """خلاصه‌سازی متن."""
        raise NotImplementedError

    @abstractmethod
    def rewrite(self, text: str) -> str:
        """بازنویسی متن."""
        raise NotImplementedError

    @abstractmethod
    def translate(self, text: str, target_lang: str = "persian") -> str:
        """ترجمه متن به زبان مقصد."""
        raise NotImplementedError

    @abstractmethod
    def generate_title(self, text: str) -> str:
        """تولید عنوان مناسب برای متن."""
        raise NotImplementedError


class YasinRelayAIAgent(BaseAgent):
    """ایجنت اختصاصی پردازش هوش مصنوعی در زیرساخت Yasin-Core."""

    def __init__(self, name: str, description: str, api_key: str, base_url: str, model: str) -> None:
        super().__init__(name=name, description=description)
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.running = False

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def execute(self, input_data: Dict[str, Any]) -> Any:
        action = input_data.get("action", "process")
        text = input_data.get("text", "")

        if not self.api_key:
            if action == "generate_title":
                words = text.split()
                return " ".join(words[:5]) + "..." if len(words) > 5 else text
            return text

        url = f"{self.base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if action == "process":
            prompt = (
                "You are a professional content editor for Iranian social media channels (specifically Eitaa).\n"
                "Your task is to rewrite, translate (if in another language), or improve the following Telegram post "
                "to make it engaging, polished, and suitable for Iranian audiences. Keep emojis, layout, and meaning intact. "
                "Output ONLY the final processed text, with no introductory or concluding remarks.\n\n"
                f"Post content:\n{text}"
            )
        elif action == "summarize":
            prompt = f"Summarize the following text briefly in Persian:\n\n{text}"
        elif action == "rewrite":
            prompt = f"Rewrite and improve the following text in Persian:\n\n{text}"
        elif action == "translate":
            target_lang = input_data.get("target_lang", "persian")
            prompt = f"Translate the following text to {target_lang}:\n\n{text}"
        elif action == "generate_title":
            prompt = f"Generate a short catchy title/headline (in Persian) for the following text. Output ONLY the title:\n\n{text}"
        else:
            prompt = text

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7,
        }

        try:
            import requests
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"].strip()
            else:
                logger.error(f"AI API returned error {response.status_code}: {response.text}")
        except Exception as exc:
            logger.error(f"Failed to process content with AI Agent: {exc}", exc_info=True)

        if action == "generate_title":
            words = text.split()
            return " ".join(words[:5]) + "..." if len(words) > 5 else text
        return text


class PassthroughProcessor(AIProcessor):
    """
    پردازشگر هوش مصنوعی واقعی که محتوای پست را با استفاده از API ارتقا یا ترجمه می‌دهد.
    در صورتی که کلید API (AI_API_KEY) تنظیم نشده باشد یا خطا رخ دهد، متن را بدون تغییر عبور می‌دهد.
    """

    def __init__(self, api_key: str = "", base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o-mini") -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.client = YasinCoreClient()
        self.agent_name = "yasinrelay-ai-agent"

        # Register the AI Agent if not already registered
        if not self.client.get_agent(self.agent_name):
            agent = YasinRelayAIAgent(
                name=self.agent_name,
                description="YasinRelay Dedicated AI Processing Agent",
                api_key=self.api_key,
                base_url=self.base_url,
                model=self.model
            )
            self.client.register_agent(agent)

    def _execute_task(self, action: str, text: str, extra_params: Optional[Dict[str, Any]] = None) -> str:
        input_data = {"action": action, "text": text}
        if extra_params:
            input_data.update(extra_params)

        # Create SDK Context
        ctx = self.client.create_context({"action": action})

        with active_context(ctx):
            task = self.client.create_task(
                id=f"task-{action}-{hash(text)}",
                name=self.agent_name,
                input_data=input_data
            )
            executed_task = self.client.execute_task(task)
            result = executed_task.result if executed_task.result else text

            # Save memory through SDK
            self.client.save_memory(task.id, result, category="short-term")

            return result

    def process(self, post: Post) -> ProcessedContent:
        processed_text = self._execute_task("process", post.text)
        return ProcessedContent(source_post=post, text=processed_text)

    def summarize(self, text: str) -> str:
        """خلاصه‌سازی متن."""
        return self._execute_task("summarize", text)

    def rewrite(self, text: str) -> str:
        """بازنویسی متن."""
        return self._execute_task("rewrite", text)

    def translate(self, text: str, target_lang: str = "persian") -> str:
        """ترجمه متن."""
        return self._execute_task("translate", text, {"target_lang": target_lang})

    def generate_title(self, text: str) -> str:
        """تولید عنوان مناسب."""
        return self._execute_task("generate_title", text)


class CallableProcessor(ContentProcessor):
    """
    پردازشگری که یک تابع دلخواه (مثلاً فراخوانی یک API مدل زبانی) را
    اجرا می‌کند. تابع باید متن ورودی را بگیرد و متن پردازش‌شده را
    برگرداند — این‌طوری اتصال به هر backend ای (Anthropic API، مدل
    محلی و ...) بدون تغییر بقیه‌ی pipeline ممکن است.
    """

    def __init__(self, transform: Callable[[str], str]) -> None:
        self._transform = transform

    def process(self, post: Post) -> ProcessedContent:
        return ProcessedContent(source_post=post, text=self._transform(post.text))

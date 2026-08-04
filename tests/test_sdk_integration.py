"""
test_sdk_integration.py
تست‌های ادغام و عملکرد برای هماهنگی YasinRelay با Yasin-Core SDK.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, Mock
from yasin_core.sdk import YasinCoreClient, active_context, get_current_context
from yasinrelay.ai_processor import PassthroughProcessor, Post


def test_sdk_client_initialization():
    """تست مقداردهی اولیه کلاینت SDK در YasinRelay."""
    client = YasinCoreClient()
    assert client is not None
    assert client.version == "3.0.0"


@patch("requests.post")
def test_ai_task_execution_through_sdk(mock_post):
    """تست اجرای تسک‌های هوش مصنوعی با کمک SDK کلاینت."""
    # آماده‌سازی پاسخ فرضی API هوش مصنوعی
    mock_post.return_value = Mock(
        status_code=200,
        json=lambda: {
            "choices": [{
                "message": {
                    "content": "متن پردازش‌شده با هوش مصنوعی"
                }
            }]
        }
    )

    processor = PassthroughProcessor(api_key="fake-key")
    post = Post(channel="@news", message_id="101", text="متن اولیه")

    processed = processor.process(post)

    assert processed.text == "متن پردازش‌شده با هوش مصنوعی"

    # بررسی ذخیره‌سازی نتیجه در حافظه کوتاه مدت SDK
    task_id = f"task-process-{hash(post.text)}"
    memory_val = processor.client.get_memory(task_id, category="short-term")
    assert memory_val == "متن پردازش‌شده با هوش مصنوعی"


def test_context_creation_and_propagation():
    """تست ایجاد کانتکست و انتشار آن در کلاینت SDK."""
    client = YasinCoreClient()
    ctx = client.create_context({"env": "test-env", "pipeline": "yasinrelay"})

    with active_context(ctx):
        current_ctx = get_current_context()
        assert current_ctx.get("env") == "test-env"
        assert current_ctx.get("pipeline") == "yasinrelay"


def test_memory_usage_through_sdk():
    """تست مدیریت حافظه (بلندمدت و کوتاه‌مدت) به کمک کلاینت SDK."""
    client = YasinCoreClient()

    client.save_memory("key1", "val1", category="short-term")
    client.save_memory("key2", "val2", category="long-term")

    assert client.get_memory("key1", category="short-term") == "val1"
    assert client.get_memory("key2", category="long-term") == "val2"


def test_tool_execution_through_sdk():
    """تست اجرای ابزارها (Tools) به کمک کلاینت SDK."""
    client = YasinCoreClient()

    from yasin_core.sdk import tool

    @tool(name="format_post_for_eitaa", description="Formats text for Eitaa publishing")
    def format_post(text: str) -> str:
        return f"[Eitaa Channel] {text}"

    client.register_tool(format_post)

    assert "format_post_for_eitaa" in client.list_tools()
    assert client.get_tool("format_post_for_eitaa") == format_post

    result = client.execute_tool("format_post_for_eitaa", text="محتوای تستی")
    assert result == "[Eitaa Channel] محتوای تستی"

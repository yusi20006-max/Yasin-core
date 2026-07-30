"""
context.py
مدیریت زمینه اجرا (Context Manager)، متغیرهای اشتراکی و تاریخچه فعالیت‌ها.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from yasin_core.sdk import get_current_context


class ContextManager:
    """مدیریت کننده کانتکست و تاریخچه اجرای تسک‌ها برای هماهنگی با مدل‌های زبانی در آینده."""

    def __init__(self) -> None:
        self.started_at: datetime = datetime.now()
        # Initialize internal structures in current SDK context if not exists
        sdk_ctx = get_current_context()
        if sdk_ctx.get("shared_variables") is None:
            sdk_ctx.set("shared_variables", {})
        if sdk_ctx.get("task_metadata") is None:
            sdk_ctx.set("task_metadata", {})
        if sdk_ctx.get("execution_history") is None:
            sdk_ctx.set("execution_history", [])

    @property
    def shared_variables(self) -> Dict[str, Any]:
        return get_current_context().get("shared_variables", {})

    @property
    def task_metadata(self) -> Dict[str, Any]:
        return get_current_context().get("task_metadata", {})

    @property
    def execution_history(self) -> List[Dict[str, Any]]:
        return get_current_context().get("execution_history", [])

    def set_variable(self, key: str, value: Any) -> None:
        """ذخیره یک متغیر مشترک در کانتکست."""
        self.shared_variables[key] = value

    def get_variable(self, key: str, default: Any = None) -> Any:
        """بازیابی یک متغیر مشترک."""
        return self.shared_variables.get(key, default)

    def set_metadata(self, key: str, value: Any) -> None:
        """تنظیم متادیتای مرتبط با تسک جاری."""
        self.task_metadata[key] = value

    def get_metadata(self, key: str, default: Any = None) -> Any:
        """بازیابی متادیتای تسک جاری."""
        return self.task_metadata.get(key, default)

    def log_history_step(self, step_type: str, details: Dict[str, Any]) -> None:
        """ثبت یک گام اجرایی جدید در تاریخچه فرآیند."""
        self.execution_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": step_type,
            "details": details,
        })

    def get_history(self) -> List[Dict[str, Any]]:
        """بازیابی کل تاریخچه اجرا."""
        return self.execution_history

    def get_llm_context(self) -> Dict[str, Any]:
        """فرمت‌دهی و آماده‌سازی تمام اطلاعات کانتکست برای استفاده مدل زبانی."""
        return {
            "metadata": self.task_metadata,
            "variables": self.shared_variables,
            "history": self.execution_history,
            "elapsed_seconds": (datetime.now() - self.started_at).total_seconds(),
        }

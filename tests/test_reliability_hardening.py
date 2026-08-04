import time
import pytest
import threading
import logging
from unittest.mock import MagicMock

from yasin_core.events import Event, EventBus
from yasin_core.execution.engine import TaskExecutionEngine
from yasin_core.execution.models import Job
from yasin_core.execution.scheduler import Scheduler
from yasin_core.sdk import YasinCoreClient


def test_event_bus_shutdown_and_reset():
    """Verify EventBus executor shutdown, RuntimeError protection, and clean reset."""
    bus = EventBus()

    # Check early executor access
    exec1 = bus._get_executor()
    assert exec1 is not None
    assert not bus._is_shutdown

    called = False
    def mock_handler(event):
        nonlocal called
        called = True

    bus.subscribe("test_event", mock_handler, async_handle=True)

    # Shutdown EventBus
    bus.shutdown()
    assert bus._is_shutdown
    assert bus._executor is None

    # Try to publish with async handler and ensure it gracefully handles the shutdown
    with patch_logger() as log_handler:
        bus.publish("test_event")
        # Should log a failed submission instead of crashing
        assert any("Failed to submit" in rec.message for rec in log_handler.records)

    assert not called  # Async handler was not successfully scheduled

    # Ensure get_executor raises RuntimeError post-shutdown
    with pytest.raises(RuntimeError) as exc_info:
        bus._get_executor()
    assert "EventBus is shut down" in str(exc_info.value)

    # Reset EventBus
    bus.reset()
    assert not bus._is_shutdown
    assert bus._executor is None

    # Get executor should work again
    exec2 = bus._get_executor()
    assert exec2 is not None


def test_task_execution_engine_shutdown_warnings():
    """Verify TaskExecutionEngine shutdown worker terminations and join warnings."""
    client = YasinCoreClient()
    engine = TaskExecutionEngine(client=client)

    # Initialize engine workers
    engine.initialize()
    assert len(engine._workers) == 2

    # Shutdown and verify all workers are cleanly terminated
    with patch_logger() as log_handler:
        engine.shutdown()
        assert len(engine._workers) == 0
        assert not any("did not terminate" in rec.message for rec in log_handler.records)


def test_scheduler_shutdown_warnings():
    """Verify Scheduler shutdown loop checks and warnings."""
    client = YasinCoreClient()
    scheduler = Scheduler(client=client)

    scheduler.initialize()
    assert scheduler._thread is not None
    assert scheduler._thread.is_alive()

    with patch_logger() as log_handler:
        scheduler.shutdown()
        assert scheduler._thread is None
        assert not any("Scheduler background thread did not stop" in rec.message for rec in log_handler.records)


class PatchLoggerHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


from contextlib import contextmanager

@contextmanager
def patch_logger():
    handler = PatchLoggerHandler()
    logger = logging.getLogger("YASIN-EVENT_BUS")
    logger2 = logging.getLogger("YASIN-TASK-EXECUTION-ENGINE")
    logger3 = logging.getLogger("YASIN-SCHEDULER")

    logger.addHandler(handler)
    logger2.addHandler(handler)
    logger3.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger2.removeHandler(handler)
        logger3.removeHandler(handler)

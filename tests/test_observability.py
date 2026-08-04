import json
import logging
import time
import pytest
from unittest.mock import MagicMock

from yasin_core.sdk import (
    YasinCoreClient,
    MetricsRegistry,
    Counter,
    Gauge,
    Histogram,
    ErrorTracker,
    PerformanceTimer,
    JSONFormatter,
    ObservabilityService,
    InMemoryMetricProvider
)


def test_metrics_collection():
    """Test custom Counter, Gauge, and Histogram metrics in MetricsRegistry."""
    registry = MetricsRegistry()

    # Counter
    cnt = registry.counter("test_counter", "A test counter", labels={"env": "test"})
    assert cnt.value == 0.0
    cnt.inc()
    cnt.inc(5.5)
    assert cnt.value == 6.5

    with pytest.raises(ValueError):
        cnt.inc(-1.0)

    cnt.reset()
    assert cnt.value == 0.0

    # Gauge
    gg = registry.gauge("test_gauge", "A test gauge", labels={"env": "test"})
    assert gg.value == 0.0
    gg.set(42.0)
    assert gg.value == 42.0
    gg.inc(3.0)
    assert gg.value == 45.0
    gg.dec(5.0)
    assert gg.value == 40.0

    # Histogram
    hist = registry.histogram("test_histogram", "A test histogram")
    assert hist.count == 0
    hist.observe(1.2)
    hist.observe(2.8)
    assert hist.count == 2
    assert hist.sum == 4.0
    assert hist.avg == 2.0
    assert 1.2 in hist.values

    # Query metrics
    metrics = registry.get_all_metrics()
    assert len(metrics) == 3

    query_res = registry.query_metrics(name="test_counter")
    assert len(query_res) == 1
    assert query_res[0].name == "test_counter"

    query_lbls = registry.query_metrics(labels={"env": "test"})
    assert len(query_lbls) == 2


def test_error_tracking():
    """Test ErrorTracker recording, querying, and clearing errors."""
    tracker = ErrorTracker()

    # Record custom error
    rec1 = tracker.record_custom_error(
        component="test_component",
        message="Something went wrong",
        context_id="ctx-123",
        metadata={"foo": "bar"}
    )
    assert rec1.component == "test_component"
    assert rec1.message == "Something went wrong"
    assert rec1.context_id == "ctx-123"
    assert rec1.metadata == {"foo": "bar"}

    # Record real exception
    try:
        raise ValueError("Invalid argument value")
    except ValueError as ex:
        rec2 = tracker.record_error("math_component", ex, context_id="ctx-123")

    assert rec2.component == "math_component"
    assert "ValueError" in rec2.traceback_str
    assert "Invalid argument value" in rec2.message

    # Query errors
    all_errors = tracker.get_errors()
    assert len(all_errors) == 2

    comp_errors = tracker.get_errors(component="math_component")
    assert len(comp_errors) == 1
    assert comp_errors[0].message == "Invalid argument value"

    ctx_errors = tracker.get_errors(context_id="ctx-123")
    assert len(ctx_errors) == 2

    # Clear
    tracker.clear()
    assert len(tracker.get_errors()) == 0


def test_performance_timing():
    """Test measuring execution durations using PerformanceTimer."""
    registry = MetricsRegistry()

    # 1. As context manager
    timer = PerformanceTimer(registry, "context_duration", "Context manager timer")
    with timer:
        time.sleep(0.01)

    hist = registry.histogram("context_duration")
    assert hist.count == 1
    assert hist.sum >= 0.01

    # 2. As decorator
    @PerformanceTimer(registry, "decorator_duration", "Decorator timer", labels={"type": "fast"})
    def mock_function():
        time.sleep(0.01)
        return "done"

    res = mock_function()
    assert res == "done"

    hist_dec = registry.histogram("decorator_duration", labels={"type": "fast", "function": "mock_function"})
    assert hist_dec.count == 1
    assert hist_dec.sum >= 0.01


def test_structured_logging(capsys):
    """Test structured JSON logging integration."""
    logger = logging.getLogger("test_json_logger")
    logger.setLevel(logging.INFO)

    # Add StreamHandler with JSONFormatter
    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    logger.info("Service started successfully", extra={"extra": {"port": 8080, "host": "localhost"}})

    captured = capsys.readouterr()
    log_line = captured.err or captured.out
    assert log_line != ""

    # Parse as JSON to verify structure
    log_data = json.loads(log_line.strip())
    assert log_data["level"] == "INFO"
    assert log_data["message"] == "Service started successfully"
    assert log_data["port"] == 8080
    assert log_data["host"] == "localhost"
    assert "timestamp" in log_data


def test_observability_service_integration():
    """Integration test of ObservabilityService with a running YasinCoreClient."""
    client = YasinCoreClient()

    # Ensure service is registered
    assert client.service_registry.has_service("observability")
    obs_service = client.observability
    assert isinstance(obs_service, ObservabilityService)

    # Start client (triggers service initialize)
    client.start()

    # Emit events on EventBus
    client.event_bus.publish("task_started", {"id": "task-001", "name": "AI Processing"})
    client.event_bus.publish("task_completed", {"id": "task-001", "name": "AI Processing"})
    client.event_bus.publish("task_failed", {"id": "task-002", "name": "Media Prep", "error": "Disk Full"})

    # Allow async dispatch/handlers if any
    time.sleep(0.1)

    # Check metrics collected from EventBus
    obs_service.collect_all()

    assert obs_service.get_metric_value("yasin_event_bus_events_total", {"event_name": "task_started"}) == 1.0
    assert obs_service.get_metric_value("yasin_tasks_started_total", {"task_id": "task-001", "task_name": "AI Processing"}) == 1.0
    assert obs_service.get_metric_value("yasin_tasks_completed_total", {"task_id": "task-001", "task_name": "AI Processing"}) == 1.0
    assert obs_service.get_metric_value("yasin_tasks_failed_total", {"task_id": "task-002", "task_name": "Media Prep"}) == 1.0

    # Check errors recorded
    errs = obs_service.errors.get_errors(component="task_executor")
    assert len(errs) == 1
    assert errs[0].message == "Disk Full"

    # Check system and on-demand gauges
    assert obs_service.get_metric_value("yasin_runtime_memory_mb") > 0.0
    assert obs_service.get_metric_value("yasin_service_healthy", {"service_name": "observability"}) == 1.0

    # Check Health and Status reports
    health_rep = obs_service.health()
    assert health_rep["status"] == "degraded"  # because an error occurred
    assert health_rep["system"]["memory_mb"] > 0.0
    assert health_rep["error_summary"]["total_errors"] == 1

    status_rep = obs_service.status()
    assert status_rep["state"] == "active"
    assert status_rep["errors_count"] == 1
    assert len(status_rep["metrics"]) > 0

    # Record API request
    obs_service.record_api_request("GET", "/v1/metrics", 200, 0.05)
    assert obs_service.get_metric_value("yasin_api_requests_total", {"method": "GET", "endpoint": "/v1/metrics", "status_class": "2xx"}) == 1.0

    # Reload service
    client.reload()
    assert obs_service.get_metric_value("yasin_tasks_started_total", {"task_id": "task-001", "task_name": "AI Processing"}) is None
    assert len(obs_service.errors.get_errors()) == 0

    # Stop client
    client.stop()

# Yasin-Core Observability & Metrics System

Yasin-Core features a centralized, thread-safe, and modular **Observability & Metrics System**. It collects runtime statistics, service health, task execution metrics, errors, performance measurements, and structured logs across the Yasin ecosystem without introducing heavy third-party dependencies.

---

## Architecture Overview

The system consists of independent, decoupled components:

1. **Metrics Framework (`metrics.py`)**: Defines thread-safe metrics types (`Counter`, `Gauge`, `Histogram`) and a central `MetricsRegistry`.
2. **Metric Providers (`providers.py`)**: Modular collectors that snapshot or export metric data (e.g., `InMemoryMetricProvider`).
3. **Error Tracker (`error_tracker.py`)**: Captures detailed traceback logs, context, and metadata of exceptions/errors.
4. **Performance Timer (`performance.py`)**: Context manager and decorator (`PerformanceTimer`) to track execution durations.
5. **Structured Logging (`logger.py`)**: Integrates with python's logging to format logs as structured JSON (`JSONFormatter`).
6. **Observability Service (`service.py`)**: Managed standard runtime service orchestrating these components.

---

## Metrics Collection

The `MetricsRegistry` supports three standard metric types:

* **Counter**: Incremental metrics (e.g. task successes, events published).
* **Gauge**: Values that fluctuate up and down (e.g. resident memory, active contexts).
* **Histogram**: Samples observations to calculate counts, sums, and averages (e.g. execution durations).

Metrics are completely thread-safe and uniquely identified by a combination of their name and sorted custom labels.

---

## SDK Observability APIs

The observability system is fully exposed on the public `YasinCoreClient` via the `.observability` property.

### 1. Querying Metrics

```python
from yasin_core.sdk import YasinCoreClient

client = YasinCoreClient()
client.start()

# Increment a custom metric
metrics = client.observability.metrics
counter = metrics.counter("my_custom_action_total", labels={"env": "production"})
counter.inc()

# Retrieve latest value
val = client.observability.get_metric_value("my_custom_action_total", {"env": "production"})
print(f"Total actions: {val}") # Outputs: 1.0

# Query metrics list
all_metrics = client.observability.query_metrics(name="my_custom_action_total")
```

### 2. Error Tracking

Exceptions and errors are tracked in a thread-safe circular memory tracker:

```python
try:
    # Some risky operation
    raise ValueError("DB connection failed")
except ValueError as ex:
    client.observability.errors.record_error(
        component="database",
        exception=ex,
        context_id="ctx-999",
        metadata={"host": "localhost"}
    )

# Retrieve recorded errors
errors = client.observability.errors.get_errors(component="database")
for err in errors:
    print(f"[{err.timestamp}] Message: {err.message}")
    print(f"Stack Trace: {err.traceback_str}")
```

### 3. Performance Measurement

Measure execution duration using `PerformanceTimer` either as a context manager or as a decorator:

```python
# Decorator usage (auto-injects function name as label)
@client.observability.performance(client.observability.metrics, "function_duration_seconds")
def process_data():
    # processing...
    pass

# Context manager usage
with client.observability.performance(client.observability.metrics, "operation_duration_seconds", labels={"type": "ai"}):
    # execution...
    pass
```

### 4. Structured JSON Logging

Create and use JSON-formatted structured loggers for easier integration with third-party log forwarders (e.g., Elasticsearch, Datadog):

```python
from yasin_core.sdk import get_structured_logger

logger = get_structured_logger("agent-runner")
logger.info("Agent starting execution pipeline", extra={"extra": {"pipeline": "telegram_to_eitaa"}})
```

---

## Integration and Automated Tracking

### Event Bus Auto-Tracking
The `ObservabilityService` subscribes to standard `EventBus` events via a wildcard subscription. It automatically increments metrics and tracks failures for:
* Task execution events (`task_started`, `task_completed`, `task_failed`).
* Agent management events (`agent_registered`, `agent_started`, `agent_stopped`).

### On-Demand & System Metric Updates
When calling `status()` or `health()`, the service updates system-wide stats dynamically:
* CPU Usage (`yasin_runtime_cpu_percent`)
* Memory resident set size in MB (`yasin_runtime_memory_mb`)
* Uptime / State of other registered services (`yasin_service_healthy`)
* Total and Active contexts in the Context Engine (`yasin_contexts_total`, `yasin_contexts_active`)
* Plugin discovery and states (`yasin_plugins_total`, `yasin_plugins_active`)
* Memory entry counts (`yasin_memory_entries_total`)

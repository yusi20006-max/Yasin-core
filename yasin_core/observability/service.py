import os
import sys
import time
import threading
from typing import Dict, Any, List, Optional

from yasin_core.runtime.interfaces import BaseService
from yasin_core.observability.metrics import MetricsRegistry, Metric, Counter, Gauge, Histogram
from yasin_core.observability.providers import BaseMetricProvider, InMemoryMetricProvider
from yasin_core.observability.error_tracker import ErrorTracker, ErrorRecord
from yasin_core.observability.performance import PerformanceTimer

def get_process_memory_mb() -> float:
    """Return the current process resident memory usage in megabytes."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        pass
    try:
        import resource
        # resource.getrusage(resource.RUSAGE_SELF).ru_maxrss is in kilobytes on Linux, bytes on macOS
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if sys.platform == "darwin":
            return usage / (1024 * 1024)
        else:
            return usage / 1024
    except Exception:
        return 0.0

def get_process_cpu_percent() -> float:
    """
    Get the current process CPU usage percentage.
    
    Returns:
    	float: The process CPU usage percentage, or `0.0` when `psutil` is unavailable.
    """
    try:
        import psutil
        return psutil.Process(os.getpid()).cpu_percent()
    except ImportError:
        return 0.0


class ObservabilityService(BaseService):
    """
    Centralized, thread-safe Observability & Metrics Service for Yasin-Core ecosystem.
    Collects runtime information, service metrics, execution stats, errors, and system health.
    """

    def __init__(self, client: Any = None):
        """Initialize the observability service with an optional client integration."""
        super().__init__()
        self.client = client
        self.metrics = MetricsRegistry()
        self.errors = ErrorTracker()
        self.performance = PerformanceTimer
        self.providers: List[BaseMetricProvider] = []
        self._lock = threading.RLock()
        self._initialized = False

    def initialize(self) -> None:
        """
        Initialize the observability service and register its default metric provider and event handler when available.
        
        This operation is idempotent; repeated calls leave an already initialized service unchanged.
        """
        with self._lock:
            if self._initialized:
                return

            # Register default InMemoryMetricProvider
            self.register_provider(InMemoryMetricProvider())

            # Register with EventBus if available
            if self.client and hasattr(self.client, "event_bus") and self.client.event_bus:
                self.client.event_bus.subscribe("*", self._handle_event)

            self._initialized = True

    def shutdown(self) -> None:
        """Stop the observability service and unsubscribe its event handler."""
        with self._lock:
            if not self._initialized:
                return
            if self.client and hasattr(self.client, "event_bus") and self.client.event_bus:
                self.client.event_bus.unsubscribe("*", self._handle_event)
            self._initialized = False

    def reload(self) -> None:
        """Reset registered metrics, tracked errors, and provider state."""
        with self._lock:
            self.metrics.clear()
            self.errors.clear()
            for provider in self.providers:
                if hasattr(provider, "clear"):
                    provider.clear()

    def register_provider(self, provider: BaseMetricProvider) -> None:
        """Register a metric provider if it has not already been registered.
        
        Parameters:
            provider (BaseMetricProvider): The metric provider to register.
        """
        with self._lock:
            if provider not in self.providers:
                self.providers.append(provider)

    def record_api_request(self, method: str, endpoint: str, status_code: int, response_time: float) -> None:
        """
        Record metrics for an API request, including its duration and error status.
        
        Parameters:
        	method (str): HTTP method used for the request.
        	endpoint (str): API endpoint handling the request.
        	status_code (int): HTTP response status code.
        	response_time (float): Request duration in seconds.
        """
        status_class = f"{status_code // 100}xx"
        labels = {"method": method, "endpoint": endpoint, "status_class": status_class}

        # Increment API request count
        counter = self.metrics.counter(
            name="yasin_api_requests_total",
            description="Total number of API requests processed",
            labels=labels
        )
        counter.inc()

        # Observe duration
        duration_hist = self.metrics.histogram(
            name="yasin_api_request_duration_seconds",
            description="API request duration in seconds",
            labels={"method": method, "endpoint": endpoint}
        )
        duration_hist.observe(response_time)

        if status_code >= 400:
            err_lbls = dict(labels)
            err_lbls["status_code"] = str(status_code)
            self.metrics.counter(
                name="yasin_api_request_errors_total",
                description="Total number of API request errors",
                labels=err_lbls
            ).inc()

    def _handle_event(self, event: Any) -> None:
        """
        Record ecosystem metrics for an EventBus event, including task and agent lifecycle activity.
        
        Parameters:
        	event (Any): Event containing a name and optional payload.
        """
        event_name = getattr(event, "name", str(event))

        # Increment overall event counts
        self.metrics.counter(
            name="yasin_event_bus_events_total",
            description="Total number of events published on the Event Bus",
            labels={"event_name": event_name}
        ).inc()

        # Task lifecycle execution metrics
        if event_name == "task_started":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_tasks_started_total",
                description="Total number of tasks started",
                labels={"task_id": payload.get("id", "unknown"), "task_name": payload.get("name", "unknown")}
            ).inc()
        elif event_name == "task_completed":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_tasks_completed_total",
                description="Total number of tasks successfully completed",
                labels={"task_id": payload.get("id", "unknown"), "task_name": payload.get("name", "unknown")}
            ).inc()
        elif event_name == "task_failed":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_tasks_failed_total",
                description="Total number of tasks that failed",
                labels={"task_id": payload.get("id", "unknown"), "task_name": payload.get("name", "unknown")}
            ).inc()
            # Record failed task error to error tracker
            self.errors.record_custom_error(
                component="task_executor",
                message=payload.get("error", "Task execution failed"),
                metadata=payload
            )

        # Agent management metrics
        elif event_name == "agent_registered":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_agents_registered_total",
                description="Total number of agents registered",
                labels={"agent_name": payload.get("name", "unknown")}
            ).inc()
        elif event_name == "agent_started":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_agents_started_total",
                description="Total number of agents started",
                labels={"agent_name": payload.get("name", "unknown")}
            ).inc()
        elif event_name == "agent_stopped":
            payload = getattr(event, "payload", {})
            self.metrics.counter(
                name="yasin_agents_stopped_total",
                description="Total number of agents stopped",
                labels={"agent_name": payload.get("name", "unknown")}
            ).inc()

    def collect_all(self) -> None:
        """Refresh system, ecosystem, and registered provider metrics."""
        with self._lock:
            # 1. System CPU and Memory Metrics
            cpu = get_process_cpu_percent()
            mem = get_process_memory_mb()
            self.metrics.gauge("yasin_runtime_cpu_percent", "Current process CPU usage percent").set(cpu)
            self.metrics.gauge("yasin_runtime_memory_mb", "Current process resident set size in MB").set(mem)

            # 2. Service health state metrics
            if self.client and hasattr(self.client, "service_registry") and self.client.service_registry:
                try:
                    registry = self.client.service_registry
                    manager = getattr(registry, "_manager", None)
                    if manager:
                        for name in manager.list_services():
                            state = manager._states.get(name)
                            from yasin_core.runtime.models import ServiceState
                            is_healthy = 1 if state == ServiceState.ACTIVE else 0
                            self.metrics.gauge(
                                name="yasin_service_healthy",
                                description="Health status of a registered service (1 = healthy, 0 = unhealthy)",
                                labels={"service_name": name}
                            ).set(is_healthy)
                except Exception:
                    pass

            # 3. Context engine metrics
            if self.client and hasattr(self.client, "context_engine") and self.client.context_engine:
                try:
                    status_info = self.client.context_engine.get_status() or {}
                    self.metrics.gauge("yasin_contexts_total", "Total registered contexts").set(status_info.get("total_contexts", 0))
                    self.metrics.gauge("yasin_contexts_active", "Currently active contexts").set(status_info.get("active_contexts", 0))
                except Exception:
                    pass

            # 4. Plugin registry metrics
            if self.client and hasattr(self.client, "plugin_registry") and self.client.plugin_registry:
                try:
                    status_info = self.client.plugin_registry.status() or {}
                    plugins = status_info.get("plugins", {})
                    self.metrics.gauge("yasin_plugins_total", "Total discovered plugins").set(len(plugins))
                    active_count = sum(1 for p in plugins.values() if p.get("state") == "active")
                    self.metrics.gauge("yasin_plugins_active", "Currently active plugins").set(active_count)
                except Exception:
                    pass

            # 5. Memory subsystem metrics
            if self.client:
                if hasattr(self.client, "short_term_memory") and self.client.short_term_memory:
                    try:
                        status_info = self.client.short_term_memory.status() or {}
                        self.metrics.gauge(
                            name="yasin_memory_entries_total",
                            description="Total entries in the memory module",
                            labels={"category": "short-term"}
                        ).set(status_info.get("total_entries", 0))
                    except Exception:
                        pass
                if hasattr(self.client, "long_term_memory") and self.client.long_term_memory:
                    try:
                        status_info = self.client.long_term_memory.status() or {}
                        self.metrics.gauge(
                            name="yasin_memory_entries_total",
                            description="Total entries in the memory module",
                            labels={"category": "long-term"}
                        ).set(status_info.get("total_entries", 0))
                    except Exception:
                        pass

            # Collect metrics inside all registered metric providers
            for provider in self.providers:
                try:
                    provider.collect(self.metrics)
                except Exception:
                    pass

    def get_metric_value(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        """
        Retrieve a metric's numeric value for the specified labels.
        
        Parameters:
            name (str): Metric name to query.
            labels (Optional[Dict[str, str]]): Labels that identify the metric series.
        
        Returns:
            Optional[float]: The metric value, the sum for a histogram, or `None` when no supported metric value is found.
        """
        results = self.metrics.query_metrics(name=name, labels=labels)
        if not results:
            return None
        metric = results[0]
        if hasattr(metric, "value"):
            return metric.value
        elif hasattr(metric, "values"): # Histogram
            return metric.sum
        return None

    def query_metrics(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Query collected metrics using optional name, label, and time filters.
        
        Parameters:
        	name (Optional[str]): Metric name to match.
        	labels (Optional[Dict[str, str]]): Labels that matching metrics must include.
        	start_time (Optional[float]): Inclusive start of the time range as a timestamp.
        	end_time (Optional[float]): Inclusive end of the time range as a timestamp.
        
        Returns:
        	List[Dict[str, Any]]: Serialized dictionaries for the matching metrics.
        """
        metrics_objs = self.metrics.query_metrics(name, labels, start_time, end_time)
        return [m.to_dict() for m in metrics_objs]

    def health(self) -> Dict[str, Any]:
        """Generate a consolidated health report for the service and its ecosystem.
        
        Returns:
            Dict[str, Any]: A report containing overall status, timestamp, process resource
                usage, tracked error details, and available service health information.
        """
        self.collect_all()
        errors = self.errors.get_errors()
        status = "healthy"
        if errors:
            status = "degraded"

        return {
            "status": status,
            "timestamp": time.time(),
            "system": {
                "cpu_percent": get_process_cpu_percent(),
                "memory_mb": get_process_memory_mb(),
            },
            "error_summary": {
                "total_errors": len(errors),
                "latest_error": errors[-1].message if errors else None
            },
            "services": self.client.service_registry.get_health() if self.client and hasattr(self.client, "service_registry") else {}
        }

    def status(self) -> Dict[str, Any]:
        """Return overall execution metrics snapshot of the service and the entire ecosystem."""
        self.collect_all()

        # Get latest metrics snapshot from InMemoryMetricProvider if available
        metrics_data = []
        for p in self.providers:
            if isinstance(p, InMemoryMetricProvider):
                snap = p.get_latest_snapshot()
                if snap:
                    metrics_data = snap.get("metrics", [])
                    break
        if not metrics_data:
            metrics_data = [m.to_dict() for m in self.metrics.get_all_metrics()]

        return {
            "state": "active" if self._initialized else "inactive",
            "metrics_count": len(self.metrics.get_all_metrics()),
            "errors_count": len(self.errors.get_errors()),
            "metrics": metrics_data
        }

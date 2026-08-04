import time
import functools
from typing import Any, Callable, Dict, Optional
from yasin_core.observability.metrics import MetricsRegistry

class PerformanceTimer:
    """
    Utility class that works as both a context manager and a decorator
    to measure execution time and record it in a Histogram metric.
    """
    def __init__(
        self,
        registry: MetricsRegistry,
        metric_name: str,
        description: str = "Execution duration in seconds",
        labels: Optional[Dict[str, str]] = None
    ):
        """Initialize a performance timer with its metrics registry and histogram configuration.
        
        Parameters:
            registry (MetricsRegistry): Registry used to store the duration histogram.
            metric_name (str): Name of the histogram that records execution durations.
            description (str): Description for the duration metric.
            labels (Optional[Dict[str, str]]): Labels associated with recorded durations.
        """
        self.registry = registry
        self.metric_name = metric_name
        self.description = description
        self.labels = labels or {}
        self.start_time: Optional[float] = None

    def __enter__(self) -> "PerformanceTimer":
        """Start measuring execution time and return this timer."""
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Record the elapsed duration in the configured metrics histogram when timing has started."""
        if self.start_time is not None:
            elapsed = time.perf_counter() - self.start_time
            # Record in histogram
            hist = self.registry.histogram(self.metric_name, self.description, self.labels)
            hist.observe(elapsed)

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
        """Decorate a function to record its execution duration in a metrics histogram.
        
        Parameters:
            func (Callable[..., Any]): The function to decorate.
        
        Returns:
            Callable[..., Any]: A wrapped function that preserves the original metadata and records its execution duration.
        """
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # We want to measure the duration of this call
            # Let's add the function name to labels if not already specified, or keep existing labels
            labels = dict(self.labels)
            if "function" not in labels:
                labels["function"] = func.__name__

            start = time.perf_counter()
            try:
                return func(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - start
                hist = self.registry.histogram(self.metric_name, self.description, labels)
                hist.observe(elapsed)
        return wrapper

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
        self.registry = registry
        self.metric_name = metric_name
        self.description = description
        self.labels = labels or {}
        self.start_time: Optional[float] = None

    def __enter__(self) -> "PerformanceTimer":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.start_time is not None:
            elapsed = time.perf_counter() - self.start_time
            # Record in histogram
            hist = self.registry.histogram(self.metric_name, self.description, self.labels)
            hist.observe(elapsed)

    def __call__(self, func: Callable[..., Any]) -> Callable[..., Any]:
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

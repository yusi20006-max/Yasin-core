import time
import threading
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"

class Metric:
    """Base class representing a single metric instance with given name, type, and labels."""
    def __init__(self, name: str, metric_type: MetricType, description: str = "", labels: Optional[Dict[str, str]] = None):
        self.name = name
        self.type = metric_type
        self.description = description
        self.labels = labels or {}
        self.timestamp = time.time()
        self._lock = threading.RLock()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "type": self.type.value,
                "description": self.description,
                "labels": self.labels,
                "timestamp": self.timestamp,
            }

class Counter(Metric):
    """Counter represents a cumulative metric that can only increase or be reset."""
    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, MetricType.COUNTER, description, labels)
        self._value = 0.0

    def inc(self, value: float = 1.0) -> None:
        if value < 0:
            raise ValueError("Counter increments must be non-negative.")
        with self._lock:
            self._value += value
            self.timestamp = time.time()

    @property
    def value(self) -> float:
        with self._lock:
            return self._value

    def reset(self) -> None:
        with self._lock:
            self._value = 0.0
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            data = super().to_dict()
            data["value"] = self._value
            return data

class Gauge(Metric):
    """Gauge represents a single numerical value that can arbitrarily go up and down."""
    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, MetricType.GAUGE, description, labels)
        self._value = 0.0

    def set(self, value: float) -> None:
        with self._lock:
            self._value = value
            self.timestamp = time.time()

    def inc(self, value: float = 1.0) -> None:
        with self._lock:
            self._value += value
            self.timestamp = time.time()

    def dec(self, value: float = 1.0) -> None:
        with self._lock:
            self._value -= value
            self.timestamp = time.time()

    @property
    def value(self) -> float:
        with self._lock:
            return self._value

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            data = super().to_dict()
            data["value"] = self._value
            return data

class Histogram(Metric):
    """Histogram samples observations (usually things like request durations or sizes) and counts them."""
    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        super().__init__(name, MetricType.HISTOGRAM, description, labels)
        self._values: List[float] = []

    def observe(self, value: float) -> None:
        with self._lock:
            self._values.append(value)
            self.timestamp = time.time()

    @property
    def values(self) -> List[float]:
        with self._lock:
            return list(self._values)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._values)

    @property
    def sum(self) -> float:
        with self._lock:
            return sum(self._values)

    @property
    def avg(self) -> float:
        with self._lock:
            if not self._values:
                return 0.0
            return sum(self._values) / len(self._values)

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            data = super().to_dict()
            data.update({
                "count": len(self._values),
                "sum": sum(self._values),
                "avg": self.avg,
                "values": list(self._values),
            })
            return data

class MetricsRegistry:
    """Thread-safe registry to store, look up, and manage Metric instances."""
    def __init__(self):
        self._lock = threading.RLock()
        self._metrics: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Metric] = {}

    def _get_key(self, name: str, labels: Optional[Dict[str, str]]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        labels_tuple = ()
        if labels:
            labels_tuple = tuple(sorted(labels.items()))
        return name, labels_tuple

    def register(self, metric: Metric) -> None:
        with self._lock:
            key = self._get_key(metric.name, metric.labels)
            if key in self._metrics:
                raise ValueError(f"Metric '{metric.name}' with labels {metric.labels} is already registered.")
            self._metrics[key] = metric

    def counter(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Counter:
        with self._lock:
            key = self._get_key(name, labels)
            if key in self._metrics:
                metric = self._metrics[key]
                if not isinstance(metric, Counter):
                    raise TypeError(f"Metric '{name}' exists but is of type {type(metric).__name__}, not Counter.")
                return metric
            metric = Counter(name, description, labels)
            self._metrics[key] = metric
            return metric

    def gauge(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Gauge:
        with self._lock:
            key = self._get_key(name, labels)
            if key in self._metrics:
                metric = self._metrics[key]
                if not isinstance(metric, Gauge):
                    raise TypeError(f"Metric '{name}' exists but is of type {type(metric).__name__}, not Gauge.")
                return metric
            metric = Gauge(name, description, labels)
            self._metrics[key] = metric
            return metric

    def histogram(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Histogram:
        with self._lock:
            key = self._get_key(name, labels)
            if key in self._metrics:
                metric = self._metrics[key]
                if not isinstance(metric, Histogram):
                    raise TypeError(f"Metric '{name}' exists but is of type {type(metric).__name__}, not Histogram.")
                return metric
            metric = Histogram(name, description, labels)
            self._metrics[key] = metric
            return metric

    def get_all_metrics(self) -> List[Metric]:
        with self._lock:
            return list(self._metrics.values())

    def query_metrics(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Metric]:
        with self._lock:
            results = []
            for metric in self._metrics.values():
                if name and metric.name != name:
                    continue
                if labels:
                    match = True
                    for k, v in labels.items():
                        if metric.labels.get(k) != v:
                            match = False
                            break
                    if not match:
                        continue
                if start_time and metric.timestamp < start_time:
                    continue
                if end_time and metric.timestamp > end_time:
                    continue
                results.append(metric)
            return results

    def clear(self) -> None:
        with self._lock:
            self._metrics.clear()

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
        """Initialize a metric with its name, type, description, labels, and creation timestamp.
        
        Parameters:
        	name (str): The metric name.
        	metric_type (MetricType): The metric category.
        	description (str): A human-readable description of the metric.
        	labels (Optional[Dict[str, str]]): Labels associated with the metric.
        """
        self.name = name
        self.type = metric_type
        self.description = description
        self.labels = labels or {}
        self.timestamp = time.time()
        self._lock = threading.RLock()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the metric's metadata to a dictionary.
        
        Returns:
            Dict[str, Any]: The metric name, type, description, labels, and timestamp.
        """
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
        """Initialize a counter metric with an optional description and labels."""
        super().__init__(name, MetricType.COUNTER, description, labels)
        self._value = 0.0

    def inc(self, value: float = 1.0) -> None:
        """Increase the counter by the specified amount.
        
        Parameters:
        	value (float): The amount to add. Must be greater than or equal to zero.
        """
        if value < 0:
            raise ValueError("Counter increments must be non-negative.")
        with self._lock:
            self._value += value
            self.timestamp = time.time()

    @property
    def value(self) -> float:
        """Return the gauge's current value.
        
        Returns:
            float: The current gauge value.
        """
        with self._lock:
            return self._value

    def reset(self) -> None:
        """Reset the counter to zero."""
        with self._lock:
            self._value = 0.0
            self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the counter and its current value.
        
        Returns:
            Dict[str, Any]: A dictionary containing the counter's metric metadata and value.
        """
        with self._lock:
            data = super().to_dict()
            data["value"] = self._value
            return data

class Gauge(Metric):
    """Gauge represents a single numerical value that can arbitrarily go up and down."""
    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        """Initialize a gauge metric with an optional description and labels."""
        super().__init__(name, MetricType.GAUGE, description, labels)
        self._value = 0.0

    def set(self, value: float) -> None:
        """Set the gauge to a numeric value.
        
        Parameters:
        	value (float): The value assigned to the gauge.
        """
        with self._lock:
            self._value = value
            self.timestamp = time.time()

    def inc(self, value: float = 1.0) -> None:
        """Increase the gauge value by the specified amount.
        
        Parameters:
        	value (float): Amount to add to the current gauge value.
        """
        with self._lock:
            self._value += value
            self.timestamp = time.time()

    def dec(self, value: float = 1.0) -> None:
        """Decrease the gauge value by the specified amount.
        
        Parameters:
        	value (float): Amount to subtract from the current gauge value.
        """
        with self._lock:
            self._value -= value
            self.timestamp = time.time()

    @property
    def value(self) -> float:
        """Return the gauge's current value.
        
        Returns:
            float: The current gauge value.
        """
        with self._lock:
            return self._value

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the counter and its current value.
        
        Returns:
            Dict[str, Any]: A dictionary containing the counter's metric metadata and value.
        """
        with self._lock:
            data = super().to_dict()
            data["value"] = self._value
            return data

class Histogram(Metric):
    """Histogram samples observations (usually things like request durations or sizes) and counts them."""
    def __init__(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None):
        """Initialize a histogram metric with an optional description and labels."""
        super().__init__(name, MetricType.HISTOGRAM, description, labels)
        self._values: List[float] = []

    def observe(self, value: float) -> None:
        """Record a numeric observation for the histogram."""
        with self._lock:
            self._values.append(value)
            self.timestamp = time.time()

    @property
    def values(self) -> List[float]:
        """Return a copy of all observed values."""
        with self._lock:
            return list(self._values)

    @property
    def count(self) -> int:
        """Return the number of recorded observations."""
        with self._lock:
            return len(self._values)

    @property
    def sum(self) -> float:
        """Return the sum of all observed values."""
        with self._lock:
            return sum(self._values)

    @property
    def avg(self) -> float:
        """Calculate the average of all observed values.
        
        Returns:
        	float: The average observed value, or `0.0` when no values have been recorded.
        """
        with self._lock:
            if not self._values:
                return 0.0
            return sum(self._values) / len(self._values)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize the histogram and its observed-value statistics.
        
        Returns:
            Dict[str, Any]: A dictionary containing the histogram metadata, count, sum,
            average, and observed values.
        """
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
        """Initialize an empty, thread-safe metrics registry."""
        self._lock = threading.RLock()
        self._metrics: Dict[Tuple[str, Tuple[Tuple[str, str], ...]], Metric] = {}

    def _get_key(self, name: str, labels: Optional[Dict[str, str]]) -> Tuple[str, Tuple[Tuple[str, str], ...]]:
        """Build a registry key from a metric name and its sorted label pairs."""
        labels_tuple = ()
        if labels:
            labels_tuple = tuple(sorted(labels.items()))
        return name, labels_tuple

    def register(self, metric: Metric) -> None:
        """
        Register a metric in the registry.
        
        Parameters:
        	metric (Metric): The metric to register.
        
        Raises:
        	ValueError: If a metric with the same name and labels is already registered.
        """
        with self._lock:
            key = self._get_key(metric.name, metric.labels)
            if key in self._metrics:
                raise ValueError(f"Metric '{metric.name}' with labels {metric.labels} is already registered.")
            self._metrics[key] = metric

    def counter(self, name: str, description: str = "", labels: Optional[Dict[str, str]] = None) -> Counter:
        """
        Retrieve an existing counter or create and register a new one.
        
        Parameters:
        	name (str): The counter name.
        	description (str): A description of the counter.
        	labels (Optional[Dict[str, str]]): Labels identifying the counter.
        
        Returns:
        	Counter: The existing or newly registered counter.
        
        Raises:
        	TypeError: If a metric with the same name and labels exists with a different type.
        """
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
        """
        Retrieve an existing gauge or create and register a new one.
        
        Parameters:
        	name (str): The metric name.
        	description (str): A description of the metric.
        	labels (Optional[Dict[str, str]]): Labels identifying the metric.
        
        Returns:
        	Gauge: The existing or newly registered gauge.
        
        Raises:
        	TypeError: If a metric with the same name and labels exists with a different type.
        """
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
        """
        Retrieve or create a histogram metric with the specified name and labels.
        
        Parameters:
            name (str): The metric name.
            description (str): A description of the metric.
            labels (Optional[Dict[str, str]]): Labels identifying the metric.
        
        Returns:
            Histogram: The existing matching histogram or a newly created one.
        
        Raises:
            TypeError: If a metric with the same name and labels exists with a different type.
        """
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
        """Return all metrics currently registered in the registry.
        
        Returns:
            List[Metric]: The registered metrics.
        """
        with self._lock:
            return list(self._metrics.values())

    def query_metrics(
        self,
        name: Optional[str] = None,
        labels: Optional[Dict[str, str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None
    ) -> List[Metric]:
        """
        Filter registered metrics by name, labels, and timestamp range.
        
        Parameters:
            name (Optional[str]): Exact metric name to match.
            labels (Optional[Dict[str, str]]): Label values that each matching metric must contain.
            start_time (Optional[float]): Earliest allowed metric timestamp.
            end_time (Optional[float]): Latest allowed metric timestamp.
        
        Returns:
            List[Metric]: Metrics matching all specified filters.
        """
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
        """Remove all metrics from the registry."""
        with self._lock:
            self._metrics.clear()

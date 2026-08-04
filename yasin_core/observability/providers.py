import time
import threading
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from yasin_core.observability.metrics import MetricsRegistry, Metric

class BaseMetricProvider(ABC):
    """Abstract base class representing a metrics provider."""

    @abstractmethod
    def collect(self, registry: MetricsRegistry) -> None:
        """Collect metrics from the registry and process/store them."""
        pass

    @abstractmethod
    def export(self) -> Any:
        """Export the collected metrics."""
        pass


class InMemoryMetricProvider(BaseMetricProvider):
    """Thread-safe concrete provider that retains collected metrics in memory."""
    def __init__(self, max_snapshots: int = 1000):
        self.max_snapshots = max_snapshots
        self._snapshots: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

    def collect(self, registry: MetricsRegistry) -> None:
        """Take a snapshot of all metrics in the registry."""
        snapshot_time = time.time()
        metrics_data = [metric.to_dict() for metric in registry.get_all_metrics()]

        with self._lock:
            self._snapshots.append({
                "timestamp": snapshot_time,
                "metrics": metrics_data
            })
            if len(self._snapshots) > self.max_snapshots:
                self._snapshots.pop(0)

    def export(self) -> List[Dict[str, Any]]:
        """Return all stored metric snapshots."""
        with self._lock:
            return list(self._snapshots)

    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Return the most recent metric snapshot collected."""
        with self._lock:
            if not self._snapshots:
                return None
            return self._snapshots[-1]

    def clear(self) -> None:
        """Clear all collected snapshots."""
        with self._lock:
            self._snapshots.clear()

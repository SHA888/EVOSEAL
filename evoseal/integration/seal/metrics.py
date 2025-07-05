"""
Metrics collection for the SEAL system.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class Metrics:
    """Metrics collection for the SEAL system."""

    request_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    processing_times: List[float] = field(default_factory=list)
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_processing_time(self, duration: float) -> None:
        """Record processing time for a request."""
        self.processing_times.append(duration)

    def record_error(self, error: Exception) -> None:
        """Record an error that occurred."""
        self.error_count += 1
        error_type = error.__class__.__name__
        self.errors_by_type[error_type] += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics."""
        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "success_rate": (self.request_count - self.error_count) / max(1, self.request_count),
            "cache_hit_rate": self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            "avg_processing_time": (
                sum(self.processing_times) / len(self.processing_times)
                if self.processing_times
                else 0
            ),
            "errors_by_type": dict(self.errors_by_type),
        }

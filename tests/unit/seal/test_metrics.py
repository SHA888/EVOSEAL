"""Unit tests for the Metrics class."""

from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pytest

from evoseal.integration.seal.exceptions import (
    RateLimitError,
    SEALError,
    ValidationError,
)
from evoseal.integration.seal.metrics import Metrics


class TestMetrics:
    """Test cases for the Metrics class."""

    def test_initial_state(self):
        """Test that metrics are initialized correctly."""
        metrics = Metrics()
        assert metrics.request_count == 0
        assert metrics.error_count == 0
        assert metrics.cache_hits == 0
        assert metrics.cache_misses == 0
        assert metrics.processing_times == []
        assert metrics.errors_by_type == {}

    def test_record_processing_time(self):
        """Test recording processing times."""
        metrics = Metrics()
        metrics.record_processing_time(0.5)
        metrics.record_processing_time(1.0)

        assert metrics.processing_times == [0.5, 1.0]
        assert metrics.get_metrics_summary()["avg_processing_time"] == 0.75

    def test_record_error(self):
        """Test recording different types of errors."""
        metrics = Metrics()

        # Record different error types
        metrics.record_error(SEALError("Test error"))
        metrics.record_error(RateLimitError("Rate limit exceeded"))
        metrics.record_error(ValidationError("Invalid input"))

        # Check error counts
        assert metrics.error_count == 3
        assert metrics.errors_by_type == {
            "SEALError": 1,
            "RateLimitError": 1,
            "ValidationError": 1,
        }

        # Record another error of the same type
        metrics.record_error(SEALError("Another error"))
        assert metrics.error_count == 4
        assert metrics.errors_by_type["SEALError"] == 2

    def test_get_metrics_summary(self):
        """Test getting a summary of all metrics."""
        metrics = Metrics()

        # Set up some metrics
        metrics.request_count = 10
        # Reset error_count since record_error will increment it
        metrics.error_count = 0
        metrics.cache_hits = 6
        metrics.cache_misses = 4
        metrics.record_processing_time(0.5)
        metrics.record_processing_time(1.0)
        # Each record_error call increments error_count by 1
        metrics.record_error(SEALError("Test error"))
        metrics.record_error(RateLimitError("Rate limit"))

        # Get the summary
        summary = metrics.get_metrics_summary()

        # Verify the summary
        assert summary["request_count"] == 10
        assert summary["error_count"] == 2  # Each error is only counted once
        assert summary["success_rate"] == 0.8  # (10-2)/10
        assert summary["cache_hit_rate"] == 0.6  # 6/(6+4)
        assert summary["avg_processing_time"] == 0.75  # (0.5+1.0)/2
        assert summary["errors_by_type"] == {
            "SEALError": 1,  # One SEALError recorded
            "RateLimitError": 1,  # One RateLimitError recorded
        }

    def test_edge_cases(self):
        """Test edge cases in metrics calculation."""
        # Test with no requests
        metrics = Metrics()
        summary = metrics.get_metrics_summary()
        assert summary["success_rate"] == 0.0
        assert summary["cache_hit_rate"] == 0.0
        assert summary["avg_processing_time"] == 0.0

        # Test with no cache hits
        metrics = Metrics(cache_hits=0, cache_misses=0)
        assert metrics.get_metrics_summary()["cache_hit_rate"] == 0.0

        # Test with only hits and no misses
        metrics = Metrics(cache_hits=5, cache_misses=0)
        assert metrics.get_metrics_summary()["cache_hit_rate"] == 1.0

    def test_immutability(self):
        """Test that the returned summary is a copy and won't affect metrics."""
        metrics = Metrics()
        summary1 = metrics.get_metrics_summary()
        summary1["request_count"] = 100  # This should not affect the metrics

        summary2 = metrics.get_metrics_summary()
        assert summary2["request_count"] == 0  # Still the default value

#!/usr/bin/env python3
"""Test script demonstrating the enhanced RegressionDetector interface.

This script shows how to use the RegressionDetector for:
1. Establishing baselines
2. Comparing versions against baselines
3. Setting up alert callbacks
4. Integrating with testing frameworks
5. Running comprehensive regression analysis
"""

import asyncio
import json
import tempfile
from pathlib import Path
from typing import Any, Dict

from evoseal.core.events import EventType, publish, subscribe
from evoseal.core.logging_system import get_logger
from evoseal.core.metrics_tracker import MetricsTracker
from evoseal.core.regression_detector import RegressionDetector

logger = get_logger(__name__)


class MockMetricsTracker:
    """Mock metrics tracker for testing purposes."""

    def __init__(self):
        self.metrics_data = {
            "v1.0": {
                "success_rate": 0.95,
                "accuracy": 0.88,
                "duration_sec": 2.5,
                "memory_mb": 128,
                "error_rate": 0.05,
                "pass_rate": 0.92,
            },
            "v1.1": {
                "success_rate": 0.97,  # Improvement
                "accuracy": 0.85,  # Slight regression
                "duration_sec": 3.2,  # Performance regression
                "memory_mb": 135,  # Memory increase
                "error_rate": 0.03,  # Improvement
                "pass_rate": 0.94,  # Improvement
            },
            "v1.2": {
                "success_rate": 0.89,  # Critical regression
                "accuracy": 0.82,  # Regression
                "duration_sec": 4.1,  # Significant performance regression
                "memory_mb": 150,  # Memory regression
                "error_rate": 0.11,  # Critical error rate increase
                "pass_rate": 0.85,  # Regression
            },
        }

    def get_metrics_by_id(self, version_id):
        """Get metrics for a specific version."""
        return self.metrics_data.get(str(version_id), {})

    def compare_metrics(self, old_version_id, new_version_id):
        """Compare metrics between two versions."""
        old_metrics = self.get_metrics_by_id(old_version_id)
        new_metrics = self.get_metrics_by_id(new_version_id)

        if not old_metrics or not new_metrics:
            return {}

        comparison = {}
        for metric_name in old_metrics:
            if metric_name in new_metrics:
                old_val = old_metrics[metric_name]
                new_val = new_metrics[metric_name]
                change_pct = (new_val - old_val) / old_val if old_val != 0 else 0

                comparison[metric_name] = {
                    "baseline": old_val,
                    "current": new_val,
                    "change_pct": change_pct,
                    "absolute_change": new_val - old_val,
                }

        return comparison


def alert_callback(regression_data: Dict[str, Any]) -> None:
    """Example alert callback function."""
    logger.warning("🚨 REGRESSION ALERT TRIGGERED!")
    logger.warning(f"Detected regressions in {len(regression_data)} metrics:")

    for metric, details in regression_data.items():
        severity = details.get("severity", "unknown")
        change = details.get("change", 0)
        logger.warning(f"  - {metric}: {severity} severity ({change:.2%} change)")


def email_alert_callback(regression_data: Dict[str, Any]) -> None:
    """Example email alert callback (mock)."""
    logger.info("📧 Sending email alert to development team...")
    critical_count = len(
        [
            r
            for r in regression_data.values()
            if isinstance(r, dict) and r.get("severity") == "critical"
        ]
    )

    if critical_count > 0:
        logger.warning(f"CRITICAL: {critical_count} critical regressions detected!")
    else:
        logger.info("Non-critical regressions detected - monitoring required")


async def event_listener():
    """Listen for regression detection events."""

    def handle_baseline_established(event_data):
        logger.info(
            f"✅ Baseline established: {event_data.get('baseline_name')} "
            f"from version {event_data.get('version_id')}"
        )

    def handle_regression_alert(event_data):
        logger.warning(
            f"⚠️ Regression alert: {event_data.get('regression_count')} regressions, "
            f"Critical: {len(event_data.get('critical_regressions', []))}"
        )

    # Subscribe to events
    subscribe(EventType.BASELINE_ESTABLISHED, handle_baseline_established)
    subscribe(EventType.REGRESSION_ALERT, handle_regression_alert)


async def test_regression_detector_interface():
    """Test the enhanced RegressionDetector interface."""

    logger.info("🧪 Testing Enhanced RegressionDetector Interface")
    logger.info("=" * 60)

    # Set up event listener
    await event_listener()

    # Create temporary directory for baselines
    with tempfile.TemporaryDirectory() as temp_dir:
        baseline_path = Path(temp_dir) / "test_baselines.json"

        # Initialize RegressionDetector with enhanced configuration
        config = {
            "regression_threshold": 0.05,  # 5% threshold
            "baseline_storage_path": str(baseline_path),
            "alert_enabled": True,
            "auto_baseline_update": False,
            "monitored_metrics": [
                "success_rate",
                "accuracy",
                "duration_sec",
                "memory_mb",
                "error_rate",
                "pass_rate",
            ],
            "metric_thresholds": {
                "success_rate": {"regression": 0.03, "critical": 0.10},
                "accuracy": {"regression": 0.05, "critical": 0.15},
                "duration_sec": {"regression": 0.20, "critical": 0.50},
                "memory_mb": {"regression": 0.15, "critical": 0.30},
                "error_rate": {"regression": 0.50, "critical": 1.00},
                "pass_rate": {"regression": 0.05, "critical": 0.15},
            },
        }

        # Create mock metrics tracker
        mock_tracker = MockMetricsTracker()

        # Initialize RegressionDetector
        detector = RegressionDetector(config, mock_tracker)

        logger.info(
            f"📊 Initialized RegressionDetector monitoring {len(detector.monitored_metrics)} metrics"
        )

        # Test 1: Establish baseline
        logger.info("\n1️⃣ Testing Baseline Establishment")
        logger.info("-" * 40)

        success = detector.establish_baseline("v1.0", "production_baseline")
        logger.info(
            f"Baseline establishment: {'✅ Success' if success else '❌ Failed'}"
        )

        # List baselines
        baselines = detector.list_baselines()
        logger.info(f"Available baselines: {len(baselines)}")
        for baseline in baselines:
            logger.info(
                f"  - {baseline['name']}: v{baseline['version_id']} "
                f"({baseline['metrics_count']} metrics)"
            )

        # Test 2: Register alert callbacks
        logger.info("\n2️⃣ Testing Alert System")
        logger.info("-" * 40)

        detector.register_alert_callback(alert_callback)
        detector.register_alert_callback(email_alert_callback)
        logger.info("Registered 2 alert callbacks")

        # Test 3: Testing framework integration
        logger.info("\n3️⃣ Testing Framework Integration")
        logger.info("-" * 40)

        pytest_config = {
            "test_command": "pytest tests/",
            "coverage_threshold": 0.80,
            "performance_tests": True,
        }

        integration_success = detector.integrate_with_test_framework(
            "pytest", pytest_config
        )
        logger.info(
            f"Pytest integration: {'✅ Success' if integration_success else '❌ Failed'}"
        )

        # Test 4: Compare against baseline (minor regressions)
        logger.info("\n4️⃣ Testing Baseline Comparison (v1.1)")
        logger.info("-" * 40)

        has_regression, regression_details = detector.compare_against_baseline(
            "v1.1", "production_baseline"
        )
        logger.info(f"Regression detected: {'⚠️ Yes' if has_regression else '✅ No'}")

        if has_regression:
            summary = detector.get_regression_summary(regression_details)
            logger.info("Regression summary:")
            logger.info(f"  - Total regressions: {summary['total_regressions']}")
            logger.info(f"  - Severity counts: {summary['severity_counts']}")
            logger.info(f"  - Recommendation: {summary['recommendation']}")

        # Test 5: Comprehensive regression analysis (critical regressions)
        logger.info("\n5️⃣ Testing Comprehensive Analysis (v1.2)")
        logger.info("-" * 40)

        analysis_results = detector.run_regression_analysis(
            "v1.2", "production_baseline", trigger_alerts=True
        )

        logger.info(f"Analysis completed for version {analysis_results['version_id']}")
        logger.info(
            f"Has regression: {'⚠️ Yes' if analysis_results['has_regression'] else '✅ No'}"
        )

        if analysis_results["has_regression"]:
            summary = analysis_results["summary"]
            logger.info("Analysis summary:")
            logger.info(f"  - Total regressions: {summary['total_regressions']}")
            logger.info(
                f"  - Critical regressions: {len(summary['critical_regressions'])}"
            )
            logger.info(
                f"  - Affected metrics: {', '.join(summary['affected_metrics'])}"
            )
            logger.info(f"  - Recommendation: {summary['recommendation']}")

            # Show detailed regression information
            logger.info("Detailed regressions:")
            for metric, details in analysis_results["regression_details"].items():
                if isinstance(details, dict):
                    severity = details.get("severity", "unknown")
                    change = details.get("change", 0)
                    logger.info(f"  - {metric}: {severity} ({change:+.2%})")

        # Test 6: Test direct regression detection
        logger.info("\n6️⃣ Testing Direct Regression Detection")
        logger.info("-" * 40)

        has_regression, regression_details = detector.detect_regression("v1.0", "v1.2")
        logger.info(
            f"Direct comparison (v1.0 → v1.2): {'⚠️ Regression' if has_regression else '✅ No regression'}"
        )

        # Test 7: Baseline persistence
        logger.info("\n7️⃣ Testing Baseline Persistence")
        logger.info("-" * 40)

        # Create new detector instance to test loading
        detector2 = RegressionDetector(config, mock_tracker)
        baselines2 = detector2.list_baselines()
        logger.info(f"Loaded baselines in new instance: {len(baselines2)}")

        # Verify baseline data
        baseline_data = detector2.get_baseline("production_baseline")
        if baseline_data:
            logger.info("✅ Baseline data successfully persisted and loaded")
            logger.info(f"  - Version: {baseline_data['version_id']}")
            logger.info(f"  - Metrics: {len(baseline_data['metrics'])}")
        else:
            logger.error("❌ Failed to load baseline data")

        logger.info("\n🎉 RegressionDetector Interface Test Complete!")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_regression_detector_interface())

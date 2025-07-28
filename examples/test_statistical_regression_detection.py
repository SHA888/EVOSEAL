#!/usr/bin/env python3
"""Test script demonstrating enhanced statistical regression detection.

This script shows the advanced statistical analysis and anomaly detection
capabilities including:
1. Trend analysis with linear regression
2. Anomaly detection using Z-score and IQR methods
3. Behavioral pattern analysis
4. Statistical significance testing
5. Confidence interval analysis
"""

import asyncio
import json
import math
import secrets
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from evoseal.core.events import EventType, publish, subscribe
from evoseal.core.logging_system import get_logger
from evoseal.core.regression_detector import RegressionDetector

logger = get_logger(__name__)


class AdvancedMockMetricsTracker:
    """Advanced mock metrics tracker with realistic data patterns."""

    def __init__(self):
        # Generate realistic time series data with trends and anomalies
        self.metrics_data = self._generate_realistic_metrics()

    def _generate_realistic_metrics(self) -> Dict[str, Dict[str, float]]:
        """Generate realistic metrics data with trends, noise, and anomalies."""
        data = {}

        # Generate 20 versions of data
        for i in range(20):
            version_id = f"v1.{i}"

            # Base metrics with gradual improvement trend
            base_success_rate = 0.85 + (i * 0.01)  # Gradual improvement
            base_accuracy = 0.80 + (i * 0.008)  # Gradual improvement
            base_duration = 3.0 - (i * 0.05)  # Performance improvement
            base_memory = 120 + (i * 2)  # Gradual memory increase
            base_error_rate = 0.15 - (i * 0.005)  # Error rate improvement

            # Add realistic noise using cryptographically secure random number generator
            secure_random = secrets.SystemRandom()
            noise_factor = 0.02
            success_rate = base_success_rate + secure_random.uniform(-noise_factor, noise_factor)
            accuracy = base_accuracy + secure_random.uniform(-noise_factor, noise_factor)
            duration = base_duration + secure_random.uniform(-noise_factor * 10, noise_factor * 10)
            memory = base_memory + secure_random.uniform(-noise_factor * 50, noise_factor * 50)
            error_rate = base_error_rate + secure_random.uniform(-noise_factor, noise_factor)

            # Introduce specific anomalies
            if i == 8:  # Anomaly at version 8
                success_rate *= 0.7  # 30% drop - critical anomaly
                error_rate *= 2.5  # Error spike
            elif i == 15:  # Another anomaly at version 15
                duration *= 2.2  # Performance regression
                memory *= 1.4  # Memory spike
            elif i == 12:  # Subtle anomaly
                accuracy *= 0.92  # Slight accuracy drop

            # Ensure values stay within realistic bounds
            data[version_id] = {
                "success_rate": success_rate,
                "accuracy": accuracy,
                "duration_sec": duration,
                "memory_mb": memory,
                "error_rate": error_rate,
                "pass_rate": success_rate * 0.95,  # Correlated with success rate
            }

        return data

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


def print_statistical_analysis(metric_name: str, stats: Dict[str, Any]) -> None:
    """Print formatted statistical analysis results."""
    logger.info(f"\n📊 Statistical Analysis for {metric_name}:")
    logger.info(f"  Mean: {stats.get('mean', 0):.4f}")
    logger.info(f"  Median: {stats.get('median', 0):.4f}")
    logger.info(f"  Std Dev: {stats.get('std_dev', 0):.4f}")
    logger.info(f"  Coefficient of Variation: {stats.get('coefficient_of_variation', 0):.4f}")

    ci = stats.get("confidence_interval", (0, 0))
    logger.info(
        f"  {stats.get('confidence_level', 0.95)*100:.0f}% Confidence Interval: [{ci[0]:.4f}, {ci[1]:.4f}]"
    )

    # Trend analysis
    trend = stats.get("trend_analysis", {})
    if trend:
        logger.info(
            f"  Trend: {trend.get('direction', 'unknown')} ({trend.get('strength', 'unknown')})"
        )
        logger.info(f"  Slope: {trend.get('slope', 0):.6f}")
        logger.info(f"  R²: {trend.get('r_squared', 0):.4f}")
        logger.info(f"  Predicted Next: {trend.get('predicted_next', 0):.4f}")

    # Anomalies
    anomalies = stats.get("anomalies", [])
    if anomalies:
        logger.info(f"  🚨 Anomalies Detected: {len(anomalies)}")
        for anomaly in anomalies[:3]:  # Show first 3 anomalies
            method = anomaly.get("method", "unknown")
            severity = anomaly.get("severity", "unknown")
            value = anomaly.get("value", 0)
            logger.info(
                f"    - Index {anomaly.get('index', 0)}: {value:.4f} ({method}, {severity})"
            )


def print_enhanced_regression_analysis(metric_name: str, analysis: Dict[str, Any]) -> None:
    """Print formatted enhanced regression analysis."""
    logger.info(f"\n🔍 Enhanced Regression Analysis for {metric_name}:")

    # Basic regression
    basic = analysis.get("basic_regression")
    if basic:
        logger.info(f"  Basic Regression: {basic.get('severity', 'none')} severity")
        logger.info(f"  Change: {basic.get('change', 0):+.2%}")

    # Statistical significance
    stat_sig = analysis.get("statistical_significance")
    if stat_sig:
        within_ci = stat_sig.get("within_confidence_interval", True)
        significance = stat_sig.get("significance", "unknown")
        logger.info(f"  Statistical Significance: {significance}")
        logger.info(f"  Within Confidence Interval: {'✅ Yes' if within_ci else '❌ No'}")

    # Historical context
    hist_context = analysis.get("historical_context")
    if hist_context:
        percentile = hist_context.get("percentile_rank", 50)
        deviation = hist_context.get("deviation_from_mean", 0)
        logger.info(f"  Historical Percentile: {percentile:.1f}%")
        logger.info(f"  Deviation from Mean: {deviation:+.4f}")

    # Anomaly status
    anomaly_status = analysis.get("anomaly_status")
    if anomaly_status:
        is_anomaly = anomaly_status.get("is_anomaly", False)
        logger.info(f"  Anomaly Status: {'🚨 ANOMALY DETECTED' if is_anomaly else '✅ Normal'}")
        if is_anomaly:
            details = anomaly_status.get("anomaly_details", [])
            for detail in details:
                method = detail.get("method", "unknown")
                severity = detail.get("severity", "unknown")
                logger.info(f"    - Method: {method}, Severity: {severity}")


async def test_statistical_regression_detection():
    """Test the enhanced statistical regression detection capabilities."""

    logger.info("🧪 Testing Statistical Regression Detection")
    logger.info("=" * 60)

    # Create temporary directory for baselines
    with tempfile.TemporaryDirectory() as temp_dir:
        baseline_path = Path(temp_dir) / "statistical_baselines.json"

        # Initialize RegressionDetector with statistical analysis enabled
        config = {
            "regression_threshold": 0.05,
            "baseline_storage_path": str(baseline_path),
            "alert_enabled": True,
            "monitored_metrics": [
                "success_rate",
                "accuracy",
                "duration_sec",
                "memory_mb",
                "error_rate",
                "pass_rate",
            ],
            "statistical_analysis": {
                "confidence_level": 0.95,
                "min_samples": 3,
                "trend_window": 10,
                "outlier_threshold": 2.0,
                "enable_trend_analysis": True,
                "enable_anomaly_detection": True,
                "enable_seasonal_adjustment": False,
            },
            "anomaly_detection": {
                "algorithms": ["zscore", "iqr", "isolation"],
                "sensitivity": "medium",
                "adaptive_threshold": True,
                "pattern_recognition": True,
            },
        }

        # Create advanced mock metrics tracker
        mock_tracker = AdvancedMockMetricsTracker()

        # Initialize RegressionDetector
        detector = RegressionDetector(config, mock_tracker)

        logger.info("📊 Initialized Statistical RegressionDetector")
        logger.info(
            f"Statistical Analysis: {'✅ Enabled' if config['statistical_analysis']['enable_trend_analysis'] else '❌ Disabled'}"
        )
        logger.info(
            f"Anomaly Detection: {'✅ Enabled' if config['statistical_analysis']['enable_anomaly_detection'] else '❌ Disabled'}"
        )

        # Test 1: Build historical data
        logger.info("\n1️⃣ Building Historical Data")
        logger.info("-" * 40)

        # Add historical metrics for statistical analysis
        for i in range(10):
            version_id = f"v1.{i}"
            metrics = mock_tracker.get_metrics_by_id(version_id)
            detector.update_historical_metrics(version_id, metrics)

        logger.info("Added historical data for 10 versions")

        # Test 2: Statistical Analysis of Individual Metrics
        logger.info("\n2️⃣ Statistical Analysis of Individual Metrics")
        logger.info("-" * 40)

        # Analyze success_rate metric
        success_rate_values = [
            mock_tracker.get_metrics_by_id(f"v1.{i}")["success_rate"] for i in range(10)
        ]
        stats = detector.analyze_metric_statistics("success_rate", success_rate_values)
        print_statistical_analysis("success_rate", stats)

        # Analyze duration_sec metric (should show performance trend)
        duration_values = [
            mock_tracker.get_metrics_by_id(f"v1.{i}")["duration_sec"] for i in range(10)
        ]
        duration_stats = detector.analyze_metric_statistics("duration_sec", duration_values)
        print_statistical_analysis("duration_sec", duration_stats)

        # Test 3: Anomaly Detection on Known Anomalous Version
        logger.info("\n3️⃣ Anomaly Detection on Known Anomalous Version (v1.8)")
        logger.info("-" * 40)

        # v1.8 has intentional anomalies (success rate drop, error spike)
        anomalous_metrics = mock_tracker.get_metrics_by_id("v1.8")
        logger.info(f"v1.8 Metrics: {json.dumps(anomalous_metrics, indent=2)}")

        # Update historical data to include the anomalous version
        detector.update_historical_metrics("v1.8", anomalous_metrics)

        # Analyze with anomaly detection
        success_rate_with_anomaly = success_rate_values + [anomalous_metrics["success_rate"]]
        anomaly_stats = detector.analyze_metric_statistics(
            "success_rate", success_rate_with_anomaly
        )
        print_statistical_analysis("success_rate (with anomaly)", anomaly_stats)

        # Test 4: Enhanced Regression Detection
        logger.info("\n4️⃣ Enhanced Regression Detection (v1.7 → v1.8)")
        logger.info("-" * 40)

        # Compare normal version to anomalous version
        has_regression, regression_details = detector.detect_regression("v1.7", "v1.8")

        logger.info(f"Regression Detected: {'⚠️ Yes' if has_regression else '✅ No'}")

        if has_regression:
            logger.info(f"Regressions found in {len(regression_details)} metrics:")
            for metric, details in regression_details.items():
                severity = details.get("severity", "unknown")
                change = details.get("change", 0)
                logger.info(f"  - {metric}: {severity} severity ({change:+.2%})")

                # Show enhanced analysis for critical regressions
                if severity in ["high", "critical"]:
                    print_enhanced_regression_analysis(metric, details)

        # Test 5: Trend Analysis Over Time
        logger.info("\n5️⃣ Trend Analysis Over Time")
        logger.info("-" * 40)

        # Analyze trends across multiple versions
        versions_to_analyze = [f"v1.{i}" for i in range(15)]

        for metric_name in ["success_rate", "duration_sec", "memory_mb"]:
            values = [mock_tracker.get_metrics_by_id(v)[metric_name] for v in versions_to_analyze]
            trend_stats = detector.analyze_metric_statistics(metric_name, values)

            trend = trend_stats.get("trend_analysis", {})
            if trend:
                direction = trend.get("direction", "unknown")
                strength = trend.get("strength", "unknown")
                slope = trend.get("slope", 0)
                r_squared = trend.get("r_squared", 0)

                logger.info(f"📈 {metric_name}: {direction} trend ({strength})")
                logger.info(f"   Slope: {slope:.6f}, R²: {r_squared:.4f}")

        # Test 6: Performance Regression Detection (v1.14 → v1.15)
        logger.info("\n6️⃣ Performance Regression Detection (v1.14 → v1.15)")
        logger.info("-" * 40)

        # v1.15 has performance regression (duration and memory spike)
        has_perf_regression, perf_details = detector.detect_regression("v1.14", "v1.15")

        logger.info(f"Performance Regression: {'⚠️ Detected' if has_perf_regression else '✅ None'}")

        if has_perf_regression:
            for metric, details in perf_details.items():
                if metric in ["duration_sec", "memory_mb"]:
                    print_enhanced_regression_analysis(metric, details)

        # Test 7: Statistical Significance Testing
        logger.info("\n7️⃣ Statistical Significance Testing")
        logger.info("-" * 40)

        # Test statistical significance of changes
        test_cases = [
            ("v1.5", "v1.6", "Normal progression"),
            ("v1.7", "v1.8", "Anomalous change"),
            ("v1.11", "v1.12", "Subtle change"),
            ("v1.14", "v1.15", "Performance regression"),
        ]

        for old_v, new_v, description in test_cases:
            logger.info(f"\n🔬 Testing: {description} ({old_v} → {new_v})")

            # Get enhanced analysis for success_rate
            old_metrics = mock_tracker.get_metrics_by_id(old_v)
            new_metrics = mock_tracker.get_metrics_by_id(new_v)

            enhanced = detector.get_statistical_regression_analysis(
                "success_rate", old_metrics["success_rate"], new_metrics["success_rate"]
            )

            stat_sig = enhanced.get("statistical_significance")
            if stat_sig:
                significance = stat_sig.get("significance", "unknown")
                within_ci = stat_sig.get("within_confidence_interval", True)
                logger.info(f"   Statistical Significance: {significance}")
                logger.info(f"   Within CI: {'✅' if within_ci else '❌'}")

            anomaly_status = enhanced.get("anomaly_status")
            if anomaly_status:
                is_anomaly = anomaly_status.get("is_anomaly", False)
                logger.info(f"   Anomaly: {'🚨 Yes' if is_anomaly else '✅ No'}")

        logger.info("\n🎉 Statistical Regression Detection Test Complete!")
        logger.info("=" * 60)

        # Summary of capabilities demonstrated
        logger.info("\n📋 Capabilities Demonstrated:")
        logger.info("✅ Trend analysis with linear regression")
        logger.info("✅ Anomaly detection (Z-score, IQR, pattern-based)")
        logger.info("✅ Statistical significance testing")
        logger.info("✅ Confidence interval analysis")
        logger.info("✅ Behavioral pattern recognition")
        logger.info("✅ Historical context analysis")
        logger.info("✅ Enhanced severity classification")


if __name__ == "__main__":
    asyncio.run(test_statistical_regression_detection())

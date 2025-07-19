"""Regression detection system for EVOSEAL evolution pipeline.

This module provides comprehensive regression detection capabilities including
performance regression, correctness regression, and configurable thresholds
for different types of metrics.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from .logging_system import get_logger
from .metrics_tracker import MetricsTracker

logger = get_logger(__name__)


class RegressionDetector:
    """Detects regressions in metrics between different versions.

    Provides comprehensive regression detection with configurable thresholds
    and severity classification for different types of metrics.
    """

    def __init__(self, config: Dict[str, Any], metrics_tracker: MetricsTracker):
        """Initialize the regression detector.

        Args:
            config: Configuration dictionary
            metrics_tracker: MetricsTracker instance for metrics comparison
        """
        self.config = config
        self.metrics_tracker = metrics_tracker

        # Regression threshold (default 5%)
        self.regression_threshold = config.get('regression_threshold', 0.05)

        # Metric-specific thresholds
        self.metric_thresholds = config.get(
            'metric_thresholds',
            {
                # Performance metrics (lower is better)
                'duration_sec': {'regression': 0.1, 'critical': 0.25},  # 10% / 25%
                'memory_mb': {'regression': 0.1, 'critical': 0.3},  # 10% / 30%
                'cpu_percent': {'regression': 0.1, 'critical': 0.3},  # 10% / 30%
                'execution_time': {'regression': 0.1, 'critical': 0.25},
                # Quality metrics (higher is better)
                'success_rate': {'regression': -0.05, 'critical': -0.1},  # 5% / 10%
                'accuracy': {'regression': -0.05, 'critical': -0.1},
                'precision': {'regression': -0.05, 'critical': -0.1},
                'recall': {'regression': -0.05, 'critical': -0.1},
                'f1_score': {'regression': -0.05, 'critical': -0.1},
                'pass_rate': {'regression': -0.05, 'critical': -0.1},
                'correctness': {'regression': -0.01, 'critical': -0.05},  # 1% / 5%
                # Error metrics (lower is better)
                'error_rate': {'regression': 0.05, 'critical': 0.1},
                'failure_rate': {'regression': 0.05, 'critical': 0.1},
            },
        )

        # Severity levels
        self.severity_levels = ['low', 'medium', 'high', 'critical']

        logger.info(f"RegressionDetector initialized with threshold: {self.regression_threshold}")

    def detect_regression(
        self, old_version_id: Union[str, int], new_version_id: Union[str, int]
    ) -> Tuple[bool, Dict[str, Any]]:
        """Detect if there's a regression in the new version.

        Args:
            old_version_id: ID of the baseline version
            new_version_id: ID of the new version to compare

        Returns:
            Tuple of (has_regression, regression_details)
        """
        try:
            # Get metrics comparison from MetricsTracker
            comparison = self.metrics_tracker.compare_metrics(old_version_id, new_version_id)
            if not comparison:
                logger.warning(
                    f"No comparison data available for versions {old_version_id} vs {new_version_id}"
                )
                return False, {}

            regressions = {}

            # Analyze each metric for regressions
            for metric_name, metric_data in comparison.items():
                if not isinstance(metric_data, dict):
                    continue

                regression_info = self._analyze_metric_regression(metric_name, metric_data)
                if regression_info:
                    regressions[metric_name] = regression_info

            has_regression = len(regressions) > 0

            if has_regression:
                logger.warning(
                    f"Regression detected between versions {old_version_id} and {new_version_id}"
                )
                for metric, info in regressions.items():
                    logger.warning(
                        f"  {metric}: {info['severity']} regression ({info['change']:.2%} change)"
                    )
            else:
                logger.info(
                    f"No regressions detected between versions {old_version_id} and {new_version_id}"
                )

            return has_regression, regressions

        except Exception as e:
            logger.error(f"Error detecting regression: {e}")
            return False, {'error': str(e)}

    def detect_regressions_batch(
        self, version_comparisons: List[Tuple[Union[str, int], Union[str, int]]]
    ) -> Dict[str, Tuple[bool, Dict[str, Any]]]:
        """Detect regressions for multiple version comparisons.

        Args:
            version_comparisons: List of (old_version_id, new_version_id) tuples

        Returns:
            Dictionary mapping comparison keys to regression results
        """
        results = {}

        for old_version, new_version in version_comparisons:
            comparison_key = f"{old_version}_vs_{new_version}"
            has_regression, regression_details = self.detect_regression(old_version, new_version)
            results[comparison_key] = (has_regression, regression_details)

        return results

    def get_regression_summary(self, regressions: Dict[str, Any]) -> Dict[str, Any]:
        """Get a summary of regression analysis.

        Args:
            regressions: Regression details from detect_regression

        Returns:
            Summary dictionary with counts and severity analysis
        """
        if not regressions:
            return {
                'total_regressions': 0,
                'severity_counts': {level: 0 for level in self.severity_levels},
                'critical_regressions': [],
                'recommendation': 'no_action',
            }

        severity_counts = {level: 0 for level in self.severity_levels}
        critical_regressions = []

        for metric_name, regression_info in regressions.items():
            severity = regression_info.get('severity', 'low')
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

            if severity == 'critical':
                critical_regressions.append(metric_name)

        # Determine recommendation
        if severity_counts['critical'] > 0:
            recommendation = 'rollback_required'
        elif severity_counts['high'] > 0:
            recommendation = 'review_required'
        elif severity_counts['medium'] > 2:
            recommendation = 'caution_advised'
        else:
            recommendation = 'monitor'

        return {
            'total_regressions': len(regressions),
            'severity_counts': severity_counts,
            'critical_regressions': critical_regressions,
            'recommendation': recommendation,
            'affected_metrics': list(regressions.keys()),
        }

    def is_critical_regression(self, regressions: Dict[str, Any]) -> bool:
        """Check if any regressions are critical.

        Args:
            regressions: Regression details from detect_regression

        Returns:
            True if any critical regressions are found
        """
        return any(regression.get('severity') == 'critical' for regression in regressions.values())

    def get_regression_threshold(self, metric_name: str) -> float:
        """Get the regression threshold for a specific metric.

        Args:
            metric_name: Name of the metric

        Returns:
            Regression threshold for the metric
        """
        if metric_name in self.metric_thresholds:
            return self.metric_thresholds[metric_name].get('regression', self.regression_threshold)
        return self.regression_threshold

    def update_thresholds(self, new_thresholds: Dict[str, Dict[str, float]]) -> None:
        """Update metric thresholds.

        Args:
            new_thresholds: Dictionary of new thresholds
        """
        self.metric_thresholds.update(new_thresholds)
        logger.info(f"Updated regression thresholds for {len(new_thresholds)} metrics")

    def _analyze_metric_regression(
        self, metric_name: str, metric_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Analyze a single metric for regression.

        Args:
            metric_name: Name of the metric
            metric_data: Metric comparison data

        Returns:
            Regression information or None if no regression
        """
        # Extract values from comparison data
        old_value = metric_data.get('baseline', metric_data.get('before'))
        new_value = metric_data.get('current', metric_data.get('after'))
        change_pct = metric_data.get('change_pct', metric_data.get('percent_change', 0))

        if old_value is None or new_value is None:
            return None

        # Convert percentage change to decimal if needed
        if abs(change_pct) > 1:
            change_pct = change_pct / 100.0

        # Get thresholds for this metric
        thresholds = self.metric_thresholds.get(metric_name, {})
        regression_threshold = thresholds.get('regression', self.regression_threshold)
        critical_threshold = thresholds.get('critical', regression_threshold * 2)

        # Determine if this is a regression based on metric type
        is_regression = False

        # Quality metrics (higher is better) - regression if decrease
        if metric_name in [
            'success_rate',
            'accuracy',
            'precision',
            'recall',
            'f1_score',
            'pass_rate',
            'correctness',
        ]:
            is_regression = change_pct < regression_threshold

        # Performance metrics (lower is better) - regression if increase
        elif metric_name in [
            'duration_sec',
            'memory_mb',
            'cpu_percent',
            'execution_time',
            'error_rate',
            'failure_rate',
        ]:
            is_regression = change_pct > abs(regression_threshold)

        # Default: use absolute threshold
        else:
            is_regression = abs(change_pct) > abs(regression_threshold)

        if not is_regression:
            return None

        # Determine severity
        severity = self._determine_severity(metric_name, change_pct, thresholds)

        return {
            'old_value': old_value,
            'new_value': new_value,
            'change': change_pct,
            'absolute_change': abs(new_value - old_value),
            'severity': severity,
            'threshold_used': regression_threshold,
            'critical_threshold': critical_threshold,
            'metric_type': self._get_metric_type(metric_name),
        }

    def _determine_severity(
        self, metric_name: str, change_pct: float, thresholds: Dict[str, float]
    ) -> str:
        """Determine the severity of a regression.

        Args:
            metric_name: Name of the metric
            change_pct: Percentage change (as decimal)
            thresholds: Thresholds for this metric

        Returns:
            Severity level string
        """
        critical_threshold = thresholds.get('critical', self.regression_threshold * 2)
        regression_threshold = thresholds.get('regression', self.regression_threshold)

        abs_change = abs(change_pct)
        abs_critical = abs(critical_threshold)
        abs_regression = abs(regression_threshold)

        if abs_change >= abs_critical:
            return 'critical'
        elif abs_change >= abs_regression * 2:
            return 'high'
        elif abs_change >= abs_regression * 1.5:
            return 'medium'
        else:
            return 'low'

    def _get_metric_type(self, metric_name: str) -> str:
        """Get the type of metric for categorization.

        Args:
            metric_name: Name of the metric

        Returns:
            Metric type string
        """
        if metric_name in [
            'success_rate',
            'accuracy',
            'precision',
            'recall',
            'f1_score',
            'pass_rate',
            'correctness',
        ]:
            return 'quality'
        elif metric_name in ['duration_sec', 'memory_mb', 'cpu_percent', 'execution_time']:
            return 'performance'
        elif metric_name in ['error_rate', 'failure_rate']:
            return 'reliability'
        else:
            return 'custom'

    def __str__(self) -> str:
        """String representation of the regression detector."""
        return (
            f"RegressionDetector("
            f"threshold={self.regression_threshold}, "
            f"metrics_tracked={len(self.metric_thresholds)})"
        )

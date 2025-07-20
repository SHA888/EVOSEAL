"""Regression detection system for EVOSEAL evolution pipeline.

This module provides comprehensive regression detection capabilities including
performance regression, correctness regression, and configurable thresholds
for different types of metrics.
"""

import json
import math
import statistics
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

from .events import EventType, publish
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

        # Baseline management
        self.baseline_storage_path = Path(config.get('baseline_storage_path', './baselines.json'))
        self.baselines: Dict[str, Dict[str, Any]] = {}
        self._load_baselines()

        # Alert system
        self.alert_callbacks: List[Callable[[Dict[str, Any]], None]] = []
        self.alert_enabled = config.get('alert_enabled', True)

        # Testing framework integration
        self.test_framework_integration = config.get('test_framework_integration', {})
        self.auto_baseline_update = config.get('auto_baseline_update', False)

        # Performance monitoring
        self.monitored_metrics = config.get(
            'monitored_metrics',
            [
                'success_rate',
                'accuracy',
                'duration_sec',
                'memory_mb',
                'error_rate',
                'pass_rate',
                'execution_time',
            ],
        )

        # Statistical analysis configuration
        self.statistical_config = config.get(
            'statistical_analysis',
            {
                'confidence_level': 0.95,  # 95% confidence intervals
                'min_samples': 3,  # Minimum samples for statistical analysis
                'trend_window': 10,  # Number of points for trend analysis
                'seasonal_period': 7,  # Period for seasonal adjustment (e.g., weekly)
                'outlier_threshold': 2.0,  # Standard deviations for outlier detection
                'enable_trend_analysis': True,
                'enable_anomaly_detection': True,
                'enable_seasonal_adjustment': False,
            },
        )

        # Historical data storage for statistical analysis
        self.historical_metrics: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=self.statistical_config['trend_window'] * 2)
        )

        # Anomaly detection configuration
        self.anomaly_config = config.get(
            'anomaly_detection',
            {
                'algorithms': ['zscore', 'iqr', 'isolation'],  # Available algorithms
                'sensitivity': 'medium',  # low, medium, high
                'adaptive_threshold': True,  # Adapt thresholds based on historical data
                'pattern_recognition': True,  # Enable behavioral pattern analysis
            },
        )

        logger.info(f"RegressionDetector initialized with threshold: {self.regression_threshold}")
        logger.info(
            f"Monitoring {len(self.monitored_metrics)} metrics with baselines: {len(self.baselines)}"
        )

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

                # Use enhanced statistical analysis if available
                if (
                    self.statistical_config['enable_trend_analysis']
                    or self.statistical_config['enable_anomaly_detection']
                ):

                    old_value = metric_data.get('baseline', metric_data.get('before', 0))
                    new_value = metric_data.get('current', metric_data.get('after', 0))

                    # Get enhanced statistical analysis
                    enhanced_analysis = self.get_statistical_regression_analysis(
                        metric_name, old_value, new_value
                    )

                    # Determine if it's a regression based on enhanced analysis
                    is_regression = False
                    severity = 'low'

                    # Check basic regression first
                    basic_regression = enhanced_analysis.get('basic_regression')
                    if basic_regression:
                        is_regression = True
                        severity = basic_regression.get('severity', 'low')

                    # Enhance severity based on statistical significance
                    stat_sig = enhanced_analysis.get('statistical_significance')
                    if stat_sig and not stat_sig.get('within_confidence_interval', True):
                        # Statistically significant regression
                        if severity == 'low':
                            severity = 'medium'
                        elif severity == 'medium':
                            severity = 'high'

                    # Check for anomalies
                    anomaly_status = enhanced_analysis.get('anomaly_status')
                    if anomaly_status and anomaly_status.get('is_anomaly', False):
                        # Anomalous behavior detected
                        anomaly_details = anomaly_status.get('anomaly_details', [])
                        critical_anomalies = [
                            a for a in anomaly_details if a.get('severity') == 'critical'
                        ]
                        if critical_anomalies:
                            severity = 'critical'
                        elif severity in ['low', 'medium']:
                            severity = 'high'

                    if is_regression or (
                        anomaly_status and anomaly_status.get('is_anomaly', False)
                    ):
                        regressions[metric_name] = {
                            **enhanced_analysis,
                            'severity': severity,
                            'change': metric_data.get('change_pct', 0),
                            'metric_type': self._get_metric_type(metric_name),
                        }
                else:
                    # Fall back to basic regression analysis
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

    def establish_baseline(
        self, version_id: Union[str, int], baseline_name: str = "default"
    ) -> bool:
        """Establish a baseline from a specific version's metrics.

        Args:
            version_id: ID of the version to use as baseline
            baseline_name: Name for this baseline (default: "default")

        Returns:
            True if baseline was successfully established
        """
        try:
            # Get metrics for this version
            metrics = self.metrics_tracker.get_metrics_by_id(version_id)
            if not metrics:
                logger.error(f"No metrics found for version {version_id}")
                return False

            # Create baseline entry
            baseline_data = {
                'version_id': str(version_id),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'metrics': metrics.to_dict() if hasattr(metrics, 'to_dict') else metrics,
                'monitored_metrics': self.monitored_metrics.copy(),
                'thresholds': self.metric_thresholds.copy(),
            }

            self.baselines[baseline_name] = baseline_data
            self._save_baselines()

            logger.info(f"Established baseline '{baseline_name}' from version {version_id}")

            # Publish baseline established event
            try:
                publish(
                    EventType.BASELINE_ESTABLISHED,
                    source="regression_detector",
                    baseline_name=baseline_name,
                    version_id=str(version_id),
                    metrics_count=len(baseline_data['metrics']),
                )
            except Exception as e:
                logger.warning(f"Failed to publish baseline established event: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to establish baseline '{baseline_name}': {e}")
            return False

    def get_baseline(self, baseline_name: str = "default") -> Optional[Dict[str, Any]]:
        """Get baseline data by name.

        Args:
            baseline_name: Name of the baseline to retrieve

        Returns:
            Baseline data dictionary or None if not found
        """
        return self.baselines.get(baseline_name)

    def list_baselines(self) -> List[Dict[str, Any]]:
        """List all available baselines.

        Returns:
            List of baseline information dictionaries
        """
        baseline_list = []
        for name, data in self.baselines.items():
            baseline_list.append(
                {
                    'name': name,
                    'version_id': data['version_id'],
                    'timestamp': data['timestamp'],
                    'metrics_count': len(data.get('metrics', {})),
                    'monitored_metrics': len(data.get('monitored_metrics', [])),
                }
            )
        return baseline_list

    def compare_against_baseline(
        self, version_id: Union[str, int], baseline_name: str = "default"
    ) -> Tuple[bool, Dict[str, Any]]:
        """Compare a version against an established baseline.

        Args:
            version_id: ID of the version to compare
            baseline_name: Name of the baseline to compare against

        Returns:
            Tuple of (has_regression, regression_details)
        """
        baseline = self.get_baseline(baseline_name)
        if not baseline:
            logger.error(f"Baseline '{baseline_name}' not found")
            return False, {'error': f"Baseline '{baseline_name}' not found"}

        baseline_version_id = baseline['version_id']
        logger.info(
            f"Comparing version {version_id} against baseline '{baseline_name}' (version {baseline_version_id})"
        )

        return self.detect_regression(baseline_version_id, version_id)

    def register_alert_callback(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        """Register a callback function to be called when regressions are detected.

        Args:
            callback: Function to call with regression details
        """
        self.alert_callbacks.append(callback)
        logger.info(f"Registered alert callback: {callback.__name__}")

    def trigger_alerts(self, regression_data: Dict[str, Any]) -> None:
        """Trigger all registered alert callbacks.

        Args:
            regression_data: Regression detection results
        """
        if not self.alert_enabled:
            return

        # Publish regression alert event
        try:
            publish(
                EventType.REGRESSION_ALERT,
                source="regression_detector",
                regression_count=len(regression_data),
                critical_regressions=self._get_critical_regressions(regression_data),
                affected_metrics=list(regression_data.keys()),
            )
        except Exception as e:
            logger.warning(f"Failed to publish regression alert event: {e}")

        # Call registered callbacks
        for callback in self.alert_callbacks:
            try:
                callback(regression_data)
            except Exception as e:
                logger.error(f"Error in alert callback {callback.__name__}: {e}")

    def integrate_with_test_framework(self, framework_name: str, config: Dict[str, Any]) -> bool:
        """Configure integration with a testing framework.

        Args:
            framework_name: Name of the testing framework (pytest, unittest, etc.)
            config: Framework-specific configuration

        Returns:
            True if integration was successful
        """
        try:
            self.test_framework_integration[framework_name] = config
            logger.info(f"Configured integration with {framework_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to integrate with {framework_name}: {e}")
            return False

    def run_regression_analysis(
        self,
        version_id: Union[str, int],
        baseline_name: str = "default",
        trigger_alerts: bool = True,
    ) -> Dict[str, Any]:
        """Run comprehensive regression analysis against a baseline.

        Args:
            version_id: ID of the version to analyze
            baseline_name: Name of the baseline to compare against
            trigger_alerts: Whether to trigger alerts if regressions are found

        Returns:
            Comprehensive analysis results
        """
        try:
            # Compare against baseline
            has_regression, regression_details = self.compare_against_baseline(
                version_id, baseline_name
            )

            # Get regression summary
            summary = self.get_regression_summary(regression_details)

            # Prepare analysis results
            analysis_results = {
                'version_id': str(version_id),
                'baseline_name': baseline_name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'has_regression': has_regression,
                'regression_details': regression_details,
                'summary': summary,
                'monitored_metrics': self.monitored_metrics,
                'thresholds_used': self.metric_thresholds,
            }

            # Trigger alerts if requested and regressions found
            if trigger_alerts and has_regression:
                self.trigger_alerts(regression_details)

            # Auto-update baseline if configured and no critical regressions
            if self.auto_baseline_update and not summary.get('critical_regressions'):
                logger.info(f"Auto-updating baseline '{baseline_name}' with version {version_id}")
                self.establish_baseline(version_id, baseline_name)

            return analysis_results

        except Exception as e:
            logger.error(f"Error in regression analysis: {e}")
            return {
                'version_id': str(version_id),
                'baseline_name': baseline_name,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'has_regression': False,
                'error': str(e),
            }

    def __str__(self) -> str:
        """String representation of the regression detector."""
        return (
            f"RegressionDetector("
            f"threshold={self.regression_threshold}, "
            f"metrics_tracked={len(self.metric_thresholds)})"
        )

    def analyze_metric_statistics(self, metric_name: str, values: List[float]) -> Dict[str, Any]:
        """Perform statistical analysis on metric values.

        Args:
            metric_name: Name of the metric
            values: List of metric values for analysis

        Returns:
            Statistical analysis results
        """
        if len(values) < self.statistical_config['min_samples']:
            return {'error': 'Insufficient samples for statistical analysis'}

        try:
            # Basic statistics
            mean_val = statistics.mean(values)
            median_val = statistics.median(values)
            std_dev = statistics.stdev(values) if len(values) > 1 else 0

            # Confidence interval calculation
            confidence_level = self.statistical_config['confidence_level']
            if len(values) > 1:
                # Using t-distribution for small samples
                import math

                n = len(values)
                # Approximation for t-critical value (95% confidence)
                t_critical = 1.96 if n > 30 else 2.0 + (0.5 / n)
                margin_error = t_critical * (std_dev / math.sqrt(n))
                confidence_interval = (mean_val - margin_error, mean_val + margin_error)
            else:
                confidence_interval = (mean_val, mean_val)

            # Trend analysis
            trend_analysis = (
                self._analyze_trend(values)
                if self.statistical_config['enable_trend_analysis']
                else {}
            )

            # Anomaly detection
            anomalies = (
                self._detect_anomalies(metric_name, values)
                if self.statistical_config['enable_anomaly_detection']
                else []
            )

            return {
                'mean': mean_val,
                'median': median_val,
                'std_dev': std_dev,
                'confidence_interval': confidence_interval,
                'confidence_level': confidence_level,
                'sample_size': len(values),
                'trend_analysis': trend_analysis,
                'anomalies': anomalies,
                'coefficient_of_variation': (std_dev / mean_val) if mean_val != 0 else 0,
            }

        except Exception as e:
            logger.error(f"Error in statistical analysis for {metric_name}: {e}")
            return {'error': str(e)}

    def _analyze_trend(self, values: List[float]) -> Dict[str, Any]:
        """Analyze trend in metric values using linear regression.

        Args:
            values: List of metric values

        Returns:
            Trend analysis results
        """
        if len(values) < 3:
            return {'trend': 'insufficient_data'}

        try:
            # Simple linear regression
            n = len(values)
            x = list(range(n))  # Time points
            y = values

            # Calculate slope (trend)
            x_mean = sum(x) / n
            y_mean = sum(y) / n

            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                slope = 0
            else:
                slope = numerator / denominator

            # Calculate correlation coefficient
            y_std = statistics.stdev(y) if len(y) > 1 else 0
            x_std = statistics.stdev(x) if len(x) > 1 else 0

            if x_std == 0 or y_std == 0:
                correlation = 0
            else:
                correlation = numerator / (
                    math.sqrt(sum((x[i] - x_mean) ** 2 for i in range(n)))
                    * math.sqrt(sum((y[i] - y_mean) ** 2 for i in range(n)))
                )

            # Determine trend direction and strength
            if abs(slope) < 0.01:  # Threshold for "no trend"
                trend_direction = 'stable'
            elif slope > 0:
                trend_direction = 'increasing'
            else:
                trend_direction = 'decreasing'

            # Trend strength based on correlation
            if abs(correlation) > 0.8:
                trend_strength = 'strong'
            elif abs(correlation) > 0.5:
                trend_strength = 'moderate'
            elif abs(correlation) > 0.3:
                trend_strength = 'weak'
            else:
                trend_strength = 'negligible'

            return {
                'slope': slope,
                'correlation': correlation,
                'direction': trend_direction,
                'strength': trend_strength,
                'r_squared': correlation**2,
                'predicted_next': y_mean + slope * n if slope != 0 else y_mean,
            }

        except Exception as e:
            logger.error(f"Error in trend analysis: {e}")
            return {'trend': 'error', 'error': str(e)}

    def _detect_anomalies(self, metric_name: str, values: List[float]) -> List[Dict[str, Any]]:
        """Detect anomalies in metric values using multiple algorithms.

        Args:
            metric_name: Name of the metric
            values: List of metric values

        Returns:
            List of detected anomalies
        """
        anomalies = []

        if len(values) < 3:
            return anomalies

        try:
            # Z-Score based anomaly detection
            if 'zscore' in self.anomaly_config['algorithms']:
                anomalies.extend(self._detect_zscore_anomalies(values))

            # IQR based anomaly detection
            if 'iqr' in self.anomaly_config['algorithms']:
                anomalies.extend(self._detect_iqr_anomalies(values))

            # Pattern-based anomaly detection
            if self.anomaly_config['pattern_recognition']:
                anomalies.extend(self._detect_pattern_anomalies(metric_name, values))

            return anomalies

        except Exception as e:
            logger.error(f"Error in anomaly detection for {metric_name}: {e}")
            return []

    def _detect_zscore_anomalies(self, values: List[float]) -> List[Dict[str, Any]]:
        """Detect anomalies using Z-score method."""
        if len(values) < 3:
            return []

        anomalies = []
        mean_val = statistics.mean(values)
        std_dev = statistics.stdev(values) if len(values) > 1 else 0

        if std_dev == 0:
            return anomalies

        threshold = self.statistical_config['outlier_threshold']

        for i, value in enumerate(values):
            z_score = abs(value - mean_val) / std_dev
            if z_score > threshold:
                anomalies.append(
                    {
                        'index': i,
                        'value': value,
                        'z_score': z_score,
                        'method': 'zscore',
                        'severity': 'high' if z_score > threshold * 1.5 else 'medium',
                    }
                )

        return anomalies

    def _detect_iqr_anomalies(self, values: List[float]) -> List[Dict[str, Any]]:
        """Detect anomalies using Interquartile Range (IQR) method."""
        if len(values) < 4:
            return []

        anomalies = []
        sorted_values = sorted(values)
        n = len(sorted_values)

        # Calculate quartiles
        q1_idx = n // 4
        q3_idx = 3 * n // 4
        q1 = sorted_values[q1_idx]
        q3 = sorted_values[q3_idx]
        iqr = q3 - q1

        if iqr == 0:
            return anomalies

        # Calculate bounds
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr

        for i, value in enumerate(values):
            if value < lower_bound or value > upper_bound:
                distance = min(abs(value - lower_bound), abs(value - upper_bound))
                anomalies.append(
                    {
                        'index': i,
                        'value': value,
                        'iqr_distance': distance,
                        'method': 'iqr',
                        'severity': 'high' if distance > iqr else 'medium',
                    }
                )

        return anomalies

    def _detect_pattern_anomalies(
        self, metric_name: str, values: List[float]
    ) -> List[Dict[str, Any]]:
        """Detect behavioral pattern anomalies."""
        anomalies = []

        if len(values) < 5:
            return anomalies

        try:
            # Detect sudden spikes or drops
            for i in range(1, len(values)):
                prev_val = values[i - 1]
                curr_val = values[i]

                if prev_val != 0:
                    change_pct = abs(curr_val - prev_val) / abs(prev_val)

                    # Configurable spike threshold based on sensitivity
                    sensitivity_thresholds = {
                        'low': 0.5,  # 50% change
                        'medium': 0.3,  # 30% change
                        'high': 0.15,  # 15% change
                    }

                    threshold = sensitivity_thresholds.get(self.anomaly_config['sensitivity'], 0.3)

                    if change_pct > threshold:
                        anomalies.append(
                            {
                                'index': i,
                                'value': curr_val,
                                'previous_value': prev_val,
                                'change_percent': change_pct,
                                'method': 'pattern_spike',
                                'severity': 'critical' if change_pct > threshold * 2 else 'high',
                            }
                        )

            return anomalies

        except Exception as e:
            logger.error(f"Error in pattern anomaly detection: {e}")
            return []

    def update_historical_metrics(self, version_id: str, metrics: Dict[str, Any]) -> None:
        """Update historical metrics for statistical analysis.

        Args:
            version_id: Version identifier
            metrics: Metrics data to add to history
        """
        try:
            timestamp = datetime.now(timezone.utc).isoformat()

            for metric_name, value in metrics.items():
                if metric_name in self.monitored_metrics and isinstance(value, (int, float)):
                    self.historical_metrics[metric_name].append(
                        {'version_id': version_id, 'value': float(value), 'timestamp': timestamp}
                    )

            logger.debug(f"Updated historical metrics for version {version_id}")

        except Exception as e:
            logger.error(f"Error updating historical metrics: {e}")

    def get_statistical_regression_analysis(
        self, metric_name: str, old_value: float, new_value: float
    ) -> Dict[str, Any]:
        """Enhanced regression analysis with statistical methods.

        Args:
            metric_name: Name of the metric
            old_value: Previous metric value
            new_value: New metric value

        Returns:
            Enhanced regression analysis with statistical insights
        """
        try:
            # Get historical data for this metric
            historical_data = list(self.historical_metrics.get(metric_name, []))
            historical_values = [item['value'] for item in historical_data]

            # Basic regression analysis
            basic_analysis = self._analyze_metric_regression(
                metric_name,
                {
                    'baseline': old_value,
                    'current': new_value,
                    'change_pct': (new_value - old_value) / old_value if old_value != 0 else 0,
                },
            )

            # Enhanced analysis with statistics
            enhanced_analysis = {
                'basic_regression': basic_analysis,
                'statistical_significance': None,
                'historical_context': None,
                'anomaly_status': None,
            }

            # Add statistical analysis if we have enough historical data
            if len(historical_values) >= self.statistical_config['min_samples']:
                # Add new value for analysis
                analysis_values = historical_values + [new_value]
                stats = self.analyze_metric_statistics(metric_name, analysis_values)

                enhanced_analysis['statistical_analysis'] = stats

                # Check if new value is within confidence interval
                if 'confidence_interval' in stats:
                    ci_lower, ci_upper = stats['confidence_interval']
                    is_within_ci = ci_lower <= new_value <= ci_upper
                    enhanced_analysis['statistical_significance'] = {
                        'within_confidence_interval': is_within_ci,
                        'confidence_level': stats['confidence_level'],
                        'significance': 'not_significant' if is_within_ci else 'significant',
                    }

                # Historical context
                if historical_values:
                    historical_mean = statistics.mean(historical_values)
                    enhanced_analysis['historical_context'] = {
                        'historical_mean': historical_mean,
                        'deviation_from_mean': new_value - historical_mean,
                        'percentile_rank': self._calculate_percentile_rank(
                            new_value, historical_values
                        ),
                    }

                # Check for anomalies
                if stats.get('anomalies'):
                    # Check if the new value (last in the list) is an anomaly
                    new_value_anomalies = [
                        a for a in stats['anomalies'] if a.get('index') == len(analysis_values) - 1
                    ]
                    enhanced_analysis['anomaly_status'] = {
                        'is_anomaly': len(new_value_anomalies) > 0,
                        'anomaly_details': new_value_anomalies,
                    }

            return enhanced_analysis

        except Exception as e:
            logger.error(f"Error in statistical regression analysis: {e}")
            return {'error': str(e)}

    def _calculate_percentile_rank(self, value: float, historical_values: List[float]) -> float:
        """Calculate percentile rank of a value in historical data."""
        if not historical_values:
            return 50.0

        sorted_values = sorted(historical_values)
        count_below = sum(1 for v in sorted_values if v < value)
        count_equal = sum(1 for v in sorted_values if v == value)

        percentile = (count_below + 0.5 * count_equal) / len(sorted_values) * 100
        return percentile

    def _load_baselines(self) -> None:
        """Load baselines from storage file."""
        if self.baseline_storage_path.exists():
            try:
                with open(self.baseline_storage_path, 'r', encoding='utf-8') as f:
                    self.baselines = json.load(f)
                logger.debug(
                    f"Loaded {len(self.baselines)} baselines from {self.baseline_storage_path}"
                )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load baselines: {e}")
                self.baselines = {}

    def _save_baselines(self) -> None:
        """Save baselines to storage file."""
        try:
            self.baseline_storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.baseline_storage_path, 'w', encoding='utf-8') as f:
                json.dump(self.baselines, f, indent=2, default=str)
        except OSError as e:
            logger.error(f"Failed to save baselines: {e}")

    def _get_critical_regressions(self, regression_data: Dict[str, Any]) -> List[str]:
        """Get list of metrics with critical regressions.

        Args:
            regression_data: Regression detection results

        Returns:
            List of metric names with critical regressions
        """
        critical = []
        for metric, info in regression_data.items():
            if isinstance(info, dict) and info.get('severity') == 'critical':
                critical.append(metric)
        return critical

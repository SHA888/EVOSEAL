"""
MetricsTracker class for tracking and comparing test metrics across test runs.
Provides functionality to store, analyze, and compare test execution metrics.
"""

import json
import statistics
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, TypedDict, Literal

import numpy as np
from rich.console import Console
from rich.table import Table

# Type aliases
TestResult = Dict[str, Any]
TestResults = List[TestResult]
MetricComparison = Dict[str, Dict[str, Union[float, str]]]

class TrendAnalysis(TypedDict):
    slope: float
    intercept: float
    pct_change: float
    trend: str

class ComparisonResult(TypedDict):
    baseline: float
    current: float
    difference: float
    change_pct: float
    direction: str
    significant: Optional[bool]
    effect_size: Optional[float]
    status: Optional[Literal['improvement', 'regression', 'neutral']]
    threshold_exceeded: Optional[bool]

# Default thresholds for different metrics
DEFAULT_THRESHOLDS = {
    'success_rate': {'regression': -1.0, 'improvement': 1.0},  # 1% change
    'duration_sec': {'regression': 0.1, 'improvement': -0.1},  # 10% change
    'memory_mb': {'regression': 0.1, 'improvement': -0.1},     # 10% change
    'cpu_percent': {'regression': 5.0, 'improvement': -5.0},   # 5% change
    'io_read_mb': {'regression': 0.1, 'improvement': -0.1},    # 10% change
    'io_write_mb': {'regression': 0.1, 'improvement': -0.1}    # 10% change
}

# Console for rich output
console = Console()


@dataclass
class TestMetrics:
    """Stores aggregated metrics for a test run."""
    
    test_type: str
    timestamp: str
    total_tests: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    tests_errors: int = 0
    success_rate: float = 0.0
    duration_sec: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def to_dict(self) -> Dict[str, Any]:
        """Convert metrics to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_test_result(cls, result: TestResult) -> 'TestMetrics':
        """Create TestMetrics from a test result dictionary."""
        resources = result.get('resources', {})
        
        return cls(
            test_type=result['test_type'],
            timestamp=result.get('timestamp', datetime.utcnow().isoformat()),
            total_tests=result.get('tests_run', 0),
            tests_passed=result.get('tests_passed', 0),
            tests_failed=result.get('tests_failed', 0),
            tests_skipped=result.get('tests_skipped', 0),
            tests_errors=result.get('tests_errors', 0),
            success_rate=(
                result['tests_passed'] / result['tests_run'] * 100 
                if result.get('tests_run', 0) > 0 else 0.0
            ),
            duration_sec=resources.get('duration_sec', 0.0),
            cpu_percent=resources.get('cpu_percent', 0.0),
            memory_mb=resources.get('memory_mb', 0.0),
            io_read_mb=resources.get('io_read_mb', 0.0),
            io_write_mb=resources.get('io_write_mb', 0.0),
            metadata=result.get('metadata', {})
        )


class MetricsTracker:
    """Tracks and compares test metrics across multiple test runs.
    
    Attributes:
        storage_path: Path to the metrics storage file
        metrics_history: List of all recorded test metrics
        thresholds: Dictionary of thresholds for different metrics
        significance_level: Alpha level for statistical tests (default: 0.05)
    """
    
    def __init__(
        self, 
        storage_path: Optional[Union[str, Path]] = None,
        thresholds: Optional[Dict[str, Dict[str, float]]] = None,
        significance_level: float = 0.05
    ):
        """Initialize the MetricsTracker.
        
        Args:
            storage_path: Path to store metrics history. If None, metrics are only kept in memory.
            thresholds: Dictionary of thresholds for different metrics. If None, uses DEFAULT_THRESHOLDS.
            significance_level: Alpha level for statistical tests (default: 0.05).
        """
        self.storage_path = Path(storage_path) if storage_path else None
        self.metrics_history: List[TestMetrics] = []
        self.thresholds = thresholds or DEFAULT_THRESHOLDS
        self.significance_level = significance_level
        
        # Load existing metrics if storage path exists
        if self.storage_path and self.storage_path.exists():
            self._load_metrics()
    
    def add_metrics(self, test_results: Union[TestResult, List[TestResult]]) -> None:
        """Add test results to the metrics history.
        
        Args:
            test_results: Single test result or list of test results to add
        """
        if not isinstance(test_results, list):
            test_results = [test_results]
        
        for result in test_results:
            metrics = TestMetrics.from_test_result(result)
            self.metrics_history.append(metrics)
        
        # Save metrics if storage path is configured
        if self.storage_path:
            self._save_metrics()
    
    def get_latest_metrics(self, test_type: Optional[str] = None) -> Optional[TestMetrics]:
        """Get the most recent metrics for a test type.
        
        Args:
            test_type: Type of test to filter by. If None, returns the most recent metrics of any type.
            
        Returns:
            Most recent TestMetrics or None if no matching metrics found
        """
        filtered = self._filter_metrics_by_type(test_type)
        return filtered[-1] if filtered else None
    
    def get_metrics_history(self, test_type: Optional[str] = None) -> List[TestMetrics]:
        """Get all metrics, optionally filtered by test type.
        
        Args:
            test_type: Type of test to filter by. If None, returns all metrics.
            
        Returns:
            List of matching TestMetrics, ordered by timestamp
        """
        return self._filter_metrics_by_type(test_type)
    
    def compare_metrics(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None
    ) -> Dict[str, ComparisonResult]:
        """Compare metrics between two test runs with statistical significance.
        
        Args:
            baseline_id: Index or timestamp of baseline metrics
            comparison_id: Index or timestamp of comparison metrics
            test_type: Type of test to compare
            
        Returns:
            Dictionary containing comparison results with statistical significance
        """
        baseline = self._get_metrics_by_id(baseline_id, test_type)
        comparison = self._get_metrics_by_id(comparison_id, test_type)
        
        if not baseline or not comparison:
            return {}
        
        return self._calculate_metrics_comparison(baseline, comparison)
        
    def find_regressions(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Find metrics that have regressed between two test runs.
        
        Args:
            baseline_id: Index or timestamp of baseline metrics
            comparison_id: Index or timestamp of comparison metrics
            test_type: Type of test to compare
            
        Returns:
            Dictionary of regressed metrics and their details
        """
        comparison = self.compare_metrics(baseline_id, comparison_id, test_type)
        return {
            k: v for k, v in comparison.items() 
            if v.get('status') == 'regression' and v.get('threshold_exceeded', False)
        }
        
    def find_improvements(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Find metrics that have improved between two test runs.
        
        Args:
            baseline_id: Index or timestamp of baseline metrics
            comparison_id: Index or timestamp of comparison metrics
            test_type: Type of test to compare
            
        Returns:
            Dictionary of improved metrics and their details
        """
        comparison = self.compare_metrics(baseline_id, comparison_id, test_type)
        return {
            k: v for k, v in comparison.items() 
            if v.get('status') == 'improvement' and v.get('threshold_exceeded', False)
        }
    
    def get_summary_statistics(
        self, 
        test_type: Optional[str] = None,
        limit: Optional[int] = None
    ) -> Dict[str, Dict[str, float]]:
        """Calculate summary statistics for metrics.
        
        Args:
            test_type: Type of test to filter by. If None, includes all test types.
            limit: Maximum number of recent test runs to include. If None, includes all.
            
        Returns:
            Dictionary of metric statistics (mean, median, min, max, std_dev)
        """
        metrics = self._filter_metrics_by_type(test_type)
        
        if limit:
            metrics = metrics[-limit:]
        
        if not metrics:
            return {}
        
        # Extract numeric metrics
        numeric_fields = [
            'success_rate', 'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb'
        ]
        
        stats = {}
        for field in numeric_fields:
            values = [getattr(m, field) for m in metrics]
            stats[field] = {
                'mean': float(np.mean(values)),
                'median': float(np.median(values)),
                'min': float(np.min(values)),
                'max': float(np.max(values)),
                'std_dev': float(np.std(values)) if len(values) > 1 else 0.0,
                'count': len(values)
            }
            
        return stats
    
    def display_comparison_table(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None,
        show_statistics: bool = True
    ) -> None:
        """Display a formatted table comparing two test runs with statistical insights.
        
        Args:
            baseline_id: Index or timestamp of baseline metrics
            comparison_id: Index or timestamp of comparison metrics
            test_type: Type of test to compare
            show_statistics: Whether to show statistical significance information
        """
        comparison = self.compare_metrics(baseline_id, comparison_id, test_type)
        
        if not comparison:
            console.print("[yellow]No comparison data available.[/yellow]")
            return
        
        # Create main comparison table
        table = Table(
            title=f"Test Metrics Comparison: {test_type or 'All Tests'}",
            show_header=True,
            header_style="bold magenta",
            box=None
        )
        
        # Add columns
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Baseline", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Difference", justify="right")
        table.add_column("Change", justify="right")
        if show_statistics:
            table.add_column("Significance", justify="center")
            table.add_column("Effect Size", justify="right")
        
        # Track regressions and improvements
        regressions = []
        improvements = []
        
        for metric, data in comparison.items():
            if metric in ['tests_total', 'tests_passed']:
                continue  # Skip test counts for now
                
            baseline = data.get('baseline', 0)
            current = data.get('current', 0)
            diff = data.get('difference', 0)
            change_pct = data.get('change_pct', 0)
            significant = data.get('significant', None)
            effect_size = data.get('effect_size', None)
            threshold_exceeded = data.get('threshold_exceeded', False)
            status = data.get('status', 'neutral')
            
            # Format values based on metric type
            if metric in ['success_rate', 'cpu_percent']:
                baseline_str = f"{baseline:.1f}%"
                current_str = f"{current:.1f}%"
                diff_str = f"{diff:+.1f}%"
                change_str = f"{change_pct:+.1f}%"
                effect_str = f"{effect_size:+.2f}" if effect_size is not None else "N/A"
            elif metric == 'duration_sec':
                baseline_str = f"{baseline:.2f}s"
                current_str = f"{current:.2f}s"
                diff_str = f"{diff:+.2f}s"
                change_str = f"{change_pct:+.1f}%"
                effect_str = f"{effect_size:+.2f}" if effect_size is not None else "N/A"
            else:  # Memory and I/O metrics
                baseline_str = f"{baseline:.2f} MB"
                current_str = f"{current:.2f} MB"
                diff_str = f"{diff:+.2f} MB"
                change_str = f"{change_pct:+.1f}%"
                effect_str = f"{effect_size:+.2f}" if effect_size is not None else "N/A"
            
            # Determine colors and symbols
            if metric in ['success_rate']:
                color = "green" if diff >= 0 else "red"
                symbol = "▲" if diff >= 0 else "▼"
            elif metric in ['duration_sec', 'memory_mb', 'io_read_mb', 'io_write_mb']:
                color = "green" if diff <= 0 else "red"
                symbol = "▼" if diff <= 0 else "▲"
            else:
                color = "white"
                symbol = ""
            
            # Add indicator for significant changes
            significance_str = ""
            if significant is not None:
                if significant:
                    significance_str = "✓" if status == 'improvement' else "✗" if status == 'regression' else "•"
                else:
                    significance_str = "•"
            
            # Add row to table
            row = [
                f"{metric.replace('_', ' ').title()}",
                baseline_str,
                current_str,
                diff_str,
                f"[{color}]{symbol} {change_str}{'!' if threshold_exceeded else ''}[/{color}]"
            ]
            
            if show_statistics:
                sig_style = "green" if status == 'improvement' else "red" if status == 'regression' else "white"
                row.extend([
                    f"[{sig_style}]{significance_str}[/{sig_style}]",
                    effect_str
                ])
            
            table.add_row(*row)
            
            # Track regressions and improvements
            if threshold_exceeded:
                if status == 'regression':
                    regressions.append(metric)
                elif status == 'improvement':
                    improvements.append(metric)
        
        # Print the table
        console.print(table)
        
        # Print summary
        if regressions or improvements:
            console.print("\n[bold]Summary:[/bold]")
            if regressions:
                console.print(f"[red]⚠️  Regressions: {', '.join(regressions)}[/red]")
            if improvements:
                console.print(f"[green]✅ Improvements: {', '.join(improvements)}[/green]")
        
        # Print legend
        if show_statistics:
            console.print("\n[dim]Legend: ✓ = significant improvement, ✗ = significant regression, • = not significant[/dim]")
    
    def _filter_metrics_by_type(self, test_type: Optional[str] = None) -> List[TestMetrics]:
        """Filter metrics by test type."""
        if test_type is None:
            return sorted(self.metrics_history, key=lambda x: x.timestamp)
        return sorted(
            [m for m in self.metrics_history if m.test_type == test_type],
            key=lambda x: x.timestamp
        )
    
    def _get_metrics_by_id(
        self, 
        metric_id: Union[int, str], 
        test_type: Optional[str] = None
    ) -> Optional[TestMetrics]:
        """Get metrics by index or timestamp."""
        metrics = self._filter_metrics_by_type(test_type)
        
        if not metrics:
            return None
        
        if isinstance(metric_id, int):
            # Handle negative indices (e.g., -1 for last item)
            if metric_id < 0 and abs(metric_id) <= len(metrics):
                return metrics[metric_id]
            elif 0 <= metric_id < len(metrics):
                return metrics[metric_id]
        else:
            # Try to find by timestamp
            for m in reversed(metrics):
                if m.timestamp.startswith(metric_id):
                    return m
        
        return None
    
    def _calculate_metrics_comparison(
        self,
        baseline: TestMetrics, 
        comparison: TestMetrics
    ) -> Dict[str, ComparisonResult]:
        """Calculate comparison metrics between two test runs with statistical significance.
        
        Args:
            baseline: Baseline metrics to compare against
            comparison: Current metrics to compare
            
        Returns:
            Dictionary containing comparison results with statistical significance
        """
        comparison_data: Dict[str, ComparisonResult] = {}
        
        # Get recent metrics for statistical testing
        recent_metrics = self._filter_metrics_by_type(baseline.test_type)
        recent_values: Dict[str, List[float]] = {
            'success_rate': [], 'duration_sec': [], 'cpu_percent': [],
            'memory_mb': [], 'io_read_mb': [], 'io_write_mb': []
        }
        
        # Collect recent values for each metric
        for metric in recent_metrics[-10:]:  # Use last 10 runs for statistics
            for field in recent_values:
                recent_values[field].append(getattr(metric, field, 0))
        
        # Numeric fields to compare
        numeric_fields = [
            'success_rate', 'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb'
        ]
        
        for field in numeric_fields:
            baseline_val = getattr(baseline, field, 0)
            current_val = getattr(comparison, field, 0)
            
            # Calculate difference and percentage change
            diff = current_val - baseline_val
            change_pct = (diff / baseline_val * 100) if baseline_val != 0 else 0.0
            
            # Check if the change exceeds thresholds
            threshold = self.thresholds.get(field, {})
            threshold_exceeded = False
            status = 'neutral'
            
            if diff > 0 and 'regression' in threshold and diff > threshold['regression'] * abs(baseline_val):
                threshold_exceeded = True
                status = 'regression' if field != 'success_rate' else 'improvement'
            elif diff < 0 and 'improvement' in threshold and abs(diff) > threshold['improvement'] * abs(baseline_val):
                threshold_exceeded = True
                status = 'improvement' if field != 'success_rate' else 'regression'
            
            # Calculate effect size (Cohen's d)
            effect_size = None
            significant = None
            
            if len(recent_values[field]) >= 2:
                from scipy import stats
                try:
                    # Perform t-test for statistical significance
                    t_stat, p_value = stats.ttest_ind(
                        recent_values[field], 
                        [current_val],
                        equal_var=False  # Welch's t-test (doesn't assume equal variance)
                    )
                    significant = p_value < self.significance_level
                    
                    # Calculate effect size (Cohen's d)
                    pooled_std = np.sqrt(
                        (np.var(recent_values[field], ddof=1) * (len(recent_values[field]) - 1) + 0) /
                        (len(recent_values[field]) + 1 - 2)
                    )
                    if pooled_std != 0:
                        effect_size = (current_val - np.mean(recent_values[field])) / pooled_std
                except (ValueError, RuntimeWarning):
                    # Handle cases where t-test can't be performed
                    pass
            
            comparison_data[field] = {
                'baseline': baseline_val,
                'current': current_val,
                'difference': diff,
                'change_pct': change_pct,
                'direction': 'increase' if diff >= 0 else 'decrease',
                'significant': significant,
                'effect_size': effect_size,
                'status': status,
                'threshold_exceeded': threshold_exceeded
            }
        
        # Add test count changes
        comparison_data['tests_total'] = {
            'baseline': baseline.total_tests,
            'current': comparison.total_tests,
            'difference': comparison.total_tests - baseline.total_tests,
            'change_pct': (
                (comparison.total_tests - baseline.total_tests) / baseline.total_tests * 100
                if baseline.total_tests > 0 else 0.0
            ),
            'direction': 'increase' if comparison.total_tests >= baseline.total_tests else 'decrease'
        }
        
        # Add pass/fail changes
        comparison_data['tests_passed'] = {
            'baseline': baseline.tests_passed,
            'current': comparison.tests_passed,
            'difference': comparison.tests_passed - baseline.tests_passed,
            'change_pct': (
                (comparison.tests_passed - baseline.tests_passed) / baseline.tests_passed * 100
                if baseline.tests_passed > 0 else 0.0
            ),
            'direction': 'increase' if comparison.tests_passed >= baseline.tests_passed else 'decrease'
        }
        
        return comparison_data
    
    def _save_metrics(self) -> None:
        """Save metrics history to disk."""
        if not self.storage_path:
            return
            
        # Ensure directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Convert metrics to dict and save as JSON
        metrics_data = [m.to_dict for m in self.metrics_history]
        
        with open(self.storage_path, 'w') as f:
            json.dump(metrics_data, f, indent=2)
    
    def get_percentiles(
        self,
        test_type: Optional[str] = None,
        percentiles: List[float] = [90, 95, 99],
        limit: Optional[int] = None
    ) -> Dict[str, Dict[float, float]]:
        """Calculate percentile values for metrics.
        
        Args:
            test_type: Type of test to filter by
            percentiles: List of percentiles to calculate (0-100)
            limit: Maximum number of recent test runs to include
            
        Returns:
            Dictionary mapping metrics to their percentile values
        """
        metrics = self._filter_metrics_by_type(test_type)
        
        if limit:
            metrics = metrics[-limit:]
        
        if not metrics:
            return {}
        
        # Extract numeric metrics
        numeric_fields = [
            'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb'
        ]
        
        # Calculate percentiles for each metric
        percentiles_dict = {}
        for field in numeric_fields:
            values = [getattr(m, field) for m in metrics]
            if not values:
                continue
                
            percentiles_dict[field] = {
                p: float(np.percentile(values, p))
                for p in percentiles
            }
        
        return percentiles_dict

    def normalize_metrics(
        self,
        metrics: TestMetrics,
        baseline: Optional[TestMetrics] = None
    ) -> Dict[str, float]:
        """Normalize metrics against a baseline.
        
        Args:
            metrics: Metrics to normalize
            baseline: Baseline metrics to normalize against. 
                     If None, uses the first available metrics as baseline.
                     
        Returns:
            Dictionary of normalized metrics
        """
        if baseline is None:
            baseline_metrics = self.get_metrics_history(test_type=metrics.test_type)
            baseline = baseline_metrics[0] if baseline_metrics else None
        
        if not baseline:
            return {}
        
        normalized = {}
        
        # Normalize numeric metrics
        numeric_fields = [
            'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb'
        ]
        
        for field in numeric_fields:
            base_val = getattr(baseline, field, 0)
            if base_val == 0:
                normalized[field] = 0.0
            else:
                normalized[field] = getattr(metrics, field, 0) / base_val
        
        # Success rate is already normalized (0-100)
        normalized['success_rate'] = metrics.success_rate / 100.0
        
        return normalized

    def detect_trends(
        self,
        test_type: Optional[str] = None,
        window_size: int = 5,
        threshold: float = 0.1
    ) -> Dict[str, TrendAnalysis]:
        """Detect trends in metrics over time.
        
        Args:
            test_type: Type of test to analyze
            window_size: Number of recent runs to consider
            threshold: Minimum change to consider significant (0-1)
            
        Returns:
            Dictionary of detected trends
        """
        metrics = self._filter_metrics_by_type(test_type)
        
        if len(metrics) < 2:
            return {}
        
        # Take the most recent runs
        metrics = metrics[-window_size:]
        
        # Calculate trends for each metric
        trends = {}
        numeric_fields = [
            'success_rate', 'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb'
        ]
        
        for field in numeric_fields:
            values = [getattr(m, field, 0) for m in metrics]
            if not values:
                continue
                
            # Simple linear regression for trend detection
            x = np.arange(len(values))
            slope, intercept = np.polyfit(x, values, 1)
            
            # Calculate percentage change over the window
            if values[0] != 0:
                pct_change = (values[-1] - values[0]) / abs(values[0])
            else:
                pct_change = 0.0
                
            trends[field] = {
                'slope': float(slope),
                'intercept': float(intercept),
                'pct_change': float(pct_change),
                'trend': 'increasing' if abs(slope) > threshold and slope > 0 
                        else 'decreasing' if abs(slope) > threshold and slope < 0
                        else 'stable'
            }
        
        return trends

    def _load_metrics(self) -> None:
        """Load metrics history from disk."""
        if not self.storage_path or not self.storage_path.exists():
            return
            
        try:
            with open(self.storage_path, 'r') as f:
                metrics_data = json.load(f)
                
            self.metrics_history = [
                TestMetrics(
                    test_type=m.get('test_type', 'unknown'),
                    timestamp=m.get('timestamp', datetime.utcnow().isoformat()),
                    total_tests=m.get('total_tests', 0),
                    tests_passed=m.get('tests_passed', 0),
                    tests_failed=m.get('tests_failed', 0),
                    tests_skipped=m.get('tests_skipped', 0),
                    tests_errors=m.get('tests_errors', 0),
                    success_rate=m.get('success_rate', 0.0),
                    duration_sec=m.get('duration_sec', 0.0),
                    cpu_percent=m.get('cpu_percent', 0.0),
                    memory_mb=m.get('memory_mb', 0.0),
                    io_read_mb=m.get('io_read_mb', 0.0),
                    io_write_mb=m.get('io_write_mb', 0.0),
                    metadata=m.get('metadata', {})
                )
                for m in metrics_data
            ]
        except (json.JSONDecodeError, OSError) as e:
            console.print(f"[red]Error loading metrics: {e}[/red]")
            self.metrics_history = []


# Example usage
if __name__ == "__main__":
    # Example test results
    test_results = [
        {
            "test_type": "unit",
            "success": True,
            "exit_code": 0,
            "output": "2 passed in 0.12s",
            "timestamp": "2023-06-15T10:00:00Z",
            "resources": {
                "cpu_percent": 45.2,
                "memory_mb": 128.5,
                "io_read_mb": 10.2,
                "io_write_mb": 2.1,
                "duration_sec": 0.12
            },
            "tests_run": 2,
            "tests_passed": 2,
            "tests_failed": 0,
            "tests_skipped": 0,
            "tests_errors": 0,
            "test_duration": 0.12
        },
        {
            "test_type": "unit",
            "success": True,
            "exit_code": 0,
            "output": "3 passed in 0.15s",
            "timestamp": "2023-06-15T11:00:00Z",
            "resources": {
                "cpu_percent": 42.8,
                "memory_mb": 130.1,
                "io_read_mb": 12.5,
                "io_write_mb": 2.3,
                "duration_sec": 0.15
            },
            "tests_run": 3,
            "tests_passed": 3,
            "tests_failed": 0,
            "tests_skipped": 0,
            "tests_errors": 0,
            "test_duration": 0.15
        }
    ]
    
    # Create a metrics tracker
    tracker = MetricsTracker("test_metrics.json")
    
    # Add test results
    tracker.add_metrics(test_results)
    
    # Display comparison between the two test runs
    tracker.display_comparison_table(0, 1, "unit")

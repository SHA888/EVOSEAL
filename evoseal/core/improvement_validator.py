"""
ImprovementValidator class for validating code improvements based on test metrics.
Provides functionality to determine if code changes represent a genuine improvement
by analyzing test results and performance metrics.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, TypedDict, Literal
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from pathlib import Path
from datetime import datetime
import json
import numpy as np

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import track
from rich.text import Text

from evoseal.core.metrics_tracker import MetricsTracker, TestMetrics

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from evoseal.core.metrics_tracker import MetricsTracker, TestMetrics

# Type aliases
ValidationResult = Dict[str, Any]
ValidationResults = List[ValidationResult]

# Console for rich output
console = Console()


class ImprovementDirection(Enum):
    """Direction of improvement for a metric."""
    INCREASE = auto()  # Higher values are better (e.g., success rate)
    DECREASE = auto()  # Lower values are better (e.g., duration, memory usage)
    NO_CHANGE = auto()  # Values should remain the same


@dataclass
class ValidationRule:
    """Defines a rule for validating test metrics with statistical significance.
    
    Attributes:
        name: Unique identifier for the rule
        description: Human-readable description
        metric: Name of the metric to validate
        direction: Expected direction of improvement
        threshold: Minimum required improvement (percentage)
        required: If True, failure causes overall validation to fail
        weight: Weight of this rule in the overall score
        min_effect_size: Minimum effect size to consider the improvement meaningful
        confidence_level: Confidence level for statistical tests (0-1)
    """
    
    def __init__(
        self,
        name: str,
        description: str,
        metric: str,
        direction: 'ImprovementDirection',
        threshold: float = 0.0,
        required: bool = True,
        weight: float = 1.0,
        min_effect_size: Optional[float] = None,
        confidence_level: float = 0.95
    ):
        self.name = name
        self.description = description
        self.metric = metric
        self.direction = direction
        self.threshold = threshold
        self.required = required
        self.weight = weight
        self.min_effect_size = min_effect_size
        self.confidence_level = confidence_level
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert rule to dictionary for serialization."""
        return {
            'name': self.name,
            'description': self.description,
            'metric': self.metric,
            'direction': self.direction.name,
            'threshold': self.threshold,
            'required': self.required,
            'weight': self.weight,
            'min_effect_size': self.min_effect_size,
            'confidence_level': self.confidence_level
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationRule':
        """Create a ValidationRule from a dictionary."""
        return cls(
            name=data['name'],
            description=data['description'],
            metric=data['metric'],
            direction=ImprovementDirection[data['direction']],
            threshold=data.get('threshold', 0.0),
            required=data.get('required', True),
            weight=data.get('weight', 1.0),
            min_effect_size=data.get('min_effect_size'),
            confidence_level=data.get('confidence_level', 0.95)
        )
    
    def validate(
        self, 
        baseline: float, 
        current: float, 
        baseline_std: Optional[float] = None,
        current_std: Optional[float] = None,
        sample_size: int = 1
    ) -> Dict[str, Any]:
        """Validate if the metric change meets the improvement criteria with statistical significance.
        
        Args:
            baseline: Baseline metric value
            current: Current metric value
            baseline_std: Standard deviation of baseline metric (for statistical tests)
            current_std: Standard deviation of current metric (for statistical tests)
            sample_size: Number of samples used for the metric
            
        Returns:
            Dictionary containing validation results with statistical significance
        """
        result = {
            'is_valid': False,
            'improvement_pct': 0.0,
            'effect_size': None,
            'is_significant': False,
            'confidence_interval': None,
            'p_value': None,
            'meets_effect_size': True,
            'baseline_value': baseline,
            'current_value': current
        }
        
        if baseline == 0:
            result['is_valid'] = not self.required
            return result
            
        # Calculate percentage improvement
        improvement_pct = ((current - baseline) / baseline) * 100
        result['improvement_pct'] = improvement_pct
        
        # Check if the change meets the threshold
        if self.direction == ImprovementDirection.INCREASE:
            is_valid = improvement_pct >= self.threshold
        elif self.direction == ImprovementDirection.DECREASE:
            is_valid = improvement_pct <= -self.threshold
        else:  # NO_CHANGE
            is_valid = abs(improvement_pct) <= self.threshold
        
        result['is_valid'] = is_valid
        
        # Calculate effect size if we have standard deviations
        if baseline_std is not None and current_std is not None and sample_size > 1:
            try:
                from scipy import stats
                
                # Calculate pooled standard deviation
                n1 = n2 = sample_size
                pooled_std = np.sqrt(((n1-1)*baseline_std**2 + (n2-1)*current_std**2) / (n1 + n2 - 2))
                
                # Calculate Cohen's d effect size
                if pooled_std > 0:
                    effect_size = (current - baseline) / pooled_std
                    result['effect_size'] = effect_size
                    result['meets_effect_size'] = (
                        self.min_effect_size is None or 
                        (self.direction == ImprovementDirection.INCREASE and effect_size >= self.min_effect_size) or
                        (self.direction == ImprovementDirection.DECREASE and effect_size <= -self.min_effect_size) or
                        (self.direction == ImprovementDirection.NO_CHANGE and abs(effect_size) <= abs(self.min_effect_size))
                    )
                
                # Perform t-test if we have enough data
                if n1 > 1 and n2 > 1:
                    t_stat, p_value = stats.ttest_ind_from_stats(
                        mean1=baseline, std1=baseline_std, nobs1=n1,
                        mean2=current, std2=current_std, nobs2=n2,
                        equal_var=False  # Welch's t-test
                    )
                    result['p_value'] = p_value
                    result['is_significant'] = p_value <= (1 - self.confidence_level)
                    
                    # Calculate confidence interval
                    se = np.sqrt((baseline_std**2 / n1) + (current_std**2 / n2))
                    t_crit = stats.t.ppf((1 + self.confidence_level) / 2, df=min(n1, n2) - 1)
                    margin = t_crit * se
                    result['confidence_interval'] = (
                        (current - baseline) - margin,
                        (current - baseline) + margin
                    )
            except (ImportError, ValueError, RuntimeError) as e:
                # If scipy is not available or calculation fails, continue without stats
                pass
        
        return result


class ImprovementValidator:
    """Validates if code changes represent a genuine improvement based on test metrics.
    
    This class provides statistical validation of improvements by comparing metrics
    between different test runs and applying configurable validation rules with
    support for statistical significance testing and effect size analysis.
    
    Attributes:
        metrics_tracker: MetricsTracker instance for accessing test metrics
        rules: List of validation rules to apply
        min_improvement_score: Minimum score (0-100) to consider changes an improvement
        confidence_level: Default confidence level for statistical tests (0-1)
    """
    
    # Default validation rules
    DEFAULT_RULES = [
        # Success rate should not decrease by more than 5%
        ValidationRule(
            name="success_rate_stable",
            description="Test success rate should not decrease significantly",
            metric="success_rate",
            direction=ImprovementDirection.INCREASE,
            threshold=-5.0,  # Allow up to 5% decrease
            required=True,
            weight=2.0,
        ),
        # Performance should not degrade by more than 10%
        ValidationRule(
            name="performance_improved",
            description="Test execution time should not increase significantly",
            metric="duration_sec",
            direction=ImprovementDirection.DECREASE,
            threshold=-10.0,  # Allow up to 10% increase
            required=True,
            weight=1.5,
        ),
        # Memory usage should not increase by more than 10%
        ValidationRule(
            name="memory_usage_stable",
            description="Memory usage should not increase significantly",
            metric="memory_mb",
            direction=ImprovementDirection.DECREASE,
            threshold=-10.0,  # Allow up to 10% increase
            required=False,
            weight=1.0,
        ),
        # No new test failures
        ValidationRule(
            name="no_new_failures",
            description="No new test failures should be introduced",
            metric="tests_failed",
            direction=ImprovementDirection.DECREASE,
            threshold=0.0,  # No increase allowed
            required=True,
            weight=2.0,
        ),
    ]
    
    def __init__(
        self, 
        metrics_tracker: MetricsTracker,
        rules: Optional[List[ValidationRule]] = None,
        min_improvement_score: float = 70.0,
        confidence_level: float = 0.95
    ) -> None:
        """Initialize the ImprovementValidator.
        
        Args:
            metrics_tracker: MetricsTracker instance for accessing test metrics
            rules: List of validation rules. If None, uses DEFAULT_RULES.
            min_improvement_score: Minimum score (0-100) to consider changes an improvement.
            confidence_level: Confidence level (0-1) for statistical tests.
        """
        self.metrics_tracker = metrics_tracker
        self.rules = rules or list(self.DEFAULT_RULES)
        self.min_improvement_score = min_improvement_score
        self.confidence_level = confidence_level
        
        # Set confidence level for all rules if not explicitly set
        for rule in self.rules:
            if not hasattr(rule, 'confidence_level') or rule.confidence_level is None:
                rule.confidence_level = confidence_level
    
    def validate_improvement(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None,
        sample_size: int = 1
    ) -> Dict[str, Any]:
        """Validate if the comparison metrics represent an improvement over baseline.
        
        Args:
            baseline_id: ID or timestamp of baseline metrics
            comparison_id: ID or timestamp of comparison metrics
            test_type: Type of test to validate. If None, validates all test types.
            sample_size: Number of samples used for calculating statistical significance
            
        Returns:
            Dictionary containing validation results with statistical analysis
        """
        # Get the metrics for comparison
        baseline_metrics = self.metrics_tracker.get_metrics_by_id(baseline_id, test_type)
        comparison_metrics = self.metrics_tracker.get_metrics_by_id(comparison_id, test_type)
        
        if not baseline_metrics or not comparison_metrics:
            return {
                "is_improvement": False,
                "score": 0.0,
                "confidence_level": self.confidence_level,
                "message": "Could not find metrics for the specified IDs",
                "details": [],
                "all_required_passed": False,
                "has_statistical_significance": False,
                "baseline_id": str(baseline_id),
                "comparison_id": str(comparison_id),
                "test_type": test_type,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Get historical data for statistical analysis
        historical_metrics = self.metrics_tracker._filter_metrics_by_type(test_type)
        baseline_std = self._calculate_metric_std(historical_metrics, baseline_metrics)
        current_std = self._calculate_metric_std(historical_metrics, comparison_metrics)
        
        # Apply validation rules
        results = []
        total_weight = 0.0
        weighted_score = 0.0
        all_required_passed = True
        has_statistical_significance = True
        
        for rule in self.rules:
            baseline_val = getattr(baseline_metrics, rule.metric, 0)
            current_val = getattr(comparison_metrics, rule.metric, 0)
            
            # Get standard deviation for this specific metric if available
            rule_baseline_std = baseline_std.get(rule.metric) if baseline_std else None
            rule_current_std = current_std.get(rule.metric) if current_std else None
            
            # Validate with statistical significance
            rule_result = rule.validate(
                baseline=baseline_val,
                current=current_val,
                baseline_std=rule_baseline_std,
                current_std=rule_current_std,
                sample_size=sample_size
            )
            
            # Calculate score based on improvement and statistical significance
            score = self._calculate_rule_score(rule, rule_result)
            
            # Apply rule weight
            rule_score = score * rule.weight
            weighted_score += rule_score
            total_weight += rule.weight
            
            # Track if any required rules failed
            rule_passed = rule_result['is_valid'] and \
                        (not rule_result.get('is_significant') or rule_result['is_significant']) and \
                        rule_result.get('meets_effect_size', True)
                        
            if rule.required and not rule_passed:
                all_required_passed = False
                
            if rule.required and not rule_result.get('is_significant', True):
                has_statistical_significance = False
            
            # Prepare detailed result
            result = {
                "rule": rule.name,
                "description": rule.description,
                "metric": rule.metric,
                "direction": rule.direction.name.lower(),
                "required": rule.required,
                "weight": rule.weight,
                "baseline_value": baseline_val,
                "current_value": current_val,
                "improvement_pct": rule_result['improvement_pct'],
                "score": score,
                "weighted_score": rule_score,
                "passed": rule_passed,
                "threshold": rule.threshold,
                "min_effect_size": getattr(rule, 'min_effect_size', None),
                "effect_size": rule_result.get('effect_size'),
                "is_significant": rule_result.get('is_significant', None),
                "confidence_interval": rule_result.get('confidence_interval'),
                "p_value": rule_result.get('p_value'),
                "meets_effect_size": rule_result.get('meets_effect_size', True),
                "baseline_std": rule_baseline_std,
                "current_std": rule_current_std
            }
            results.append(result)
        
        # Calculate overall score
        overall_score = (weighted_score / total_weight) if total_weight > 0 else 0.0
        
        # Determine if this is a valid improvement
        is_improvement = all_required_passed and \
                        (overall_score >= self.min_improvement_score) and \
                        has_statistical_significance
        
        # Prepare the final result
        validation_result = {
            "is_improvement": is_improvement,
            "score": overall_score,
            "required_passed": all_required_passed,
            "message": message,
            "baseline_id": baseline_id,
            "comparison_id": comparison_id,
            "test_type": test_type,
            "details": results,
            "timestamp": datetime.utcnow().isoformat(),
        }
    
    def display_validation_results(self, validation_result: ValidationResult) -> None:
        """Display validation results in a formatted table.
        
        Args:
            validation_result: Result from validate_improvement()
        """
        # Display summary
        console.print("\n[bold]Improvement Validation Results[/bold]")
        console.print(f"Status: {'[green]PASSED[/green]' if validation_result['is_improvement'] else '[red]FAILED[/red]'}")
        console.print(f"Score: {validation_result['score']:.1f}/100")
        console.print(validation_result['message'])
        
        # Display detailed results in a table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Rule", style="cyan")
        table.add_column("Metric", style="yellow")
        table.add_column("Baseline", justify="right")
        table.add_column("Current", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Status", justify="center")
        table.add_column("Score", justify="right")
        
        for detail in validation_result['details']:
            # Format change value with sign
            change_pct = detail['improvement_pct']
            change_str = f"{change_pct:+.1f}%"
            
            # Format status with color
            if detail['is_valid']:
                status = "[green]PASS[/green]"
            elif not detail['required']:
                status = "[yellow]WARN[/yellow]"
            else:
                status = "[red]FAIL[/red]"
            
            # Add row to table
            table.add_row(
                detail['rule'],
                detail['metric'],
                str(detail['baseline']),
                str(detail['current']),
                change_str,
                status,
                f"{detail['score']:.1f}"
            )
        
        console.print("\n[bold]Detailed Validation Results[/bold]")
        console.print(table)
        
        # Display final verdict
        console.print("\n[bold]Verdict:[/bold]", end=" ")
        if validation_result['is_improvement']:
            console.print("[green]✅ These changes represent a valid improvement.[/green]")
        else:
            console.print("[red]❌ These changes do not meet the improvement criteria.[/red]")
    
    def save_validation_results(
        self, 
        validation_result: ValidationResult, 
        output_path: Union[str, Path]
    ) -> None:
        """Save validation results to a JSON file.
        
        Args:
            validation_result: Result from validate_improvement()
            output_path: Path to save the results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(validation_result, f, indent=2)
        
        console.print(f"\n[green]Validation results saved to: {output_path}[/green]")


    def _calculate_metric_std(
        self, 
        historical_metrics: List[TestMetrics], 
        current_metric: TestMetrics
    ) -> Dict[str, float]:
        """Calculate standard deviation for each metric from historical data.
        
        Args:
            historical_metrics: List of historical metrics
            current_metric: Current metric to calculate std for
            
        Returns:
            Dictionary mapping metric names to their standard deviations
        """
        if not historical_metrics or len(historical_metrics) < 2:
            return {}
            
        # Get all numeric fields from the metrics
        numeric_fields = [
            'success_rate', 'duration_sec', 'cpu_percent', 
            'memory_mb', 'io_read_mb', 'io_write_mb',
            'tests_passed', 'tests_failed', 'tests_skipped', 'tests_errors'
        ]
        
        std_values = {}
        for field in numeric_fields:
            values = [getattr(m, field, 0) for m in historical_metrics if hasattr(m, field)]
            if len(values) >= 2:  # Need at least 2 values to calculate std
                std_values[field] = float(np.std(values, ddof=1))  # Sample standard deviation
                
        return std_values
    
    def _calculate_rule_score(
        self, 
        rule: ValidationRule, 
        result: Dict[str, Any]
    ) -> float:
        """Calculate a score (0-100) for a validation rule result.
        
        Args:
            rule: The validation rule
            result: The validation result from rule.validate()
            
        Returns:
            Score between 0 and 100
        """
        improvement_pct = result['improvement_pct']
        is_significant = result.get('is_significant', True)  # Assume significant if not calculated
        meets_effect_size = result.get('meets_effect_size', True)  # Assume met if not calculated
        
        # Base score based on improvement percentage
        if rule.direction == ImprovementDirection.INCREASE:
            # For INCREASE metrics, higher improvement is better
            base_score = min(100, max(0, 50 + (improvement_pct / 2)))
        elif rule.direction == ImprovementDirection.DECREASE:
            # For DECREASE metrics, more negative improvement is better
            base_score = min(100, max(0, 50 - (improvement_pct / 2)))
        else:  # NO_CHANGE
            # For NO_CHANGE, score is based on how close to zero the change is
            base_score = 100 - min(100, abs(improvement_pct) * 2)
        
        # Apply penalties for statistical issues
        score = base_score
        
        # Penalty for not meeting effect size
        if not meets_effect_size and rule.min_effect_size is not None:
            score *= 0.7  # 30% penalty
            
        # Penalty for lack of statistical significance
        if not is_significant and hasattr(rule, 'confidence_level'):
            score *= 0.8  # 20% penalty
        
        return max(0, min(100, score))
    
    def save_validation_report(
        self,
        validation_result: Dict[str, Any],
        output_path: Union[str, Path],
        format: str = 'json',
        include_details: bool = True
    ) -> None:
        """Save validation results to a file.
        
        Args:
            validation_result: Result from validate_improvement()
            output_path: Path to save the report
            format: Output format ('json' or 'txt')
            include_details: Whether to include detailed rule results
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create a simplified result for saving
        result_to_save = {
            'is_improvement': validation_result['is_improvement'],
            'score': validation_result['score'],
            'confidence_level': validation_result.get('confidence_level', 0.95),
            'passed_required': validation_result['passed_required'],
            'has_statistical_significance': validation_result.get('has_statistical_significance', True),
            'meets_score_threshold': validation_result['meets_score_threshold'],
            'message': validation_result.get('message', ''),
            'baseline_id': validation_result['baseline_id'],
            'comparison_id': validation_result['comparison_id'],
            'test_type': validation_result['test_type'],
            'timestamp': validation_result['timestamp'],
            'rules_applied': validation_result.get('rules_applied', []),
            'metrics_compared': validation_result.get('metrics_compared', [])
        }
        
        if include_details:
            result_to_save['details'] = validation_result.get('details', [])
        
        if format.lower() == 'json':
            with open(output_path, 'w') as f:
                json.dump(result_to_save, f, indent=2)
        else:  # txt format
            with open(output_path, 'w') as f:
                f.write(f"Validation Report\n{'='*80}\n")
                f.write(f"Result: {'PASSED' if result_to_save['is_improvement'] else 'FAILED'}\n")
                f.write(f"Score: {result_to_save['score']:.1f}/100 (Threshold: {self.min_improvement_score})\n")
                f.write(f"Confidence Level: {result_to_save['confidence_level']*100:.0f}%\n")
                f.write(f"Statistical Significance: {'Yes' if result_to_save.get('has_statistical_significance', True) else 'No'}\n")
                f.write(f"All Required Rules Passed: {'Yes' if result_to_save['passed_required'] else 'No'}\n")
                f.write(f"Baseline: {result_to_save['baseline_id']}\n")
                f.write(f"Comparison: {result_to_save['comparison_id']}\n")
                if result_to_save['test_type']:
                    f.write(f"Test Type: {result_to_save['test_type']}\n")
                f.write(f"Timestamp: {result_to_save['timestamp']}\n\n")
                
                if include_details and 'details' in result_to_save:
                    f.write("Detailed Results:\n")
                    for detail in result_to_save['details']:
                        f.write(f"\nRule: {detail['rule']} ({'Required' if detail['required'] else 'Optional'})")
                        f.write(f"\n  Description: {detail['description']}")
                        f.write(f"\n  Metric: {detail['metric']} (Direction: {detail['direction']})")
                        f.write(f"\n  Baseline: {detail['baseline_value']:.2f} ± {detail.get('baseline_std', 0):.2f}")
                        f.write(f"\n  Current: {detail['current_value']:.2f} ± {detail.get('current_std', 0):.2f}")
                        f.write(f"\n  Improvement: {detail['improvement_pct']:+.2f}%")
                        if 'effect_size' in detail and detail['effect_size'] is not None:
                            f.write(f" (Effect Size: {detail['effect_size']:.2f})")
                        if 'p_value' in detail and detail['p_value'] is not None:
                            f.write(f"\n  p-value: {detail['p_value']:.4f} (Significant: {'Yes' if detail.get('is_significant') else 'No'})")
                        if 'confidence_interval' in detail and detail['confidence_interval']:
                            ci = detail['confidence_interval']
                            f.write(f"\n  {self.confidence_level*100:.0f}% CI: [{ci[0]:.2f}, {ci[1]:.2f}]")
                        f.write(f"\n  Score: {detail['score']:.1f}/100 (Weight: {detail['weight']}x)")
                        f.write(f"\n  Status: {'PASS' if detail['passed'] else 'FAIL'}\n")

    def get_validation_summary_table(self, validation_result: Dict[str, Any]) -> Table:
        """Create a rich Table with a summary of validation results.
        
        Args:
            validation_result: Result from validate_improvement()
            
        Returns:
            A rich Table object ready for display
        """
        from rich import box
        
        # Create summary table
        summary_table = Table(
            title="Improvement Validation Summary",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold magenta",
            expand=True
        )
        
        # Add columns
        summary_table.add_column("Metric", style="cyan", no_wrap=True)
        summary_table.add_column("Value", justify="right")
        
        # Add rows
        summary_table.add_row("Overall Result", 
                            "[green]PASSED[/green]" if validation_result['is_improvement'] else "[red]FAILED[/red]")
        summary_table.add_row("Score", f"{validation_result['score']:.1f}/100")
        summary_table.add_row("Required Rules Passed", 
                            "[green]Yes[/green]" if validation_result['passed_required'] else "[red]No[/red]")
        summary_table.add_row("Statistical Significance", 
                            "[green]Yes[/green]" if validation_result.get('has_statistical_significance', True) else "[yellow]No[/yellow]")
        summary_table.add_row("Confidence Level", f"{validation_result.get('confidence_level', 0.95)*100:.0f}%")
        summary_table.add_row("Baseline ID", str(validation_result['baseline_id']))
        summary_table.add_row("Comparison ID", str(validation_result['comparison_id']))
        if validation_result['test_type']:
            summary_table.add_row("Test Type", validation_result['test_type'])
        
        return summary_table

# Example usage
if __name__ == "__main__":
    # Create a metrics tracker with some example data
    tracker = MetricsTracker()
    
    # Add some test metrics
    baseline_metrics = TestMetrics(
        test_type="unit",
        timestamp="2023-06-15T10:00:00Z",
        total_tests=10,
        tests_passed=8,
        tests_failed=2,
        tests_skipped=0,
        tests_errors=0,
        success_rate=80.0,
        duration_sec=5.2,
        cpu_percent=45.0,
        memory_mb=128.5,
        io_read_mb=10.2,
        io_write_mb=2.1
    )
    
    comparison_metrics = TestMetrics(
        test_type="unit",
        timestamp="2023-06-15T11:00:00Z",
        total_tests=10,
        tests_passed=9,  # One more test passed
        tests_failed=1,  # One less failure
        tests_skipped=0,
        tests_errors=0,
        success_rate=90.0,  # Improved success rate
        duration_sec=4.8,   # Slightly faster
        cpu_percent=44.0,   # Slightly better CPU usage
        memory_mb=130.0,    # Slightly more memory used
        io_read_mb=10.5,    # Slightly more I/O
        io_write_mb=2.2     # Slightly more I/O
    )
    
    # Add metrics to tracker
    tracker.metrics_history = [baseline_metrics, comparison_metrics]
    
    # Create validator with default rules
    validator = ImprovementValidator(tracker, min_improvement_score=60.0)
    
    # Validate the improvement
    result = validator.validate_improvement(0, 1, "unit")
    
    # Display results
    validator.display_validation_results(result)

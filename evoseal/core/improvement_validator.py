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
from typing import Any, Dict, List, Optional, Tuple, Union

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
    """Defines a rule for validating test metrics."""
    
    name: str
    description: str
    metric: str
    direction: ImprovementDirection
    threshold: float = 0.0  # Minimum required improvement (percentage)
    required: bool = True   # If True, failure causes overall validation to fail
    weight: float = 1.0     # Weight of this rule in the overall score
    
    def validate(self, baseline: float, current: float) -> Tuple[bool, float]:
        """Validate if the metric change meets the improvement criteria.
        
        Args:
            baseline: Baseline metric value
            current: Current metric value
            
        Returns:
            Tuple of (is_valid, improvement_percentage)
        """
        if baseline == 0:
            return (not self.required, 0.0)
            
        improvement_pct = ((current - baseline) / baseline) * 100
        
        if self.direction == ImprovementDirection.INCREASE:
            is_valid = improvement_pct >= self.threshold
        elif self.direction == ImprovementDirection.DECREASE:
            is_valid = improvement_pct <= -self.threshold
        else:  # NO_CHANGE
            is_valid = abs(improvement_pct) <= self.threshold
            improvement_pct = 0.0  # No improvement for NO_CHANGE
            
        return (is_valid, improvement_pct)


class ImprovementValidator:
    """Validates if code changes represent a genuine improvement based on test metrics."""
    
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
        min_improvement_score: float = 0.0
    ) -> None:
        """Initialize the ImprovementValidator.
        
        Args:
            metrics_tracker: MetricsTracker instance for accessing test metrics
            rules: List of validation rules. If None, uses DEFAULT_RULES.
            min_improvement_score: Minimum score (0-100) to consider changes an improvement.
        """
        self.metrics_tracker = metrics_tracker
        self.rules = rules or list(self.DEFAULT_RULES)
        self.min_improvement_score = min_improvement_score
    
    def validate_improvement(
        self, 
        baseline_id: Union[int, str], 
        comparison_id: Union[int, str],
        test_type: Optional[str] = None
    ) -> ValidationResult:
        """Validate if the comparison metrics represent an improvement over baseline.
        
        Args:
            baseline_id: ID or timestamp of baseline metrics
            comparison_id: ID or timestamp of comparison metrics
            test_type: Type of test to validate. If None, validates all test types.
            
        Returns:
            Dictionary containing validation results
        """
        # Get the metrics for comparison
        baseline_metrics = self.metrics_tracker.get_metrics_by_id(baseline_id, test_type)
        comparison_metrics = self.metrics_tracker.get_metrics_by_id(comparison_id, test_type)
        
        if not baseline_metrics or not comparison_metrics:
            return {
                "is_improvement": False,
                "score": 0.0,
                "message": "Could not find metrics for the specified IDs",
                "details": []
            }
        
        # Apply validation rules
        results = []
        total_weight = 0.0
        weighted_score = 0.0
        all_required_passed = True
        
        for rule in self.rules:
            baseline_val = getattr(baseline_metrics, rule.metric, 0)
            current_val = getattr(comparison_metrics, rule.metric, 0)
            
            is_valid, improvement_pct = rule.validate(baseline_val, current_val)
            
            # Calculate score contribution (0-100)
            if rule.direction == ImprovementDirection.INCREASE:
                # For INCREASE metrics, higher improvement is better
                score = min(100, max(0, 50 + (improvement_pct / 2)))
            elif rule.direction == ImprovementDirection.DECREASE:
                # For DECREASE metrics, more negative improvement is better
                score = min(100, max(0, 50 - (improvement_pct / 2)))
            else:  # NO_CHANGE
                # For NO_CHANGE, score is based on how close to zero the change is
                score = 100 - min(100, abs(improvement_pct) * 2)
            
            # Apply rule weight
            rule_score = score * rule.weight
            weighted_score += rule_score
            total_weight += rule.weight
            
            # Track if any required rules failed
            if rule.required and not is_valid:
                all_required_passed = False
            
            results.append({
                "rule": rule.name,
                "description": rule.description,
                "metric": rule.metric,
                "baseline": baseline_val,
                "current": current_val,
                "improvement_pct": improvement_pct,
                "is_valid": is_valid,
                "required": rule.required,
                "weight": rule.weight,
                "score": score,
                "weighted_score": rule_score,
            })
        
        # Calculate overall score (0-100)
        overall_score = (weighted_score / total_weight) if total_weight > 0 else 0.0
        
        # Determine if the changes represent an improvement
        is_improvement = all_required_passed and (overall_score >= self.min_improvement_score)
        
        # Generate a summary message
        if not all_required_passed:
            message = "Validation failed: One or more required rules were not met."
        elif overall_score < self.min_improvement_score:
            message = f"Validation failed: Improvement score {overall_score:.1f} is below the minimum threshold of {self.min_improvement_score}."
        else:
            message = f"Validation passed with a score of {overall_score:.1f}/100."
        
        return {
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

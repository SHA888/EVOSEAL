# RegressionDetector Interface

The **RegressionDetector** provides a comprehensive interface for detecting performance and safety regressions in the EVOSEAL evolution pipeline. This document outlines the enhanced interface capabilities including baseline management, alert systems, and testing framework integration.

## Overview

The RegressionDetector interface is designed to:

1. **Establish and manage baselines** for performance comparison
2. **Detect regressions** by comparing system performance across versions
3. **Trigger alerts** when regressions are detected
4. **Define metrics to monitor** with configurable thresholds
5. **Integrate with testing frameworks** for automated evaluation
6. **Support both automated and human-in-the-loop** evaluation workflows

## Core Interface Methods

### Baseline Management

#### `establish_baseline(version_id, baseline_name="default") -> bool`

Establishes a baseline from a specific version's metrics.

```python
# Establish a production baseline
success = detector.establish_baseline('v1.0', 'production_baseline')

# Establish a development baseline
success = detector.establish_baseline('v1.1-dev', 'dev_baseline')
```

**Parameters:**
- `version_id`: ID of the version to use as baseline
- `baseline_name`: Name for this baseline (default: "default")

**Returns:** `True` if baseline was successfully established

#### `get_baseline(baseline_name="default") -> Optional[Dict[str, Any]]`

Retrieves baseline data by name.

```python
baseline = detector.get_baseline('production_baseline')
if baseline:
    print(f"Baseline version: {baseline['version_id']}")
    print(f"Metrics count: {len(baseline['metrics'])}")
```

#### `list_baselines() -> List[Dict[str, Any]]`

Lists all available baselines with metadata.

```python
baselines = detector.list_baselines()
for baseline in baselines:
    print(f"{baseline['name']}: v{baseline['version_id']} ({baseline['metrics_count']} metrics)")
```

#### `compare_against_baseline(version_id, baseline_name="default") -> Tuple[bool, Dict[str, Any]]`

Compares a version against an established baseline.

```python
has_regression, details = detector.compare_against_baseline('v1.2', 'production_baseline')
if has_regression:
    print(f"Regressions detected in {len(details)} metrics")
```

### Regression Detection

#### `detect_regression(old_version_id, new_version_id) -> Tuple[bool, Dict[str, Any]]`

Core regression detection between two specific versions.

```python
has_regression, details = detector.detect_regression('v1.0', 'v1.1')
```

#### `run_regression_analysis(version_id, baseline_name="default", trigger_alerts=True) -> Dict[str, Any]`

Runs comprehensive regression analysis with optional alert triggering.

```python
analysis = detector.run_regression_analysis('v1.2', 'production_baseline')
print(f"Recommendation: {analysis['summary']['recommendation']}")
```

### Alert System

#### `register_alert_callback(callback: Callable[[Dict[str, Any]], None]) -> None`

Registers a callback function to be called when regressions are detected.

```python
def email_alert(regression_data):
    send_email_to_team(f"Regression detected: {len(regression_data)} metrics affected")

detector.register_alert_callback(email_alert)
```

#### `trigger_alerts(regression_data: Dict[str, Any]) -> None`

Manually triggers all registered alert callbacks.

```python
detector.trigger_alerts(regression_details)
```

### Testing Framework Integration

#### `integrate_with_test_framework(framework_name: str, config: Dict[str, Any]) -> bool`

Configures integration with testing frameworks.

```python
pytest_config = {
    'test_command': 'pytest tests/',
    'coverage_threshold': 0.80,
    'performance_tests': True
}

success = detector.integrate_with_test_framework('pytest', pytest_config)
```

**Supported Frameworks:**
- pytest
- unittest
- nose2
- Custom frameworks via configuration

## Configuration Options

The RegressionDetector accepts comprehensive configuration:

```python
config = {
    # Basic settings
    'regression_threshold': 0.05,  # 5% default threshold
    'baseline_storage_path': './baselines.json',

    # Alert system
    'alert_enabled': True,
    'auto_baseline_update': False,

    # Monitored metrics
    'monitored_metrics': [
        'success_rate', 'accuracy', 'duration_sec',
        'memory_mb', 'error_rate', 'pass_rate'
    ],

    # Per-metric thresholds
    'metric_thresholds': {
        'success_rate': {'regression': 0.03, 'critical': 0.10},
        'accuracy': {'regression': 0.05, 'critical': 0.15},
        'duration_sec': {'regression': 0.20, 'critical': 0.50},
        'memory_mb': {'regression': 0.15, 'critical': 0.30},
        'error_rate': {'regression': 0.50, 'critical': 1.00},
        'pass_rate': {'regression': 0.05, 'critical': 0.15}
    },

    # Testing framework integration
    'test_framework_integration': {
        'pytest': {
            'test_command': 'pytest tests/',
            'coverage_threshold': 0.80
        }
    }
}

detector = RegressionDetector(metrics_tracker, config)
```

## Severity Classification

The RegressionDetector classifies regressions into four severity levels:

### Low Severity
- **Threshold:** Within normal variance (< regression_threshold)
- **Action:** Monitor, no immediate action required
- **Example:** 2% performance decrease

### Medium Severity
- **Threshold:** Exceeds regression threshold but below critical
- **Action:** Review and investigate
- **Example:** 8% accuracy decrease

### High Severity
- **Threshold:** Significant regression requiring attention
- **Action:** Review required, consider rollback
- **Example:** 15% success rate decrease

### Critical Severity
- **Threshold:** Exceeds critical threshold
- **Action:** Immediate rollback recommended
- **Example:** 25% error rate increase

## Event System Integration

The RegressionDetector publishes events for observability:

### `BASELINE_ESTABLISHED`
Published when a new baseline is established.

```python
def handle_baseline_established(event_data):
    print(f"Baseline {event_data['baseline_name']} established from v{event_data['version_id']}")

subscribe(EventType.BASELINE_ESTABLISHED, handle_baseline_established)
```

### `REGRESSION_ALERT`
Published when regressions are detected and alerts are triggered.

```python
def handle_regression_alert(event_data):
    critical_count = len(event_data['critical_regressions'])
    if critical_count > 0:
        initiate_emergency_response()

subscribe(EventType.REGRESSION_ALERT, handle_regression_alert)
```

## Metrics Monitoring

### Default Monitored Metrics

The interface monitors these metrics by default:

- **Quality Metrics:** `success_rate`, `accuracy`, `pass_rate`
- **Performance Metrics:** `duration_sec`, `memory_mb`, `execution_time`
- **Reliability Metrics:** `error_rate`, `failure_rate`

### Custom Metrics

Add custom metrics through configuration:

```python
config = {
    'monitored_metrics': [
        'success_rate', 'accuracy',  # Standard metrics
        'custom_score', 'business_kpi'  # Custom metrics
    ],
    'metric_thresholds': {
        'custom_score': {'regression': 0.10, 'critical': 0.25},
        'business_kpi': {'regression': 0.05, 'critical': 0.15}
    }
}
```

## Usage Patterns

### 1. Continuous Integration Pipeline

```python
# In CI/CD pipeline
detector = RegressionDetector(metrics_tracker, config)

# Establish baseline from stable release
detector.establish_baseline('v1.0-stable', 'ci_baseline')

# Test new build
analysis = detector.run_regression_analysis('build-123', 'ci_baseline')

if analysis['summary']['recommendation'] == 'rollback_required':
    trigger_rollback()
elif analysis['summary']['recommendation'] == 'review_required':
    notify_development_team()
```

### 2. A/B Testing Integration

```python
# Compare A/B test variants
has_regression, details = detector.detect_regression('variant_a', 'variant_b')

if has_regression:
    # Analyze which variant performs better
    summary = detector.get_regression_summary(details)
    choose_better_variant(summary)
```

### 3. Production Monitoring

```python
# Set up production monitoring
detector.register_alert_callback(send_slack_notification)
detector.register_alert_callback(create_incident_ticket)

# Continuous monitoring
for new_deployment in production_deployments:
    analysis = detector.run_regression_analysis(
        new_deployment.version,
        'production_baseline'
    )

    if analysis['has_regression']:
        handle_production_regression(analysis)
```

## Best Practices

### 1. Baseline Management
- **Establish stable baselines** from well-tested versions
- **Update baselines periodically** to reflect expected improvements
- **Use multiple baselines** for different environments (dev, staging, prod)
- **Version your baselines** with meaningful names

### 2. Threshold Configuration
- **Start with conservative thresholds** and adjust based on experience
- **Set different thresholds** for different metric types
- **Consider business impact** when setting critical thresholds
- **Review and update thresholds** regularly

### 3. Alert Management
- **Implement multiple alert channels** (email, Slack, PagerDuty)
- **Use severity-based routing** (critical → immediate, medium → daily digest)
- **Include actionable information** in alerts
- **Avoid alert fatigue** with proper threshold tuning

### 4. Testing Integration
- **Run regression tests** as part of CI/CD pipeline
- **Combine with existing test suites** for comprehensive coverage
- **Use performance baselines** alongside functional tests
- **Automate rollback decisions** for critical regressions

## Troubleshooting

### Common Issues

#### Baseline Not Found
```python
baseline = detector.get_baseline('missing_baseline')
if not baseline:
    # Establish a new baseline
    detector.establish_baseline('v1.0', 'missing_baseline')
```

#### No Metrics Available
```python
has_regression, details = detector.compare_against_baseline('v1.1')
if 'error' in details:
    logger.error(f"Metrics comparison failed: {details['error']}")
    # Check metrics_tracker configuration
```

#### Alert Callbacks Failing
```python
# Wrap callbacks in try-catch for resilience
def safe_alert_callback(regression_data):
    try:
        send_notification(regression_data)
    except Exception as e:
        logger.error(f"Alert callback failed: {e}")
        # Fallback notification method
```

## Integration Examples

See `examples/test_regression_detector_interface.py` for comprehensive usage examples demonstrating all interface capabilities.

## API Reference

For detailed API documentation, see the docstrings in `evoseal/core/regression_detector.py`.

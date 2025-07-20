# Statistical Regression Detection

The **Statistical Regression Detection** system provides advanced algorithms and mechanisms to detect performance degradation or safety issues in new system versions using statistical analysis, anomaly detection, and behavioral pattern recognition.

## Overview

This enhanced regression detection system goes beyond simple threshold-based comparisons to provide:

1. **Statistical Analysis Tools** - Confidence intervals, trend analysis, and significance testing
2. **Anomaly Detection Algorithms** - Z-score, IQR, and pattern-based outlier detection
3. **Behavioral Pattern Analysis** - Time series analysis and pattern recognition
4. **Configurable Sensitivity Levels** - Adaptive thresholds based on historical data
5. **Automated and Human-in-the-Loop Evaluation** - Comprehensive analysis with actionable insights

## Statistical Analysis Features

### Confidence Interval Analysis

The system calculates confidence intervals to determine statistical significance of changes:

```python
config = {
    'statistical_analysis': {
        'confidence_level': 0.95,  # 95% confidence intervals
        'min_samples': 3,          # Minimum samples for analysis
    }
}

# Analyze metric statistics
stats = detector.analyze_metric_statistics('success_rate', values)
print(f"95% CI: {stats['confidence_interval']}")
```

**Key Features:**
- **T-distribution** for small samples (n < 30)
- **Normal distribution** for large samples (n ≥ 30)
- **Configurable confidence levels** (90%, 95%, 99%)
- **Statistical significance testing** - determines if changes are meaningful

### Trend Analysis

Linear regression-based trend analysis identifies patterns over time:

```python
trend = stats['trend_analysis']
print(f"Trend: {trend['direction']} ({trend['strength']})")
print(f"Slope: {trend['slope']:.6f}")
print(f"R²: {trend['r_squared']:.4f}")
print(f"Predicted next value: {trend['predicted_next']:.4f}")
```

**Trend Classifications:**
- **Direction:** `increasing`, `decreasing`, `stable`
- **Strength:** `strong` (|r| > 0.8), `moderate` (|r| > 0.5), `weak` (|r| > 0.3), `negligible`
- **Predictive capability** for forecasting next values

### Basic Statistical Metrics

Comprehensive statistical analysis includes:

- **Mean and Median** - Central tendency measures
- **Standard Deviation** - Variability measure
- **Coefficient of Variation** - Relative variability (σ/μ)
- **Sample Size** - Number of data points
- **Percentile Ranking** - Historical context positioning

## Anomaly Detection Algorithms

### Z-Score Based Detection

Identifies outliers based on standard deviations from the mean:

```python
config = {
    'statistical_analysis': {
        'outlier_threshold': 2.0,  # 2 standard deviations
    },
    'anomaly_detection': {
        'algorithms': ['zscore'],
        'sensitivity': 'medium'
    }
}
```

**Z-Score Classification:**
- **Medium Anomaly:** Z-score > threshold
- **High Anomaly:** Z-score > threshold × 1.5
- **Effective for:** Normally distributed data

### Interquartile Range (IQR) Detection

Robust outlier detection using quartile-based bounds:

```python
# IQR method configuration
config['anomaly_detection']['algorithms'].append('iqr')
```

**IQR Method:**
- **Lower Bound:** Q1 - 1.5 × IQR
- **Upper Bound:** Q3 + 1.5 × IQR
- **Robust to:** Non-normal distributions and extreme outliers
- **Classification:** Based on distance from bounds

### Pattern-Based Anomaly Detection

Behavioral pattern recognition for sudden changes:

```python
config = {
    'anomaly_detection': {
        'pattern_recognition': True,
        'sensitivity': 'medium'  # low, medium, high
    }
}
```

**Pattern Detection:**
- **Sudden Spikes:** Rapid increases in metric values
- **Sudden Drops:** Rapid decreases in metric values
- **Configurable Sensitivity:**
  - `low`: 50% change threshold
  - `medium`: 30% change threshold
  - `high`: 15% change threshold

## Enhanced Regression Analysis

### Statistical Significance Integration

The enhanced regression detection combines multiple analysis methods:

```python
enhanced_analysis = detector.get_statistical_regression_analysis(
    'success_rate', old_value, new_value
)

# Check statistical significance
stat_sig = enhanced_analysis['statistical_significance']
if not stat_sig['within_confidence_interval']:
    print("Statistically significant change detected!")
```

**Significance Levels:**
- **Not Significant:** Within confidence interval
- **Significant:** Outside confidence interval
- **Severity Enhancement:** Statistical significance upgrades severity levels

### Historical Context Analysis

Provides context based on historical performance:

```python
hist_context = enhanced_analysis['historical_context']
print(f"Historical percentile: {hist_context['percentile_rank']:.1f}%")
print(f"Deviation from mean: {hist_context['deviation_from_mean']:+.4f}")
```

**Context Metrics:**
- **Historical Mean** - Long-term average performance
- **Deviation from Mean** - How far current value differs
- **Percentile Rank** - Position relative to historical data (0-100%)

### Anomaly Status Integration

Anomaly detection results integrated into regression analysis:

```python
anomaly_status = enhanced_analysis['anomaly_status']
if anomaly_status['is_anomaly']:
    for detail in anomaly_status['anomaly_details']:
        print(f"Anomaly: {detail['method']} ({detail['severity']})")
```

**Anomaly Impact on Severity:**
- **Critical Anomalies** → Upgrade to `critical` severity
- **High Anomalies** → Upgrade `low`/`medium` to `high`
- **Multiple Detection Methods** → Higher confidence in anomaly classification

## Configuration Options

### Statistical Analysis Configuration

```python
statistical_config = {
    'confidence_level': 0.95,        # Confidence interval level
    'min_samples': 3,                # Minimum samples for analysis
    'trend_window': 10,              # Number of points for trend analysis
    'seasonal_period': 7,            # Period for seasonal adjustment
    'outlier_threshold': 2.0,        # Standard deviations for outliers
    'enable_trend_analysis': True,   # Enable trend analysis
    'enable_anomaly_detection': True, # Enable anomaly detection
    'enable_seasonal_adjustment': False # Enable seasonal adjustment
}
```

### Anomaly Detection Configuration

```python
anomaly_config = {
    'algorithms': ['zscore', 'iqr', 'isolation'],  # Detection algorithms
    'sensitivity': 'medium',                       # Sensitivity level
    'adaptive_threshold': True,                    # Adaptive thresholds
    'pattern_recognition': True                    # Pattern-based detection
}
```

## Usage Examples

### Basic Statistical Analysis

```python
# Initialize with statistical analysis
detector = RegressionDetector(config, metrics_tracker)

# Analyze metric statistics
values = [0.85, 0.87, 0.86, 0.89, 0.88, 0.90, 0.85, 0.91, 0.89, 0.92]
stats = detector.analyze_metric_statistics('success_rate', values)

print(f"Mean: {stats['mean']:.4f}")
print(f"Trend: {stats['trend_analysis']['direction']}")
print(f"Anomalies: {len(stats['anomalies'])}")
```

### Enhanced Regression Detection

```python
# Build historical data
for version_id in version_history:
    metrics = get_metrics(version_id)
    detector.update_historical_metrics(version_id, metrics)

# Detect regressions with statistical analysis
has_regression, details = detector.detect_regression('v1.5', 'v1.6')

for metric, analysis in details.items():
    print(f"Metric: {metric}")
    print(f"Severity: {analysis['severity']}")

    # Statistical significance
    if analysis['statistical_significance']:
        sig = analysis['statistical_significance']['significance']
        print(f"Statistical significance: {sig}")

    # Anomaly status
    if analysis['anomaly_status']['is_anomaly']:
        print("🚨 Anomaly detected!")
```

### Trend Analysis Over Time

```python
# Analyze trends across multiple versions
versions = ['v1.0', 'v1.1', 'v1.2', 'v1.3', 'v1.4', 'v1.5']
values = [get_metric_value(v, 'duration_sec') for v in versions]

stats = detector.analyze_metric_statistics('duration_sec', values)
trend = stats['trend_analysis']

if trend['direction'] == 'increasing' and trend['strength'] in ['moderate', 'strong']:
    print("⚠️ Performance degradation trend detected!")
    print(f"Predicted next value: {trend['predicted_next']:.2f}s")
```

## Algorithm Details

### Linear Regression for Trend Analysis

The trend analysis uses simple linear regression:

```
slope = Σ((xi - x̄)(yi - ȳ)) / Σ((xi - x̄)²)
correlation = slope × (σx / σy)
r² = correlation²
```

Where:
- `xi` = time points (0, 1, 2, ...)
- `yi` = metric values
- `x̄, ȳ` = means of x and y
- `σx, σy` = standard deviations

### Z-Score Anomaly Detection

```
z = |x - μ| / σ
```

Where:
- `x` = observed value
- `μ` = sample mean
- `σ` = sample standard deviation
- Anomaly if `z > threshold`

### IQR Anomaly Detection

```
IQR = Q3 - Q1
Lower Bound = Q1 - 1.5 × IQR
Upper Bound = Q3 + 1.5 × IQR
```

Anomaly if value < Lower Bound or value > Upper Bound

## Performance Considerations

### Memory Usage

- **Historical Data Storage:** Configurable window size limits memory usage
- **Deque Implementation:** Efficient circular buffer for time series data
- **Lazy Evaluation:** Statistical analysis only when needed

### Computational Complexity

- **Trend Analysis:** O(n) where n = number of data points
- **Z-Score Detection:** O(n) for each metric
- **IQR Detection:** O(n log n) due to sorting
- **Overall Complexity:** Linear with respect to metrics and data points

### Optimization Strategies

- **Minimum Sample Requirements:** Avoid analysis with insufficient data
- **Configurable Algorithms:** Enable only needed detection methods
- **Caching:** Statistical results cached for repeated queries
- **Batch Processing:** Analyze multiple metrics simultaneously

## Integration with Existing Systems

### Backward Compatibility

The enhanced statistical analysis is fully backward compatible:

```python
# Basic usage still works
has_regression, details = detector.detect_regression('v1.0', 'v1.1')

# Enhanced features available when configured
if detector.statistical_config['enable_trend_analysis']:
    # Statistical analysis automatically included
    pass
```

### Event System Integration

Statistical analysis results are published via the event system:

```python
# Listen for enhanced regression events
def handle_statistical_regression(event_data):
    if event_data.get('statistical_significance') == 'significant':
        trigger_detailed_investigation()

subscribe(EventType.REGRESSION_DETECTED, handle_statistical_regression)
```

## Best Practices

### Configuration Guidelines

1. **Start Conservative:** Begin with higher confidence levels (95%) and lower sensitivity
2. **Adjust Based on Data:** Tune thresholds based on your metric characteristics
3. **Historical Data:** Collect sufficient historical data (≥10 samples) for reliable analysis
4. **Algorithm Selection:** Choose algorithms appropriate for your data distribution

### Data Quality Requirements

1. **Sufficient Samples:** Minimum 3 samples for basic analysis, 10+ for robust trends
2. **Data Consistency:** Ensure metrics are measured consistently across versions
3. **Outlier Handling:** Consider data cleaning before statistical analysis
4. **Missing Data:** Handle missing values appropriately

### Interpretation Guidelines

1. **Statistical Significance ≠ Practical Significance:** Large datasets may show statistical significance for trivial changes
2. **Multiple Testing:** Consider multiple comparison corrections when analyzing many metrics
3. **Context Matters:** Always interpret statistical results in business/technical context
4. **Trend vs. Noise:** Distinguish between meaningful trends and random fluctuations

## Troubleshooting

### Common Issues

#### Insufficient Historical Data
```python
stats = detector.analyze_metric_statistics('metric', values)
if 'error' in stats:
    print("Need more historical data for statistical analysis")
```

#### No Trend Detected
```python
trend = stats['trend_analysis']
if trend.get('strength') == 'negligible':
    print("No significant trend - data may be stable or noisy")
```

#### False Positives in Anomaly Detection
```python
# Adjust sensitivity
config['anomaly_detection']['sensitivity'] = 'low'  # Reduce false positives
config['statistical_analysis']['outlier_threshold'] = 2.5  # More conservative
```

## API Reference

### Core Methods

- `analyze_metric_statistics(metric_name, values)` - Comprehensive statistical analysis
- `get_statistical_regression_analysis(metric_name, old_value, new_value)` - Enhanced regression analysis
- `update_historical_metrics(version_id, metrics)` - Update historical data
- `_analyze_trend(values)` - Trend analysis using linear regression
- `_detect_anomalies(metric_name, values)` - Multi-algorithm anomaly detection

### Configuration Parameters

See the configuration sections above for detailed parameter descriptions.

## Examples

See `examples/test_statistical_regression_detection.py` for comprehensive usage examples demonstrating all statistical analysis capabilities.

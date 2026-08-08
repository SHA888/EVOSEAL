# EVOSEAL Hyperparameter Space

> **Status:** Reference document (follow-up from ADR 0005 §6).
> **Purpose:** Enumerate all tuneable pipeline parameters, their current values/ranges,
>   and where they are defined. Prerequisite for any PBT feasibility spike or systematic
>   sensitivity analysis.

EVOSEAL exposes dozens of tuneable parameters spread across configuration files, dataclass
defaults, and inline constants. This document catalogs them by subsystem so that operators
and researchers know what can be adjusted and what the defaults are.

---

## 1. Evolution Pipeline

The core evolutionary loop parameters, defined in `ExperimentConfig` (`evoseal/models/experiment.py`).

| Parameter | Default | Range | Description |
|-----------|---------|-------|-------------|
| `population_size` | `50` | ≥1 | Number of candidate variants per generation |
| `mutation_rate` | `0.1` | [0.0, 1.0] | Probability of mutating a candidate |
| `crossover_rate` | `0.8` | [0.0, 1.0] | Probability of crossover between two candidates |
| `fitness_function` | `"default"` | string | Name of the fitness evaluation strategy |
| `iterations` (CLI) | `5` | ≥1 | Number of evolution iterations when run from CLI |

**Configured via:** `ExperimentConfig` dataclass, overridable through `ExperimentIntegration`
(`evoseal/core/experiment_integration.py:496-503`).

---

## 2. Selection

Parameters for candidate selection strategies, defined in `evoseal/core/selection.py`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `tournament_size` | `3` | Number of individuals in each tournament round |
| `elitism` | `1` | Number of top candidates preserved unchanged across generations |

---

## 3. LLM Provider (Generation)

Model inference parameters, defined per-provider in `evoseal/providers/`. The Ollama provider
(`evoseal/providers/ollama_provider.py`) sets these as defaults:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `temperature` | `0.7` (coder), `0.3` (reviewer) | Sampling temperature — higher = more creative |
| `top_p` | `0.9` | Nucleus sampling threshold |
| `top_k` | `40` | Top-k sampling cutoff |
| `max_tokens` / `num_predict` | `2048` | Maximum tokens to generate per response |
| `timeout` | `90` (seconds) | Per-request timeout for provider calls |

**Configured via:** `SEALConfig.providers` in `evoseal/config.py`. Provider priority determines
which is used when multiple are enabled.

---

## 4. Fine-Tuning

Training hyperparameters for the LoRA/QLoRA fine-tuning path, defined in
`evoseal/fine_tuning/model_fine_tuner.py`.

### 4.1 Training Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `epochs` | `3` | Number of training epochs |
| `learning_rate` | `2e-4` | AdamW learning rate |
| `batch_size` | `4` | Per-device training batch size |

### 4.2 LoRA Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `r` (rank) | `16` | LoRA rank — controls adapter capacity |
| `lora_alpha` | `32` | LoRA scaling factor |
| `lora_dropout` | `0.1` | Dropout probability on LoRA layers |
| `target_modules` | `["q_proj", "k_proj", "v_proj", "o_proj"]` | Which attention layers to adapt |

### 4.3 Training Infrastructure

| Parameter | Default | Description |
|-----------|---------|-------------|
| `logging_steps` | `10` | Log training metrics every N steps |
| `save_steps` | `100` | Save checkpoint every N steps |
| `save_total_limit` | `2` | Maximum checkpoints to retain |
| `dataloader_drop_last` | `True` | Drop incomplete final batch |

### 4.4 Scheduling & Readiness

| Parameter | Default | Location | Description |
|-----------|---------|----------|-------------|
| `min_training_samples` | `100` | `TrainingManager.__init__` | Minimum evolution results before training triggers |
| `training_check_interval` | `1800` (30 min) | `SEALConfig` | How often the daemon checks training readiness |

---

## 5. Regression Detection

Thresholds for detecting performance/quality regressions, defined in
`evoseal/core/regression_detector.py` and `configs/safety.yaml`.

### 5.1 Global Thresholds

| Parameter | Default | Description |
|-----------|---------|-------------|
| `regression_threshold` | `0.05` (5%) | Global default — change beyond this is a regression |

### 5.2 Per-Metric Thresholds (from `configs/safety.yaml`)

| Metric | Regression | Critical | Direction |
|--------|-----------|----------|-----------|
| `duration_sec` | +10% | +25% | Lower is better |
| `memory_mb` | +10% | +30% | Lower is better |
| `execution_time` | +10% | +25% | Lower is better |
| `success_rate` | −5% | −10% | Higher is better |
| `pass_rate` | −5% | −10% | Higher is better |
| `correctness` | −1% | −5% | Higher is better |

### 5.3 Statistical Analysis

| Parameter | Default | Description |
|-----------|---------|-------------|
| `confidence_level` | `0.95` | Confidence interval for statistical tests |
| `min_samples` | `3` | Minimum data points before statistical analysis runs |
| `trend_window` | `10` | Number of recent points used for trend analysis |
| `seasonal_period` | `7` | Period for seasonal adjustment |
| `outlier_threshold` | `2.0` (std devs) | Z-score threshold for outlier detection |
| `enable_trend_analysis` | `True` | Whether to compute trend direction |
| `enable_anomaly_detection` | `True` | Whether to flag anomalies |
| `enable_seasonal_adjustment` | `False` | Whether to apply seasonal correction |

### 5.4 Anomaly Detection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `algorithms` | `["zscore", "iqr", "isolation"]` | Which anomaly detection algorithms to run |
| `sensitivity` | `"medium"` | Detection sensitivity — `low`, `medium`, `high` |
| `adaptive_threshold` | `True` | Adapt thresholds based on historical data |
| `pattern_recognition` | `True` | Enable behavioral pattern analysis |

---

## 6. Improvement Validation

Rules that gate whether a self-modification is accepted, defined in
`evoseal/core/improvement_validator.py`.

### 6.1 Validation Rules (DEFAULT_RULES)

| Rule | Metric | Direction | Threshold | Required | Weight |
|------|--------|-----------|-----------|----------|--------|
| `success_rate_stable` | `success_rate` | increase | −5.0% | Yes | 2.0 |
| `performance_improved` | `duration_sec` | decrease | −10.0% | Yes | 1.5 |
| `memory_usage_stable` | `memory_mb` | decrease | −10.0% | No | 1.0 |
| `no_new_failures` | `tests_failed` | decrease | 0.0 | Yes | 2.0 |

A negative threshold on an "increase" metric means "allow up to this much decrease."
A threshold of `0.0` on `no_new_failures` means zero new failures are tolerated.

### 6.2 Scoring

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_improvement_score` | varies | Minimum weighted score for validation to pass |
| `sample_size` | `1` | Number of evaluation runs per candidate |

---

## 7. Error Recovery & Resilience

Retry and recovery strategy parameters, defined in `evoseal/core/error_recovery.py`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_retries` | `3` | Maximum retry attempts before escalation |
| `retry_delay` | `1.0` (sec) | Initial delay between retries |
| `backoff_multiplier` | `2.0` | Exponential backoff multiplier |
| `max_delay` | `300.0` (sec) | Cap on retry delay |
| `timeout` | `30.0` (sec) | Per-operation timeout |
| `escalation_threshold` | `5` | Failures before escalating to operator |

The resilience integration layer (`evoseal/core/resilience.py`, `resilience_integration.py`)
adds:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `health_check_interval` | `30`–`60` (sec) | How often to poll component health |

---

## 8. Resource Limits

Limits on test execution and sandboxed runs, defined in `evoseal/core/testrunner.py` and
`configs/safety.yaml`.

### 8.1 Test Runner

| Parameter | Default | Description |
|-----------|---------|-------------|
| `timeout` | `60` (sec) | Default test execution timeout |
| `test_dir` | `"tests"` | Default test directory |
| `cpu_limit_secs` | `120` | CPU time limit for sandboxed tests |
| `memory_limit_bytes` | `2 GB` | Memory limit for sandboxed tests |
| `fd_limit` | `256` | File descriptor limit for sandboxed tests |

### 8.2 Sandbox (from `configs/safety.yaml`)

| Parameter | Default | Description |
|-----------|---------|-------------|
| `sandbox.enabled` | `True` | Whether to sandbox test execution |
| `sandbox.cpu_limit_secs` | `120` | Sandbox CPU limit |
| `sandbox.memory_limit_mb` | `512` | Sandbox memory limit |
| `sandbox.fd_limit` | `256` | Sandbox file descriptor limit |

---

## 9. Budget & Cost

Token and cost limits, defined in `config/budget.yaml`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_tokens_per_run` | `500000` | Hard token limit per evolution run |
| `max_cost_per_run` | `null` (unlimited) | Hard cost limit per run |
| `cost_per_1k_tokens` | `0.005` | Cost estimation rate (Claude Sonnet pricing) |
| `warn_at_percent_of_budget` | `80` | Warn when this % of budget is consumed |
| `stop_on_exhaustion` | `True` | Stop gracefully when budget is exhausted |
| `stop_tolerance_tokens` | `500` | Token buffer before hard stop |
| `max_tokens_per_cycle` | `15000` | Per-cycle token cap |
| `max_tokens_per_epoch` | `20000` | Per-epoch token cap |

---

## 10. Scheduling & Daemon

Parameters for the continuous evolution daemon, defined in `evoseal/config.py`.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `evolution_interval` | `3600` (1 hr) | How often the daemon triggers an evolution cycle |
| `training_check_interval` | `1800` (30 min) | How often the daemon checks training readiness |
| `min_evolution_samples` | `50` | Minimum samples before evolution data is used |
| `model_validation_timeout` | `300` (sec) | Timeout for model validation runs |

---

## 11. Monitoring & Logging

Dashboard and log analysis parameters.

### 11.1 Dashboard

| Parameter | Default | Location | Description |
|-----------|---------|----------|-------------|
| `dashboard_port` | `8081` | `SEALConfig` | Dashboard HTTP port |
| `dashboard_host` | `"localhost"` | `SEALConfig` | Dashboard bind address |

### 11.2 Log Analysis

| Parameter | Default | Location | Description |
|-----------|---------|----------|-------------|
| `window_size` | `1000` | `LogAggregator.__init__` | Log buffer size |
| `analysis_interval` | `60` (sec) | `LogAggregator.__init__` | How often to analyze logs |
| `error_rate` threshold | `0.1` (10%) | `LogAggregator.alert_thresholds` | Error rate that triggers alert |
| `critical_count` threshold | `5` | `LogAggregator.alert_thresholds` | Critical log count that triggers alert |
| `logs_per_minute` threshold | `1000` | `LogAggregator.alert_thresholds` | Log volume that triggers alert |

---

## 12. Safety & Checkpoints

Safety enforcement parameters from `configs/safety.yaml`.

### 12.1 Checkpoints

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_checkpoints` | `10` | Maximum checkpoints to retain |
| `auto_rollback_on_critical` | `True` | Automatically rollback on critical regression |

### 12.2 Edit Scope

| Parameter | Default | Description |
|-----------|---------|-------------|
| `edit_scope.enabled` | `True` | Whether edit-scope enforcement is active |
| `forbidden_paths` | `[".env", "Makefile"]` | Individual files the evolution loop cannot modify |
| `forbidden_dirs` | `[".git", ".github/workflows", ...]` | Directories entirely off-limits |
| `allowed_dirs` | `["evoseal/", "tests/", ...]` | Directories the evolution loop may modify |

---

## Recommendations for PBT / Sensitivity Analysis

Based on ADR 0005, the following parameters are the strongest candidates for adaptive tuning
because they have the most direct impact on evolution outcomes:

1. **High impact, easy to vary:** `temperature`, `mutation_rate`, `crossover_rate`,
   `tournament_size`, `elitism`, `learning_rate`, `batch_size`
2. **High impact, constrained by hardware:** `population_size`, LoRA `r`/`lora_alpha`,
   `max_tokens`
3. **Safety-critical (should NOT be auto-tuned without guardrails):**
   `regression_threshold`, validation rule thresholds, `max_checkpoints`,
   `auto_rollback_on_critical`, edit-scope paths

A PBT feasibility spike should focus on category 1, hold category 2 constant, and
never touch category 3 without human review.

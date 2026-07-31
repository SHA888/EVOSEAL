# API Reference

This document provides detailed information about the EVOSEAL public API — both the CLI
and the Python internals. For the Phase 3 monitoring dashboard REST/WebSocket API, see
[API_REFERENCE.md](../API_REFERENCE.md).

---

## CLI

EVOSEAL exposes a Typer-based CLI (`evoseal`) defined at `evoseal.cli.main:app`.

### Top-level

| Command | Description |
|---|---|
| `evoseal --version` | Print the installed version |
| `evoseal init project` | Scaffold a new EVOSEAL project |
| `evoseal doctor` | Validate environment (API keys, configs, dependencies, git state) |
| `evoseal estimate-cost` | Estimate token/cost for a given number of iterations |

### Config (`evoseal config`)

| Subcommand | Description |
|---|---|
| `evoseal config show` | Display current configuration |
| `evoseal config set <key> <value>` | Set a config value |
| `evoseal config unset <key>` | Remove a config value |

### Pipeline (`evoseal pipeline`)

| Subcommand | Description |
|---|---|
| `evoseal pipeline init` | Initialize pipeline state |
| `evoseal pipeline start` | Start the evolution pipeline |
| `evoseal pipeline pause` / `resume` | Pause or resume a running pipeline |
| `evoseal pipeline stop` | Stop the pipeline |
| `evoseal pipeline status` | Show current pipeline status |
| `evoseal pipeline config` | Show/modify pipeline configuration |
| `evoseal pipeline logs` | Display pipeline logs |

### Continuous Evolution (`evoseal start`)

| Subcommand | Description |
|---|---|
| `evoseal start evolution` | Start the `ContinuousEvolutionService` daemon (Phase 3 loop) |

### Subsystem Commands

| Command | Description |
|---|---|
| `evoseal dgm improve/evaluate/compare` | Interact with the DGM subsystem |
| `evoseal openevolve run/resume/analyze` | Interact with OpenEvolve |
| `evoseal export results/variant/all` | Export evolution results |

---

## Core Python API

### `EvolutionPipeline`

The central orchestrator. Integrates DGM, OpenEvolve, and SEAL to run the
code evolution workflow.

**Module:** `evoseal.core.evolution_pipeline`

```python
from evoseal.core.evolution_pipeline import EvolutionPipeline, EvolutionConfig

# Initialize with defaults
pipeline = EvolutionPipeline()

# Or with explicit config
pipeline = EvolutionPipeline(
    EvolutionConfig(
        dgm_config={...},
        openevolve_config={...},
        seal_config={...},
        test_config={...},
        max_iterations=1000,
    )
)

# Run one or more evolution iterations
results = await pipeline.run_evolution_cycle(iterations=1)

# Run with safety gates (checkpoint + rollback on regression)
results = await pipeline.run_evolution_cycle_with_safety(iterations=1)
```

#### `EvolutionConfig`

Dataclass holding per-subsystem configuration and runaway-control knobs:

| Field | Type | Default | Description |
|---|---|---|---|
| `dgm_config` | `dict` | `{}` | DGM-specific settings |
| `openevolve_config` | `dict` | `{}` | OpenEvolve-specific settings |
| `seal_config` | `dict` | `{}` | SEAL-specific settings |
| `test_config` | `dict` | `{}` | Test runner settings |
| `metrics_config` | `dict` | `{}` | Metrics tracker settings |
| `validation_config` | `dict` | `{}` | Improvement validation settings |
| `version_control_config` | `dict` | `{}` | Version control settings |
| `max_iterations` | `int` | `1000` | Hard cap on evolution iterations |
| `max_consecutive_rejections` | `int` | `5` | Stuck-generator circuit threshold |

#### Key Methods

| Method | Signature | Description |
|---|---|---|
| `run_evolution_cycle` | `async (iterations=1) -> list[dict]` | Run N evolution iterations |
| `run_evolution_cycle_with_safety` | `async (iterations=1) -> list[dict]` | Same, with checkpoint/rollback safety |
| `pause` | `() -> bool` | Pause the pipeline |
| `resume` | `() -> bool` | Resume a paused pipeline |

---

## Safety Layer

### `SafetyIntegration`

Coordinates safety checkpoints, edit-scope validation, and regression detection.

**Module:** `evoseal.core.safety_integration`

| Method | Description |
|---|---|
| `create_safety_checkpoint(description)` | Create a git-backed safety checkpoint |
| `validate_version_safety(version_id, ...)` | Validate a proposed version against safety rules |
| `execute_safe_evolution_step(...)` | Run one evolution step inside the safety envelope |
| `validate_edit_path(file_path)` | Check a file path against the edit-scope allowlist |
| `validate_edits_before_apply(edited_files)` | Batch pre-apply edit validation |
| `get_safety_status()` | Return current safety status dict |

### `CheckpointManager`

Git-backed checkpointing and rollback.

**Module:** `evoseal.core.checkpoint_manager`

| Method | Description |
|---|---|
| `create_checkpoint(version_id, changes, ...)` | Create a named checkpoint |
| `restore_checkpoint(version_id)` | Restore to a previous checkpoint |
| `get_checkpoint_path(version_id)` | Get the filesystem path for a checkpoint |

### `EditScopeValidator`

Validates that self-modifications stay within the allowed scope.

**Module:** `evoseal.core.edit_scope_validator`

### `RegressionDetector`

Detects metric regressions between versions.

**Module:** `evoseal.core.regression_detector`

### `TestRunner` / `SandboxedTestRunner`

Executes test suites, optionally in a sandboxed environment (Tier 1 isolation).

**Module:** `evoseal.core.testrunner`

---

## Phase 3 — Continuous Evolution

### `ContinuousEvolutionService`

Long-running daemon that drives the autonomous evolution → training → deployment loop.

**Module:** `evoseal.services.continuous_evolution_service`

```python
from evoseal.services.continuous_evolution_service import ContinuousEvolutionService

service = ContinuousEvolutionService(config={...})
await service.start()  # enters the service loop
await service.shutdown()  # graceful stop
```

| Method | Description |
|---|---|
| `start()` | Start the daemon (signal handlers, service loop) |
| `shutdown()` | Graceful shutdown |
| `generate_service_report()` | Return a status/evolution/training report dict |

### `TrainingManager`

Manages fine-tuning readiness checks, data preparation, and training cycles.

**Module:** `evoseal.fine_tuning.training_manager`

| Method | Description |
|---|---|
| `check_training_readiness()` | Check if enough data exists and no training is in progress |
| `prepare_training_data()` | Build training dataset from evolution results |
| `run_training_cycle()` | Execute one full training cycle |
| `get_training_status()` | Return current training status |

---

## Monitoring Dashboard

The Phase 3 monitoring dashboard serves a REST API and WebSocket interface on port 9613
(default). Full endpoint documentation is in [API_REFERENCE.md](../API_REFERENCE.md).

### Quick Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Dashboard HTML page |
| `/api/status` | GET | Service status + basic metrics |
| `/api/metrics` | GET | Comprehensive system metrics |
| `/api/report` | GET | Detailed evolution report |
| `/ws` | WS | Real-time metrics updates (every 30s) |

### Authentication

When the dashboard is constructed with `auth_token`, all `/api/*` and `/ws` requests must
include `Authorization: Bearer <token>`. WebSocket clients may pass `?token=<value>` as a
query parameter instead.

### CORS

Allowed origins default to the dashboard's own `host:port`. Binding to `0.0.0.0` logs a
security warning. Wildcard `*` origins disable `allow_credentials` per the CORS spec.

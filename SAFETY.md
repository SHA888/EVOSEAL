# SAFETY.md — Safety Invariants and Known Gaps

This file summarizes the safety invariants EVOSEAL enforces, the protections that
are in place, and the known gaps that remain. For the full threat model, see
[docs/safety/threat_model.md](docs/safety/threat_model.md).

## Invariants (enforced)

These protections are implemented and tested:

1. **Checkpoint before every edit.** The `CheckpointManager` creates a restorable
   snapshot before any self-modification is applied. Checkpoints are SHA-256
   verified for integrity.

2. **Automatic rollback on critical regression.** A critical regression (≥25%
   performance drop, ≥10% quality drop) triggers automatic rollback to the last
   known-good checkpoint. Rollback is file-copy based, not Git-mutating.

3. **Rollback target validation.** The rollback manager refuses to restore to the
   current working directory, a parent directory, or a system directory
   (`/`, `/home`, `/usr`, `/var`, `/etc`, `/opt`). Falls back to
   `./.evoseal/rollback_target` when no safe directory is available.

4. **Per-test timeout.** Test execution uses `subprocess.run(..., timeout=60s)`.
   A hung test cannot block the evolution loop indefinitely.

5. **Cascading rollback cap.** `max_rollback_attempts=3` prevents infinite
   rollback chains.

6. **Component circuit breakers.** The resilience layer opens breakers after a
   component call's failure threshold and switches to degraded/fallback modes.

7. **Budget enforcement.** The loop stops gracefully when token or cost limits are
   reached. Warning at 80% of configured budget.

8. **Edit-scope allowlist.** The evolution loop can only modify files within the
   allowed scope. Safety-critical files (`configs/safety.yaml`, `.env`, CI
   workflows) are protected.

9. **Regression detection.** The `RegressionDetector` uses statistical thresholds
   (5% global default, per-metric overrides) to identify regressions before they
   are accepted.

## Known gaps (not yet addressed)

These are documented risks that are **not** defended against today:

| Gap | Risk | Mitigation planned |
|-----|------|--------------------|
| **Network egress from generated code** | Test subprocess inherits network access; a variant could exfiltrate secrets | Scrub test environment (Plans.md 2.2) |
| **Unbounded CPU/memory** | Monitored via `psutil` but not limited; a runaway variant can consume resources until timeout | Resource limits (Plans.md 2.15) |
| **Secret exposure in test subprocess** | `os.environ.copy()` passes full environment including API keys to test subprocess | Scrubbed environment for tests |
| **No hard iteration cap** | `max_iterations` is config, not enforced as a stopping condition in the pipeline | Enforce in pipeline (Plans.md 2.15) |
| **"Generator stuck" detection** | Repeated failures cause repeated rollbacks without a circuit to stop the loop | Stuck-generator circuit (Plans.md 2.15) |

## Safety-related files

| File | Purpose |
|------|---------|
| `evoseal/core/safety_integration.py` | Gates edits on outcome (regression/improvement validation) |
| `evoseal/core/rollback_manager.py` | Checkpoint-based rollback with target validation |
| `evoseal/core/regression_detector.py` | Statistical regression detection |
| `evoseal/core/improvement_validator.py` | Validates that a variant is an improvement |
| `evoseal/core/checkpoint_manager.py` | Creates/restores SHA-256 verified checkpoints |
| `configs/safety.yaml` | Safety thresholds and configuration |
| `tests/safety/` | Adversarial and safety-critical tests |

## Running safety checks

```bash
# Run all safety tests
uv run pytest tests/safety/ -v

# Run adversarial edit tests
uv run pytest tests/safety/test_adversarial_edits.py -v

# Run rollback safety tests
uv run pytest tests/safety/test_rollback_safety_critical.py -v

# Validate system health
uv run evoseal doctor
```

## See also

- [AGENT.md](AGENT.md) — agent identity and constraints.
- [EVOLUTION.md](EVOLUTION.md) — current evolution goals and state.
- [docs/safety/threat_model.md](docs/safety/threat_model.md) — full threat model.
- [docs/adr/0001-isolation-strategy.md](docs/adr/0001-isolation-strategy.md) — sandbox decision record (ADR 0001).

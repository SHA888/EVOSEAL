# Progressive Rollout Gating for Self-Modifications

This document specifies a promotion model for self-modification candidates in
EVOSEAL's evolution pipeline. Instead of immediately adopting every change that
passes regression tests, candidates progress through stability stages before
permanent adoption.

> **Implementation status.** This is a design document. The gating mechanism
> described here is not yet implemented — the current pipeline adopts or rejects
> changes in a single step.

---

## 1. Motivation

The evolution pipeline currently treats `should_continue` as a binary gate: a
candidate either passes validation and is adopted, or it fails and is discarded.
This has two problems:

1. **Flaky improvements.** A change that passes regression tests once may
   introduce subtle instability that only surfaces across multiple cycles.
   Single-shot validation cannot distinguish a genuinely better variant from one
   that happened to pass on a favorable test run.

2. **No graduated trust.** All adopted changes are treated identically — a
   formatting tweak and a core-algorithm rewrite both go live immediately.
   Riskier changes deserve more scrutiny before they are considered permanent.

Progressive rollout gating addresses both by requiring candidates to demonstrate
stability over time, not just at adoption time.

---

## 2. Stage Model

Every self-modification candidate occupies one of three stages:

| Stage | Meaning | Promotion condition |
|-------|---------|---------------------|
| **candidate** | Under initial evaluation | Passes regression tests and the `_validate_improvement` gate |
| **beta** | Active but not permanent | Survives N additional evolution cycles without regression |
| **stable** | Permanently adopted | Promoted from beta after N clean cycles |

### Stage transitions

```text
  ┌──────────┐    ┌──────────┐    ┌──────────────┐
  │ candidate │───▶│   beta   │───▶│   stable     │
  └──────────┘    └──────────┘    └──────────────┘
       │               │
       │ regression    │ regression
       ▼               ▼
  ┌──────────┐    ┌──────────┐
  │ rejected  │    │ rejected │
  └──────────┘    └──────────┘
```

- **candidate → beta**: the candidate passes the initial validation gate
  (`_validate_improvement`), exactly as today. At this point the change is
  applied to the working tree but tracked as beta.
- **beta → stable**: the candidate survives N consecutive evolution cycles
  without any regression being detected. N is configurable (default: 3).
- **beta/candidate → rejected**: a regression is detected at any stage. The
  change is rolled back and recorded as rejected.

### What "regression" means at each stage

| Stage | Regression signal |
|-------|-------------------|
| candidate | Fails `_validate_improvement` (existing gate) |
| beta | Any subsequent cycle's validation detects a metric drop against the beta candidate's baseline snapshot |
| stable | Terminal stage — no longer monitored for regression. Defects discovered after promotion are handled through the normal bug-fix pipeline, not rollout rollback. |

---

## 3. Data Model

Each tracked candidate needs:

```python
@dataclass
class RolloutCandidate:
    candidate_id: str  # e.g. checkpoint version id
    stage: str  # "candidate" | "beta" | "stable" | "rejected"
    created_at: datetime  # when the candidate was first created
    promoted_to_beta_at: datetime | None
    promoted_to_stable_at: datetime | None
    clean_cycles: int  # count of consecutive cycles without regression
    regression_count: int  # total regressions detected
    baseline_metrics: dict  # metrics snapshot at creation time
    checkpoint_path: str  # for rollback
```

This can be stored as a JSON file alongside the existing version registry
(e.g. `rollout_registry.json`) or as an extension to `ModelVersionManager`'s
registry.

---

## 4. Integration Points

### 4.1 Evolution Pipeline (`_validate_improvement`)

The existing `_validate_improvement` gate remains the first filter. When it
accepts a candidate, instead of immediately adopting it permanently, the
pipeline should:

1. Record the candidate as `stage="candidate"` with a baseline metrics snapshot.
2. Apply the change (as it does today).
3. Promote to `beta` immediately (the candidate has already passed the
   validation gate, so no dwell period at the candidate stage is needed — the
   stage exists to register the checkpoint and baseline metrics before the beta
   observation window begins).

### 4.2 Continuous Evolution Service

The continuous evolution loop (`_run_evolution_cycle`) should, at the start of
each cycle:

1. Check all active beta candidates.
2. Run validation against each beta candidate's baseline metrics.
3. If clean: increment `clean_cycles`. If `clean_cycles >= N`: promote to
   `stable`.
4. If regression: mark `rejected`. If `auto_rollback_on_regression` is `true`
   (§5/§6), roll back to the candidate's checkpoint; otherwise log the
   regression and leave the working tree unchanged for manual intervention.

### 4.3 Bidirectional Manager

`BidirectionalEvolutionManager.run_loop_cycle()` should be aware of rollout
state. A model deployed from a `beta` candidate should be flagged as
pre-stable, so that the generation surface can optionally prefer `stable`
models for production workloads while using `beta` models for experimentation.

---

## 5. Configuration

Add to `configs/safety.yaml` or a new `configs/evolution.yaml`:

```yaml
rollout_gating:
  enabled: true
  beta_cycles_required: 3        # N: cycles a beta must survive
  auto_rollback_on_regression: true
  prefer_stable_for_generation: true  # generation uses stable model when available
```

---

## 6. Rollback

When a regression is detected at any stage:

1. Restore the checkpoint captured at candidate creation time.
2. Mark the candidate as `rejected` with the regression details.
3. If the candidate was `beta`, the working tree reverts to the pre-candidate
   state — the N clean cycles it accumulated are discarded.

This leverages the existing `CheckpointManager` (fixed in PR #74 for path
traversal) and is consistent with the current rollback-on-failure pattern.

Rollback is gated by the `auto_rollback_on_regression` config flag (§5). When
`false`, regressions are logged and the candidate is marked `rejected`, but the
working tree is not automatically reverted — a human must intervene to restore
the checkpoint manually.

---

## 7. Relationship to Existing Patterns

This design is analogous to release channels in software distribution:

| Rollout stage | Software release analogue |
|---------------|---------------------------|
| candidate | Nightly / dev build |
| beta | Beta channel — active but not default |
| stable | Stable release — promoted for general use |

OpenClaw uses npm dist-tags (`stable`, `beta`, `dev`) to serve different
versions to different users. EVOSEAL's rollout gating applies the same
graduated-trust principle to autonomous self-modifications rather than
user-facing releases.

---

## 8. Future Extensions

- **Graduated rollout**: instead of all-or-nothing promotion, weight beta
  candidates by `clean_cycles / N` and use that weight in selection.
- **Multi-metric gates**: require stability across multiple dimensions
  (correctness, runtime, token cost) rather than a single pass/fail.
- **Human override**: allow manual promotion/demotion via the dashboard
  (ties into the "Human-in-the-loop feedback interface" P3 item).

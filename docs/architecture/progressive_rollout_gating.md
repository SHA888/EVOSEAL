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
  └──────────┘    └─────┬────┘    └──────────────┘
                        │
                        │ regression
                        ▼
                   ┌──────────┐
                   │ rejected │
                   └──────────┘
```

- **candidate → beta**: the candidate passes the initial validation gate
  (`_validate_improvement`), exactly as today. At this point the change is
  applied to the working tree but tracked as beta.
- **beta → stable**: the candidate survives N consecutive evolution cycles
  without any regression being detected. N is configurable (default: 3).
- **beta → rejected**: a regression is detected during a subsequent cycle.
  The change is rolled back and recorded as rejected.

> **Note.** Rejection *before* the candidate stage (i.e. when
> `_validate_improvement` fails) is handled by the existing pipeline — no
> `RolloutCandidate` record is created, so it does not appear in the state
> machine above. The rollout state machine only tracks candidates that
> passed the initial gate.

### What "regression" means at each stage

| Stage | Regression signal |
|-------|-------------------|
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
    baseline_metrics: dict  # metrics snapshot at creation time
    checkpoint_path: str  # for rollback
    rejection_reason: str | None  # regression detail when stage is "rejected"
    rejected_at: datetime | None  # when the regression was detected
```

Every stage transition is timestamped (`created_at`, `promoted_to_beta_at`,
`promoted_to_stable_at`, `rejected_at`) so a candidate's full history can be
reconstructed from the registry alone — without this, a `rejected` record says
why it was rejected but not when, which makes post-hoc debugging of a
regression impossible to correlate with the cycle that caused it.

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
4. If regression: mark `rejected` (record the regression detail in
   `rejection_reason`). If `auto_rollback_on_regression` is `true`
   (§5/§6), roll back to the candidate's checkpoint; otherwise log the
   regression and leave the working tree unchanged for manual intervention.

> **Baseline scope.** `baseline_metrics` is captured once at candidate creation
> time (§4.1) and remains fixed for the entire beta observation window — it is
> *not* re-snapshotted each cycle. This means a candidate can accumulate N
> individually-clean cycles against the original baseline while the surrounding
> codebase drifts. The tradeoff is deliberate: a fixed baseline makes promotion
> decisions deterministic and independent of cycle ordering. The risk of
> cumulative drift is mitigated by the short default window (N=3) and by the
> fact that each cycle already runs the full regression suite. A rolling
> baseline would catch slow drift but would also make promotion non-deterministic
> (the same candidate could promote or regress depending on what else landed
> in the interim).

> **Concurrent beta candidates.** More than one candidate can occupy `beta` at
> the same time, and they are *not* isolated from each other: all candidates
> share a single working tree, and step 2 validates against the pipeline's
> shared metrics history rather than re-running each candidate's change in
> isolation. Two consequences follow, both deliberate for this first iteration:
>
> - **Attribution is approximate.** When several candidates are in `beta` and a
>   regression appears, every active beta candidate sees the same failing
>   comparison, so all of them are rejected — the design does not attempt to
>   identify which change actually caused it. This is fail-safe (a real
>   regression is never promoted) but not precise (innocent candidates are
>   rejected alongside the guilty one).
> - **Rollback is per-candidate, not layered.** Each candidate records its own
>   `checkpoint_path` captured before its change was applied. Restoring one
>   candidate's checkpoint therefore also discards any changes layered on top of
>   it by later candidates. With simultaneous betas this is a blunt instrument.
>
> The precise alternatives — serializing beta candidates one at a time, or a
> layered/patch-based checkpoint model that can revert a single change out of a
> stack — are deferred (§8). Deployments that need exact attribution should set
> `beta_cycles_required: 1` or otherwise keep at most one candidate in beta.

### 4.3 Bidirectional Manager

`BidirectionalEvolutionManager.run_loop_cycle()` should be aware of rollout
state. A model deployed from a `beta` candidate should be flagged as
pre-stable. The `prefer_stable_for_generation` flag (§5) controls whether the
generation surface prefers `stable` models for production workloads while
using `beta` models for experimentation — this section's "pre-stable" flag
is the implementation signal that flag consumes.

---

## 5. Configuration

Add to `configs/safety.yaml` (which already holds regression thresholds and checkpoint policy):

```yaml
rollout_gating:
  enabled: true
  beta_cycles_required: 3        # N: cycles a beta must survive
  auto_rollback_on_regression: true
  prefer_stable_for_generation: true  # generation uses stable model when available
```

**When `enabled` is `false`,** gating is bypassed end to end and the pipeline
behaves exactly as it does today: §4.1 registers no `RolloutCandidate` when
`_validate_improvement` accepts a change (it is adopted permanently in one
step), and §4.2's per-cycle beta check returns immediately without validating
or promoting anything. Candidates already recorded in the registry from a
previous run are left untouched — they are neither promoted nor rejected while
gating is off, and resume being checked if it is re-enabled.

---

## 6. Rollback

When a regression is detected at any stage:

1. Mark the candidate as `rejected`, recording the regression details in
   `rejection_reason` and the detection time in `rejected_at` (§3).
2. If `auto_rollback_on_regression` is `true` (§5), restore the checkpoint
   captured at candidate creation time. If the candidate was `beta`, the
   working tree reverts to the pre-candidate state — the N clean cycles it
   accumulated are discarded.
3. If `auto_rollback_on_regression` is `false`, log the regression and leave
   the working tree unchanged for manual intervention.

This leverages the existing `CheckpointManager` (fixed in PR #74 for path
traversal) and is consistent with the current rollback-on-failure pattern.
Note that with several candidates in `beta` simultaneously, restoring one
candidate's checkpoint also discards later candidates layered on top of it —
see the concurrency note in §4.2.

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
- **Per-candidate isolation**: serialize beta candidates, or adopt a
  layered/patch-based checkpoint model, so a regression can be attributed to
  and reverted from a single candidate without rejecting or discarding the
  others (§4.2).
- **Human override**: allow manual promotion/demotion via the dashboard
  (ties into the "Human-in-the-loop feedback interface" P3 item).

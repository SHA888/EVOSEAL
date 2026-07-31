# How EVOSEAL Actually Works

A step-by-step walkthrough of a single evolution cycle — from code analysis
through self-modification — with real code references and example output.

**Who this is for:** Contributors who want to understand the runtime flow
before reading source, and operators who want to know what happens when they
run `evoseal start evolution` or `evoseal pipeline run`.

---

## The Big Picture

EVOSEAL alternates between two phases:

1. **Solve a task** — generate code variants, test them, pick the best.
2. **Improve the pipeline** — use the results to fine-tune the model or
   adjust the pipeline itself.

A single cycle of Phase 1 is what `EvolutionPipeline.run_evolution_cycle()`
executes. Phase 2 is orchestrated by `ContinuousEvolutionService` and
`BidirectionalEvolutionManager` on a timer.

This tutorial covers **one Phase-1 cycle** end to end.

---

## Prerequisites

- EVOSEAL installed (`uv sync` from the repo root)
- API key configured in `.env` (or use `--dry-run` for mock responses)
- Submodules initialized if you want real DGM/OpenEvolve/SEAL integration
  (`git submodule update --init --recursive`)

For a zero-cost walkthrough, use dry-run mode:

```bash
evoseal pipeline run --dry-run
```

---

## Entry Points

There are two ways to trigger a cycle:

| Entry point | What it does |
|---|---|
| `evoseal pipeline run` | Runs one or more evolution iterations synchronously via the CLI |
| `evoseal start evolution` | Starts `ContinuousEvolutionService`, a long-running daemon that runs cycles on a timer and also monitors training readiness |

Both converge on the same core: `EvolutionPipeline.run_evolution_cycle()`.

---

## Step 1: Initialization

When the pipeline starts, it sets up the safety infrastructure first:

```
EvolutionPipeline.__init__
├── SafetyIntegration(config, repo_root=...)  # checkpoint + rollback + regression detection
├── MetricsTracker()                          # records fitness scores per iteration
├── ImprovementValidator()                    # compares before/after metrics
├── BudgetTracker()                           # enforces token/spend limits
└── IntegrationOrchestrator()                 # manages DGM/OpenEvolve/SEAL adapters
```

The safety layer is not optional — it gates every self-modification. If you
skip it, the pipeline will still run, but no improvement will ever be
validated (the validator needs metrics history to compare against).

**Key file:** `evoseal/core/evolution_pipeline.py` — `__init__`

---

## Step 2: The Iteration Loop

`run_evolution_cycle(iterations=N)` runs N iterations. Each iteration is
one pass through the full analyze → generate → adapt → evaluate → validate
pipeline:

```python
# Simplified illustration — see evolution_pipeline.py for the actual code
for i in range(iterations):
    iteration_result = await self._run_single_iteration(i + 1)
    results.append(iteration_result)

    if not iteration_result["should_continue"]:
        break  # stop early if no improvement found
```

**Key file:** `evoseal/core/evolution_pipeline.py` — `run_evolution_cycle`

---

## Step 3: Analyze the Current Version

```python
analysis = await self._analyze_current_version()
```

This step examines the current codebase state — what tests exist, what the
current fitness scores look like, and where the weakest points are. The
analysis result is a dict that feeds into the generation step.

In the current implementation, this step is a placeholder that returns `{}`
(the TODO for full analysis logic is noted in the source). The pipeline
still works because the generation step can operate without analysis context
when using OpenEvolve's built-in strategies.

**Key file:** `evoseal/core/evolution_pipeline.py` — `_analyze_current_version`

---

## Step 4: Generate Improvements

```python
improvements = await self._generate_improvements(analysis)
```

The pipeline method itself is a stub — the real work happens through
integration adapters. OpenEvolve (via the integration orchestrator) generates
code variants. Each variant is a candidate improvement — a modified version
of some part of the codebase.

The `Controller` class (`evoseal/core/controller.py`) provides an independent
inner loop for orchestrating test/evaluate/select cycles:

```
# Illustrative — see controller.py:run_generation for the real code
Controller.run_generation()
├── test_runner.run_tests(target)     # run tests against the candidate
├── evaluator.evaluate(test_results)  # score the candidate
└── select_candidates(eval_results)   # pick top-k for the next generation
```

Multiple generations of candidates may be produced within a single pipeline
iteration, depending on OpenEvolve's configuration.

**Key file:** `evoseal/core/controller.py` — `run_generation`

---

## Step 5: SEAL Adaptation

```python
adapted_improvements = await self._adapt_improvements(improvements)
```

The pipeline method itself is a passthrough — SEAL (Self-Adapting Language
Models) takes the raw improvements from OpenEvolve via the integration
adapter and adapts them, applying learned editing strategies to refine the
candidates. This is the "self-adapting" part of the system.

The adaptation strategies live in `evoseal/integration/seal/self_editor/strategies/`
and include code-style, documentation, and logic-focused strategies.

**Key file:** `evoseal/core/evolution_pipeline.py` — `_adapt_improvements`

---

## Step 6: Evaluate the New Version

```python
evaluation_result = await self._evaluate_version(adapted_improvements)
```

The pipeline method itself is a stub — the real evaluation happens through
the integration adapter. The adapted improvements are applied (or simulated,
in dry-run mode) and the result is scored. The evaluation runs the test
suite against the modified code and collects metrics: pass rate, fitness
score, runtime, etc.

The `SandboxedTestRunner` (`evoseal/core/testrunner.py`) runs tests in an
isolated environment:
- Strips API keys from the subprocess environment
- Makes `configs/safety.yaml` and `.env` read-only
- Enforces CPU time and memory limits
- Captures stdout/stderr for diagnostics

**Key file:** `evoseal/core/testrunner.py` — `SandboxedTestRunner`

---

## Step 7: Validate the Improvement

```python
is_improvement = await self._validate_improvement(evaluation_result)
```

This is the gate. The `ImprovementValidator` compares the current iteration's
metrics against the previous iteration's metrics. If the new version
regresses on any critical dimension, the improvement is rejected and the
cycle stops (`should_continue=False`).

```python
# Illustrative — see _validate_improvement for the real code
metrics = self.metrics_tracker.get_metrics_history(test_type)

if len(metrics) < 2:
    return True  # first iteration, nothing to compare against

result = self.validator.validate_improvement(baseline_id, comparison_id, test_type)
return result.passed
```

The `RegressionDetector` (`evoseal/core/regression_detector.py`) provides
configurable thresholds for what counts as a regression — not just raw
fitness, but also test pass rate, runtime, and memory usage.

**Key file:** `evoseal/core/evolution_pipeline.py` — `_validate_improvement`

---

## Step 8: Safety Wraparound (Optional)

The `run_evolution_cycle_with_safety` variant wraps each iteration with:

1. **Checkpoint** — snapshot the codebase before the iteration
2. **Run** — execute the iteration
3. **Detect regression** — compare metrics against the checkpoint
4. **Rollback** — if regression is detected, restore the checkpoint

```
# Illustrative flow — see run_evolution_cycle_with_safety for the real code
CheckpointManager.create_checkpoint()
→ run iteration
→ RegressionDetector.check_for_regression()
→ if regression: RollbackManager.rollback_to_checkpoint()
```

This is the mechanism that prevents a bad self-modification from corrupting
the system. The safety config lives in `configs/safety.yaml`.

**Key file:** `evoseal/core/safety_integration.py` — `SafetyIntegration`

---

## Step 9: Results and Events

Each iteration produces a result dict:

```python
{
    "iteration": 1,
    "success": True,
    "is_improvement": True,
    "metrics": {"fitness": 0.85, "pass_rate": 0.92},
    "should_continue": True,
    "resilience_status": {...},
}
```

Events are published at every stage boundary via the `EventBus`
(`evoseal/core/events.py`):

| Event | When |
|---|---|
| `EVOLUTION_STARTED` | Cycle begins |
| `ITERATION_STARTED` | Each iteration begins |
| `STAGE_STARTED` / `STAGE_COMPLETED` | Each pipeline stage |
| `ITERATION_COMPLETED` / `ITERATION_FAILED` | Each iteration ends |
| `EVOLUTION_COMPLETED` | Cycle ends |
| `ERROR_OCCURRED` | On any unrecovered error |

These events feed the monitoring dashboard (`evoseal/services/monitoring_dashboard.py`)
via WebSocket.

---

## Step 10: Continuous Loop (Daemon Mode)

When started via `evoseal start evolution`, the
`ContinuousEvolutionService` wraps the above in a long-running loop:

```
# Illustrative — see continuous_evolution_service.py for the real code
while not shutdown:
    await _run_evolution_cycle()          # Phase 1: evolve
    await asyncio.sleep(evolution_interval)

    if bidirectional_manager.should_train():
        await bidirectional_manager.run_loop_cycle()  # Phase 2: train + deploy
    await asyncio.sleep(training_check_interval)
```

Phase 2 (the bidirectional loop) involves:
1. Collect evolution results into training data
2. Fine-tune the model (LoRA/QLoRA)
3. Validate the fine-tuned model
4. Deploy the improved model
5. The next evolution cycle uses the improved model

This is the "bidirectional co-evolution" — evolution improves the model,
and the improved model produces better evolution candidates.

**Key file:** `evoseal/services/continuous_evolution_service.py`

---

## Resilience and Error Recovery

Every pipeline stage is wrapped with the resilience manager:

```python
analysis = await resilience_manager.execute_with_resilience(
    "pipeline", "analyze_version", self._analyze_current_version
)
```

This provides:
- **Circuit breakers** — if a component fails repeatedly, it's temporarily
  disabled to prevent cascading failures
- **Retry with backoff** — transient failures are retried with exponential
  delay
- **Error recovery** — `error_recovery_manager` attempts to recover from
  known failure patterns before giving up

**Key file:** `evoseal/core/resilience.py`

---

## What's Still TODO

Several pieces of the pipeline are stubbed with `# TODO` comments:

- `_analyze_current_version()` returns `{}`
- `_generate_improvements()` returns `[]` (the real generation logic lives in the OpenEvolve adapter — see `Controller.run_generation` for the test/evaluate/select loop)
- `_adapt_improvements()` is a passthrough (the real SEAL strategy application lives in the integration adapter)
- `_evaluate_version()` returns `{"metrics": {}}` (the real evaluation lives in the test runner adapter — `SandboxedTestRunner`)

The pipeline methods are coordination points, not the actual implementations.
The real logic lives in the integration adapters (DGM, OpenEvolve, SEAL),
which the resilience manager wraps at runtime (see Step 4-6 above for how
that works).

---

## Further Reading

- [Bidirectional Evolution Architecture](../architecture/bidirectional_evolution.md)
- [Self-Improvement Walkthrough](../examples/self_improvement_walkthrough.md)
- [Safety Overview](../safety/index.md)
- [Configuration Guide](../guides/CONFIGURATION.md)

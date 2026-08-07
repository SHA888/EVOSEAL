# ADR 0005 — Population-Based Training for Hyperparameter Evolution

**Status:** Proposed
**Date:** 2026-08-07
**Context:** EVOSEAL currently uses MAP-Elites (via OpenEvolve) for code variant
selection. The TODO roadmap calls for exploring Population-Based Training (PBT)
as an alternative to improve convergence speed for hyperparameter evolution.
This ADR evaluates whether PBT should complement or replace MAP-Elites for
specific workloads.

---

## 1. Context

EVOSEAL's evolution loop generates code variants, evaluates them, and selects
the best for the next generation. MAP-Elites (ADR 0002) handles *code variant
selection* — it maintains a quality-diversity archive across behavioral
dimensions. But EVOSEAL also needs to tune *pipeline hyperparameters* themselves:
mutation rates, selection pressure, evaluation weights, model temperature,
fitness function parameters, and so on.

Currently these hyperparameters are either:
- Fixed in configuration (manual tuning, no adaptation)
- Left to the user to set before each run

For hyperparameter tuning specifically, MAP-Elites is suboptimal: the
behavioral-characterization grid that makes it powerful for structural diversity
is ill-suited to continuous hyperparameter spaces where "behavioral distance" is
meaningless. A dedicated hyperparameter optimization strategy could converge
faster.

## 2. Decision

**Propose** PBT as a complementary strategy for hyperparameter evolution within
the evolution pipeline. MAP-Elites remains the primary selection mechanism for
code variants (unchanged). PBT would operate at the pipeline configuration
level, evolving hyperparameters across parallel runs.

## 3. What PBT Is

Population-Based Training (Jaderberg et al., 2017) combines:

1. **Parallel training** — a population of agents with different hyperparameters
   trains simultaneously.
2. **Periodic evaluation** — each agent is evaluated on a shared metric at
   regular intervals.
3. **Explore-exploit** — underperforming agents copy weights from top
   performers (*exploit*) and perturb their hyperparameters (*explore*).
4. **No separate search phase** — training and tuning happen simultaneously,
   eliminating the train-then-search overhead of grid/random/Bayesian methods.

The key insight: hyperparameters should change *during* training, not just
between runs. An agent that was best early may need different hyperparameters
later; PBT adapts continuously.

### PBT vs MAP-Elites: Different Problems

| Dimension | MAP-Elites | PBT |
|-----------|-----------|-----|
| **What it evolves** | Code variants (structural diversity) | Hyperparameters (continuous optimization) |
| **Diversity mechanism** | Behavioral grid (explicit niches) | Population diversity via perturbation |
| **Fitness landscape** | Discrete, high-dimensional | Continuous, low-dimensional |
| **Selection pressure** | Per-niche elitism | Global ranking with exploit/explore |
| **Convergence** | Slower (maintains coverage) | Faster (top performers propagate) |
| **Best for** | Exploring many structurally different solutions | Finding optimal configuration for a known structure |

These are **complementary**, not competing. MAP-Elites answers "which code
variants should survive?"; PBT answers "what hyperparameters should those
variants use?"

## 4. Where PBT Fits in EVOSEAL

### Scope: Pipeline Configuration, Not Code Selection

PBT would evolve EVOSEAL pipeline hyperparameters:

- **Mutation parameters:** rate, type weights, scope constraints
- **Selection parameters:** tournament size, elitism count, temperature
- **Evaluation parameters:** metric weights, pass/fail thresholds
- **Model parameters:** temperature, top-p, max tokens for generation
- **Safety parameters:** regression tolerance, rollback thresholds

It would **not** replace MAP-Elites for code variant selection — that remains
in OpenEvolve.

### Architecture Sketch

```
                    ┌──────────────────────┐
                    │   PBT Population      │
                    │  (N parallel configs) │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Evolution Pipeline   │
                    │  (each config runs    │
                    │   independently)      │
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Periodic Evaluation  │
                    │  (every K generations)│
                    └──────────┬───────────┘
                               │
                    ┌──────────▼───────────┐
                    │  Exploit/Explore      │
                    │  - Copy weights from  │
                    │    top performers     │
                    │  - Perturb params     │
                    └──────────────────────┘
```

### Implementation Path

If adopted, the integration points would be:

1. **`evoseal/core/evolution_pipeline.py`** — accept a `PBTConfig` alongside
   the existing pipeline config; run multiple pipeline instances in parallel
   with different hyperparameters.
2. **`evoseal/core/selection.py`** — add a PBT selection strategy (exploit from
   top performers, explore via perturbation) as a new strategy alongside
   tournament and roulette.
3. **`configs/pbt.yaml`** — PBT-specific configuration (population size,
   perturbation ranges, exploit interval, metric to rank on).
4. **Checkpoint integration** — PBT requires checkpointing entire pipeline
   state (including model weights) for exploit (copying from top performers);
   `CheckpointManager` already handles this.
5. **`evoseal/cli/commands/`** — a `pbt` subcommand to run PBT-tuned
   evolution sessions.

## 5. Trade-offs

### Why PBT Could Improve Convergence

- **No wasted compute** — unlike grid/random search, PBT never runs
  underperforming configs to completion; it prunes them mid-run.
- **Adaptive** — hyperparameters change as the fitness landscape shifts across
  generations, rather than being fixed for an entire run.
- **Works with small populations** — Jaderberg et al. demonstrated effective
  results with populations of 10-50 agents, well within EVOSEAL's budget.

### Why It May Not Be Worth It Now

- **Parallelism requirement** — PBT needs N parallel pipeline runs, each with
  its own model inference. This multiplies API costs by N (or requires local
  models, which aren't yet fully validated end-to-end per TODO item "Add support
  for local models").
- **Checkpointing overhead** — exploit requires serializing and transferring
  full pipeline state (including model weights). `CheckpointManager` exists but
  hasn't been benchmarked for this workload.
- **Complexity** — adds a new orchestration layer on top of the already complex
  evolution pipeline. The bidirectional co-evolution loop (items 4-6) must be
  stable first.
- **Diminishing returns for code evolution** — PBT's advantage is strongest
  when hyperparameters interact with training dynamics (e.g., learning rate
  schedules). For EVOSEAL's discrete code generation, the hyperparameter space
  is smaller and may not justify the overhead.

### Open Questions

1. **What's the cost multiplier?** Running N=10 parallel pipelines with
   different configs multiplies LLM API costs. Is this acceptable, or does PBT
   only make sense with local models?
2. **Which hyperparameters actually matter?** A sensitivity analysis of
   EVOSEAL's config parameters would tell us whether there's enough tunable
   surface to justify PBT.
3. **Can we start simpler?** Before full PBT, could we run a small-scale
   experiment: 3-5 parallel pipelines with different configs for 10 generations,
   measure variance in outcomes, and decide if the spread is large enough to
   warrant adaptive tuning?

## 6. Recommendation

**Do not implement PBT now.** The prerequisites aren't in place:

1. Local model support must work end-to-end (otherwise the N× cost multiplier
   is prohibitive).
2. The bidirectional co-evolution loop (items 4-6, now complete) must prove
   stable across multiple runs before adding another optimization layer.
3. A sensitivity analysis of pipeline hyperparameters should confirm that the
   tunable surface is large enough to justify PBT's complexity.

**Instead, run a feasibility spike first:** configure 3-5 parallel pipeline runs
with manually varied hyperparameters (mutation rate, selection pressure,
temperature), run for 10 generations each, and measure outcome variance. If
the variance is meaningful (>10% fitness spread), PBT is justified. If not,
the hyperparameter space may be too narrow to warrant the overhead.

### Recommended Next Steps

1. **Document the hyperparameter space** — enumerate all tuneable pipeline
   parameters and their current values/ranges.
2. **Run a feasibility spike** (use the `spike` skill) — parallel runs with
   varied configs, measure outcome spread.
3. **If justified:** write a PBT implementation design doc with concrete
   integration points, cost model, and checkpoint strategy.
4. **If not justified:** close this item as "explored, not worth the complexity
   given current hyperparameter sensitivity."

## 7. References

- Jaderberg, M., et al. (2017). *Population Based Training of Neural Networks.*
  arXiv:1711.09846.
- Mouret, J.-B. & Clune, J. (2015). *Illuminating Search Spaces by Mapping
  Elites.* arXiv:1504.04909.
- [`docs/adr/0002-map-elites-selection.md`](0002-map-elites-selection.md) —
  MAP-Elites decision for code variant selection.
- [`docs/architecture/overview.md`](../architecture/overview.md) — EVOSEAL
  architecture overview.
- `evoseal/core/selection.py` — current selection implementation (tournament,
  roulette).

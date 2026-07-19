# ADR 0002 — MAP-Elites for candidate selection

**Status:** Accepted
**Date:** 2026-07-19
**Context:** EVOSEAL needs a strategy for selecting which code variants survive
across generations. The choice of selection algorithm directly affects convergence
speed, solution diversity, and the risk of premature convergence.

---

## 1. Context

EVOSEAL generates multiple code variants per generation and must decide which
ones carry forward. The two fundamental tensions are:

- **Exploitation** — keep the highest-fitness variants to converge quickly.
- **Exploration** — maintain diverse variants to avoid getting stuck in local
  optima.

Classical evolutionary strategies (tournament selection, roulette wheel,
elitism) lean toward exploitation. Pure random selection preserves diversity but
ignores fitness. EVOSEAL needs a strategy that balances both, because
self-modifying code can easily converge to a local optimum (a pipeline that
"works" but is worse than alternatives it never explored).

## 2. Decision

Use **MAP-Elites** (Multi-dimensional Archive of Phenotypic Elites), a
quality-diversity algorithm, as the primary selection mechanism in OpenEvolve.

## 3. Rationale

### Why MAP-Elites over alternatives

| Alternative | Limitation | MAP-Elites advantage |
|-------------|-----------|---------------------|
| Tournament selection | Converges fast, loses diversity | MAP-Elites maintains an archive of elites across behavioral dimensions |
| Roulette wheel | Fitness-proportional, still converges | MAP-Elites decouples fitness from behavioral characterization |
| NSGA-II (multi-objective) | Pareto front doesn't guarantee coverage | MAP-Elites fills a behavioral grid, ensuring broad exploration |
| Random selection | Ignores fitness entirely | MAP-Elites selects the best *within each niche* |

### Why quality-diversity matters for self-modification

In a self-modifying system, premature convergence is particularly dangerous:
the system may lock into a suboptimal pipeline configuration and lose the
ability to explore alternatives. MAP-Elites addresses this by:

1. **Behavioral characterization** — variants are placed in a grid based on
   behavioral features (not just fitness), so structurally different solutions
   coexist.
2. **Elitism within niches** — the best variant in each niche survives,
   preserving both quality and diversity.
3. **No explicit diversity penalty** — unlike NSGA-II, diversity is structural
   (the grid) rather than a secondary objective to optimize.

### What MAP-Elites is *not*

- It is not a replacement for the fitness function — it organizes *how* fitness
  is applied, not what fitness measures.
- It does not guarantee global optima — it improves coverage, not convergence
  speed in the limit.
- It adds complexity (grid design, behavioral characterization) that simpler
  strategies avoid.

## 4. Consequences

- **Positive:** Broader exploration of the variant space; reduced risk of
  premature convergence; the archive itself is a useful artifact for analyzing
  what the system explored.
- **Negative:** Grid design requires choosing behavioral dimensions, which is
  problem-dependent and non-trivial. Archive memory grows with grid resolution.
- **Neutral:** MAP-Elites is implemented in OpenEvolve; EVOSEAL wraps it via
  the integration layer.

## 5. References

- Mouret, J.-B. & Clune, J. (2015). *Illuminating Search Spaces by Mapping
  Elites.* arXiv:1504.04909.
- [`docs/architecture/overview.md`](../architecture/overview.md) — OpenEvolve
  component description.
- [`evoseal/core/selection.py`](https://github.com/SHA888/EVOSEAL/blob/main/evoseal/core/selection.py) — EVOSEAL's
  selection wrapper.

# PBT Feasibility Spike

## Question

Does varying EVOSEAL's pipeline hyperparameters (tournament size, elitism,
mutation rate/magnitude) produce meaningful outcome differences across parallel
runs? If so, Population-Based Training (PBT) is justified as a complementary
hyperparameter optimization strategy.

## Threshold (ADR 0005 §6)

> If the variance is meaningful (>10% fitness spread), PBT is justified. If
> not, the hyperparameter space may be too narrow to warrant the overhead.

## Method

- **Synthetic population** of 50 individuals with 3-dimensional fitness scores
  drawn from N(0.5, 0.15), clamped to [0, 1].
- **5 hyperparameter configs** tested (baseline, exploratory, exploitative,
  balanced, conservative) — each with 5 random seeds.
- **10 generations** of tournament selection + Gaussian perturbation per run.
- **Metrics tracked:** best fitness, average fitness, diversity (std dev), and
  improvement (delta from gen 0 to gen 10).
- **Cross-config spread:** max(best_fitness_mean) − min(best_fitness_mean)
  across configs, expressed as % of overall mean.

## Results

| Config | Tournament | Elitism | Mut Rate | Mut Mag | Final Best | Improvement |
|--------|-----------|---------|----------|---------|------------|-------------|
| baseline | 3 | 1 | 0.10 | 0.05 | 0.708 ± 0.039 | +0.025 |
| exploratory | 2 | 0 | 0.30 | 0.15 | 0.848 ± 0.066 | +0.165 |
| exploitative | 7 | 3 | 0.05 | 0.02 | 0.680 ± 0.022 | −0.003 |
| balanced | 4 | 2 | 0.15 | 0.08 | 0.744 ± 0.058 | +0.061 |
| conservative | 3 | 5 | 0.05 | 0.03 | 0.686 ± 0.030 | +0.003 |

**Cross-config spread:**
- Best fitness: 0.168 (**22.9%**) — exceeds 10% threshold ✓
- Average fitness: 0.012 (2.3%) — below threshold (expected: population average is less sensitive)
- Improvement spread: 0.168

## Verdict: VALIDATED

Hyperparameter variance produces meaningful outcome differences in the
pipeline's selection/mutation mechanics. The 22.9% best-fitness spread across
configs is more than double the 10% threshold.

**Key finding:** The "exploratory" config (small tournament, no elitism, high
mutation) achieved 24.7% higher best fitness than "exploitative" — but with
2.5× more variance. This is exactly the explore-exploit tradeoff that PBT is
designed to navigate adaptively.

### Caveats

1. This spike uses synthetic fitness landscapes, not real LLM-generated code
   variants. Real fitness landscapes may be more or less sensitive to
   hyperparameter changes.
2. The spike tests selection + mutation only. It does not exercise the full
   pipeline (generation, evaluation, self-modification).
3. EVOSEAL's real fitness function involves code correctness, efficiency, and
   readability — multi-dimensional in a way that may amplify or dampen
   hyperparameter sensitivity.

## Recommendation

Proceed to a PBT implementation design doc with:
- Concrete integration points (where PBT hooks into the evolution loop)
- Cost model (N× parallel runs vs. convergence speedup)
- Checkpoint strategy (how to save/restore PBT population state)

### Next steps (if proceeding)
1. Run a second spike with real LLM calls (requires API keys) to validate
   synthetic-fitness transferability.
2. Design doc covering PBT integration with `ContinuousEvolutionService`.
3. Prototype PBT as a thin wrapper around the existing `EvolutionPipeline`.

## Files

- `spike.py` — the spike script (standalone, no external deps)
- `results.json` — raw numerical results
- `README.md` — this file

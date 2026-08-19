#!/usr/bin/env python3
"""
PBT Feasibility Spike — measures whether hyperparameter variance produces
meaningful outcome differences in EVOSEAL's pipeline.

Verdict threshold (from ADR 0005 §6): >10% fitness spread across configs
justifies PBT; otherwise the hyperparameter space is too narrow.

This spike exercises the selection + perturbation loop with synthetic fitness
landscapes, varying tournament_size, elitism, and mutation magnitude.  It does
NOT require API keys or real LLM calls — the question is purely whether the
pipeline's internal hyperparameters create enough outcome variance to warrant
adaptive tuning.

Usage:
    python spikes/pbt-feasibility/spike.py
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

POPULATION_SIZE = 50
GENERATIONS = 10
RUNS_PER_CONFIG = 5  # repetitions with different seeds for each config
INITIAL_FITNESS_MEAN = 0.5
INITIAL_FITNESS_STD = 0.15
FITNESS_DIMENSIONS = 3  # multi-dimensional fitness

# Hyperparameter grid — each dict is one "config"
CONFIGS: list[dict[str, Any]] = [
    # Baseline (current defaults)
    {
        "name": "baseline",
        "tournament_size": 3,
        "elitism": 1,
        "mutation_rate": 0.1,
        "mutation_mag": 0.05,
    },
    # Small tournament, high mutation — more exploration
    {
        "name": "exploratory",
        "tournament_size": 2,
        "elitism": 0,
        "mutation_rate": 0.3,
        "mutation_mag": 0.15,
    },
    # Large tournament, low mutation — more exploitation
    {
        "name": "exploitative",
        "tournament_size": 7,
        "elitism": 3,
        "mutation_rate": 0.05,
        "mutation_mag": 0.02,
    },
    # Moderate — balanced
    {
        "name": "balanced",
        "tournament_size": 4,
        "elitism": 2,
        "mutation_rate": 0.15,
        "mutation_mag": 0.08,
    },
    # High elitism — conservative
    {
        "name": "conservative",
        "tournament_size": 3,
        "elitism": 5,
        "mutation_rate": 0.05,
        "mutation_mag": 0.03,
    },
]

SEED_BASE = 42


# ---------------------------------------------------------------------------
# Core mechanics (selection mirrors evoseal/core/selection.py logic, but
# deterministic via explicit rng; mutation loop is spike-only — production
# uses self_improve_step which has different semantics).
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class Individual:
    """Synthetic individual with multi-dimensional fitness.

    eq=False so that ``in`` and ``.remove()`` compare by object identity,
    not by value.  Two distinct individuals can share the same ``id`` and
    ``fitness`` (e.g. via the fill-when-undersized fallback in
    ``tournament_select``); value-based equality would silently collapse
    them and corrupt the selection pool.
    """

    id: int
    fitness: list[float]  # per-dimension fitness scores

    @property
    def aggregate_fitness(self) -> float:
        """Weighted sum of fitness dimensions (equal weights)."""
        return sum(self.fitness) / len(self.fitness)


def generate_population(size: int, rng: random.Random) -> list[Individual]:
    """Create a synthetic population with normally-distributed fitness."""
    pop = []
    for i in range(size):
        fitness = [
            max(0.0, min(1.0, rng.gauss(INITIAL_FITNESS_MEAN, INITIAL_FITNESS_STD)))
            for _ in range(FITNESS_DIMENSIONS)
        ]
        pop.append(Individual(id=i, fitness=fitness))
    return pop


def tournament_select(
    population: list[Individual],
    n: int,
    tournament_size: int,
    elitism: int,
    rng: random.Random,
) -> list[Individual]:
    """Tournament selection with elitism (deterministic via rng)."""
    selected: list[Individual] = []
    pop = population[:]

    # Elitism: preserve top-N
    if elitism > 0:
        sorted_pop = sorted(pop, key=lambda x: x.aggregate_fitness, reverse=True)
        elites = sorted_pop[:elitism]
        selected.extend(elites)
        pop = [ind for ind in pop if ind not in elites]

    while len(selected) < n and pop:
        indices = rng.sample(range(len(pop)), min(tournament_size, len(pop)))
        tournament = [pop[i] for i in indices]
        winner = max(tournament, key=lambda x: x.aggregate_fitness)
        selected.append(winner)
        pop.remove(winner)

    # Fill if needed (guard against empty pool — e.g. elitism=0 with
    # an empty starting population, or n=0 reuse elsewhere).
    # Duplicates are possible here (same Individual reference appended
    # multiple times).  This is benign because mutate() always creates a
    # new Individual object for non-elites, so the next generation still
    # has distinct objects.  With the current configs (POPULATION_SIZE=50,
    # elitism<=5) the fill path is extremely unlikely to trigger.
    if selected:
        while len(selected) < n:
            selected.append(rng.choice(selected))

    return selected[:n]


def mutate(
    individual: Individual,
    mutation_rate: float,
    mutation_mag: float,
    rng: random.Random,
) -> Individual:
    """Perturb fitness dimensions to simulate mutation effect."""
    new_fitness = []
    for f in individual.fitness:
        if rng.random() < mutation_rate:
            delta = rng.gauss(0, mutation_mag)
            new_fitness.append(max(0.0, min(1.0, f + delta)))
        else:
            new_fitness.append(f)
    return Individual(id=individual.id, fitness=new_fitness)


def run_generation(
    population: list[Individual],
    config: dict[str, Any],
    rng: random.Random,
) -> list[Individual]:
    """One generation: select → mutate → return next generation.

    Elites survive unchanged — only non-elite selected individuals are
    mutated.  This preserves the standard elitism guarantee that the best
    fitness is non-decreasing across generations.
    """
    elitism = config["elitism"]
    # Selection — relies on tournament_select returning elites as the
    # first ``elitism`` entries (preserved unmutated below).
    selected = tournament_select(
        population,
        n=len(population),
        tournament_size=config["tournament_size"],
        elitism=elitism,
        rng=rng,
    )
    # Elites pass through unchanged; the rest are mutated.
    elites = selected[:elitism]
    rest = selected[elitism:]
    next_gen = elites + [
        mutate(ind, config["mutation_rate"], config["mutation_mag"], rng) for ind in rest
    ]
    return next_gen


# ---------------------------------------------------------------------------
# Spike runner
# ---------------------------------------------------------------------------


@dataclass
class RunResult:
    """Results from one run of one config."""

    config_name: str
    seed: int
    best_fitness_per_gen: list[float] = field(default_factory=list)
    avg_fitness_per_gen: list[float] = field(default_factory=list)
    diversity_per_gen: list[float] = field(default_factory=list)

    @property
    def final_best(self) -> float:
        return self.best_fitness_per_gen[-1] if self.best_fitness_per_gen else 0.0

    @property
    def final_avg(self) -> float:
        return self.avg_fitness_per_gen[-1] if self.avg_fitness_per_gen else 0.0

    @property
    def improvement(self) -> float:
        """Best fitness improvement over generations."""
        if len(self.best_fitness_per_gen) < 2:
            return 0.0
        return self.best_fitness_per_gen[-1] - self.best_fitness_per_gen[0]


def run_single(config: dict[str, Any], seed: int) -> RunResult:
    """Run one full evolution with a given config and seed."""
    rng = random.Random(seed)
    pop = generate_population(POPULATION_SIZE, rng)
    result = RunResult(config_name=config["name"], seed=seed)

    for gen in range(GENERATIONS):
        best = max(ind.aggregate_fitness for ind in pop)
        avg = statistics.mean(ind.aggregate_fitness for ind in pop)
        # Diversity: std dev of aggregate fitness
        diversity = statistics.stdev(ind.aggregate_fitness for ind in pop) if len(pop) > 1 else 0.0

        result.best_fitness_per_gen.append(best)
        result.avg_fitness_per_gen.append(avg)
        result.diversity_per_gen.append(diversity)

        pop = run_generation(pop, config, rng)

    # Record final generation stats
    best = max(ind.aggregate_fitness for ind in pop)
    avg = statistics.mean(ind.aggregate_fitness for ind in pop)
    diversity = statistics.stdev(ind.aggregate_fitness for ind in pop) if len(pop) > 1 else 0.0
    result.best_fitness_per_gen.append(best)
    result.avg_fitness_per_gen.append(avg)
    result.diversity_per_gen.append(diversity)

    return result


def run_spike() -> dict[str, Any]:
    """Run the full spike across all configs and seeds."""
    all_results: list[RunResult] = []

    for config in CONFIGS:
        for run_idx in range(RUNS_PER_CONFIG):
            seed = SEED_BASE + run_idx
            result = run_single(config, seed)
            all_results.append(result)

    # Aggregate by config
    config_stats: dict[str, dict[str, Any]] = {}
    for config in CONFIGS:
        name = config["name"]
        results = [r for r in all_results if r.config_name == name]
        final_bests = [r.final_best for r in results]
        final_avgs = [r.final_avg for r in results]
        improvements = [r.improvement for r in results]
        final_diversities = [r.diversity_per_gen[-1] for r in results]

        config_stats[name] = {
            "config": config,
            "final_best_mean": statistics.mean(final_bests),
            "final_best_std": statistics.stdev(final_bests) if len(final_bests) > 1 else 0.0,
            "final_avg_mean": statistics.mean(final_avgs),
            "final_avg_std": statistics.stdev(final_avgs) if len(final_avgs) > 1 else 0.0,
            "improvement_mean": statistics.mean(improvements),
            "improvement_std": statistics.stdev(improvements) if len(improvements) > 1 else 0.0,
            "final_diversity_mean": statistics.mean(final_diversities),
        }

    # Cross-config spread
    best_means = [s["final_best_mean"] for s in config_stats.values()]
    avg_means = [s["final_avg_mean"] for s in config_stats.values()]
    improvement_means = [s["improvement_mean"] for s in config_stats.values()]

    best_spread = max(best_means) - min(best_means)
    avg_spread = max(avg_means) - min(avg_means)
    improvement_spread = max(improvement_means) - min(improvement_means)

    # Relative spreads (as % of the mean)
    best_mean_overall = statistics.mean(best_means)
    avg_mean_overall = statistics.mean(avg_means)

    best_relative_spread = (best_spread / best_mean_overall * 100) if best_mean_overall > 0 else 0
    avg_relative_spread = (avg_spread / avg_mean_overall * 100) if avg_mean_overall > 0 else 0

    return {
        "config_stats": config_stats,
        "cross_config": {
            "best_spread": best_spread,
            "avg_spread": avg_spread,
            "improvement_spread": improvement_spread,
            "best_relative_spread_pct": best_relative_spread,
            "avg_relative_spread_pct": avg_relative_spread,
        },
        "threshold": 10.0,  # ADR 0005 §6 threshold
    }


def print_report(results: dict[str, Any]) -> None:
    """Print a human-readable report."""
    cross = results["cross_config"]
    threshold = results["threshold"]

    print("=" * 70)
    print("PBT FEASIBILITY SPIKE — RESULTS")
    print("=" * 70)
    print()
    print(f"Population size: {POPULATION_SIZE}")
    print(f"Generations: {GENERATIONS}")
    print(f"Runs per config: {RUNS_PER_CONFIG}")
    print(f"Configs tested: {len(CONFIGS)}")
    print(f"Fitness dimensions: {FITNESS_DIMENSIONS}")
    print()

    print("PER-CONFIG RESULTS:")
    print("-" * 70)
    for name, stats in results["config_stats"].items():
        cfg = stats["config"]
        print(f"\n  [{name}]")
        print(
            f"    tournament_size={cfg['tournament_size']}, elitism={cfg['elitism']}, "
            f"mutation_rate={cfg['mutation_rate']}, mutation_mag={cfg['mutation_mag']}"
        )
        print(
            f"    Final best fitness: {stats['final_best_mean']:.4f} ± {stats['final_best_std']:.4f}"
        )
        print(
            f"    Final avg fitness:  {stats['final_avg_mean']:.4f} ± {stats['final_avg_std']:.4f}"
        )
        print(
            f"    Improvement:        {stats['improvement_mean']:.4f} ± {stats['improvement_std']:.4f}"
        )
        print(f"    Final diversity:    {stats['final_diversity_mean']:.4f}")

    print()
    print("CROSS-CONFIG SPREAD:")
    print("-" * 70)
    print(
        f"  Best fitness spread:       {cross['best_spread']:.4f} ({cross['best_relative_spread_pct']:.1f}%)"
    )
    print(
        f"  Average fitness spread:    {cross['avg_spread']:.4f} ({cross['avg_relative_spread_pct']:.1f}%)"
    )
    print(f"  Improvement spread:        {cross['improvement_spread']:.4f}")
    print()

    # Verdict
    # NOTE: Using ``or`` (either metric crossing threshold) as the VALIDATED
    # gate.  Best-fitness is a max-order statistic and inherently noisier
    # across small samples (n=5 seeds/config) than the population average.
    # A stricter gate would require a significance test (e.g. t-test or CI)
    # against the per-config std devs before drawing a conclusion.  The
    # current threshold is intentionally permissive — the spike answers
    # "is there *any* signal?" rather than "is the signal statistically
    # robust?"  Treat the VALIDATED verdict as directional, not definitive.
    best_pct = cross["best_relative_spread_pct"]
    avg_pct = cross["avg_relative_spread_pct"]
    exceeds = best_pct > threshold or avg_pct > threshold

    print("VERDICT:")
    print("-" * 70)
    if exceeds:
        verdict = "VALIDATED"
        recommendation = (
            "Hyperparameter variance produces meaningful outcome differences "
            f"(best spread {best_pct:.1f}% / avg spread {avg_pct:.1f}% > {threshold}% threshold). "
            "PBT is justified — proceed to design doc with concrete integration points."
        )
    else:
        verdict = "INVALIDATED"
        recommendation = (
            f"Hyperparameter spread is below {threshold}% threshold "
            f"(best {best_pct:.1f}%, avg {avg_pct:.1f}%). "
            "The current hyperparameter space may be too narrow for PBT to add value. "
            "Consider: (1) expanding the tunable surface, (2) testing on real LLM-generated "
            "fitness landscapes where mutation quality varies more, or (3) closing this item "
            "as 'explored, not worth the complexity'."
        )

    print(f"  {verdict}")
    print(f"  {recommendation}")
    print()


def main() -> None:
    results = run_spike()
    print_report(results)

    # Write raw results to JSON
    output_path = Path(__file__).parent / "results.json"
    # Convert to serializable form
    serializable = {
        "cross_config": results["cross_config"],
        "threshold": results["threshold"],
        "config_stats": {},
    }
    for name, stats in results["config_stats"].items():
        serializable["config_stats"][name] = {k: v for k, v in stats.items() if k != "config"}
        serializable["config_stats"][name]["config"] = {
            k: v for k, v in stats["config"].items() if k != "name"
        }

    with open(output_path, "w") as f:
        json.dump(serializable, f, indent=2)
    print(f"Raw results written to: {output_path}")


if __name__ == "__main__":
    main()

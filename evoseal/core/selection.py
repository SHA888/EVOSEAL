"""
SelectionAlgorithm for choosing code variants for the next generation.

Supports tournament, roulette wheel, and pluggable strategies with diversity options.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol, TypeVar

# Type variables for generic types
T = TypeVar("T")
Individual = dict[str, Any]
Population = list[Individual]

# Constants
DEFAULT_TOURNAMENT_SIZE = 3
DEFAULT_ELITISM = 1

# Configure logger
logger = logging.getLogger(__name__)


class SelectionAlgorithm:
    def __init__(self, strategies: dict[str, Callable[..., Any]] | None = None) -> None:
        self.strategies = strategies or {
            "tournament": self.tournament_selection,
            "roulette": self.roulette_wheel_selection,
        }

    def select(
        self,
        population: list[dict[str, Any]],
        num_selected: int,
        strategy: str = "tournament",
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """
        Select num_selected individuals from population using the given strategy.
        """
        if strategy not in self.strategies:
            raise ValueError(f"Unknown selection strategy: {strategy}")
        return list(self.strategies[strategy](population, num_selected, **kwargs))

    def tournament_selection(  # noqa: PLR0913
        self,
        population: list[dict[str, Any]],
        num_selected: int,
        tournament_size: int = DEFAULT_TOURNAMENT_SIZE,
        elitism: int = DEFAULT_ELITISM,
        fitness_key: str = "eval_score",
    ) -> list[dict[str, Any]]:
        """
        Select individuals via tournament selection with optional elitism.
        """
        selected: list[dict[str, Any]] = []
        pop = population[:]
        # Elitism: always select top N first
        if elitism > 0:
            sorted_pop = sorted(pop, key=lambda x: x.get(fitness_key, 0), reverse=True)
            elites = sorted_pop[:elitism]
            selected.extend(elites)
            # Remove elites from pool for further selection
            pop = [ind for ind in pop if ind not in elites]
        while len(selected) < num_selected and pop:
            tournament = random.sample(pop, min(tournament_size, len(pop)))
            winner = max(tournament, key=lambda x: x.get(fitness_key, 0))
            selected.append(winner)
            pop.remove(winner)
        # If not enough unique individuals, fill with randoms (with possible repeats)
        while len(selected) < num_selected:
            selected.append(random.choice(selected))
        return list(selected[:num_selected])

    def roulette_wheel_selection(
        self,
        population: list[dict[str, Any]],
        num_selected: int,
        fitness_key: str = "eval_score",
        elitism: int = DEFAULT_ELITISM,
    ) -> list[dict[str, Any]]:
        """
        Select individuals via roulette wheel (fitness-proportionate) selection.
        """
        selected: list[dict[str, Any]] = []
        pop = population[:]
        # Elitism: always select top N first
        if elitism > 0:
            sorted_pop = sorted(pop, key=lambda x: x.get(fitness_key, 0), reverse=True)
            elites = sorted_pop[:elitism]
            selected.extend(elites)
            pop = [ind for ind in pop if ind not in elites]
        fitnesses = [max(0.0, x.get(fitness_key, 0)) for x in pop]
        total_fitness = sum(fitnesses)
        if total_fitness == 0 and pop:
            selected.extend(random.sample(pop, min(num_selected - len(selected), len(pop))))
            # If still not enough, fill with randoms from selected
            while len(selected) < num_selected:
                selected.append(random.choice(selected))
            return list(selected[:num_selected])
        for _ in range(num_selected - len(selected)):
            pick = random.uniform(0, total_fitness)
            current = 0
            for ind, fit in zip(pop, fitnesses):
                current += fit
                if current >= pick:
                    selected.append(ind)
                    pop.remove(ind)
                    fitnesses = [max(0.0, x.get(fitness_key, 0)) for x in pop]
                    total_fitness = sum(fitnesses)
                    break
            else:
                # fallback in case of rounding errors
                if pop:
                    selected.append(pop[-1])
                    pop.pop()
        while len(selected) < num_selected:
            selected.append(random.choice(selected))
        return list(selected[:num_selected])

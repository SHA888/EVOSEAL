"""
SelectionAlgorithm for choosing code variants for the next generation.

Supports tournament, roulette wheel, and pluggable strategies with diversity options.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol, TypeVar

# Type variables for generic types
T = TypeVar("T")
Individual = Dict[str, Any]
Population = List[Individual]

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

    def tournament_selection(
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
            # Using secrets for sampling to ensure secure random selection
            tournament = [
                pop[i]
                for i in sorted(
                    secrets.SystemRandom().sample(range(len(pop)), min(tournament_size, len(pop)))
                )
            ]
            winner = max(tournament, key=lambda x: x.get(fitness_key, 0))
            selected.append(winner)
            pop.remove(winner)
        # If not enough unique individuals, fill with randoms (with possible repeats)
        while len(selected) < num_selected:
            selected.append(secrets.SystemRandom().choice(selected))
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
        Optimized version with O(n log n) complexity using binary search.
        """
        selected: list[dict[str, Any]] = []
        pop = population[:]
        
        # Elitism: always select top N first
        if elitism > 0:
            sorted_pop = sorted(pop, key=lambda x: x.get(fitness_key, 0), reverse=True)
            elites = sorted_pop[:elitism]
            selected.extend(elites)
            # Remove elites from pool for further selection using set for O(1) lookup
            elite_ids = {id(elite) for elite in elites}
            pop = [ind for ind in pop if id(ind) not in elite_ids]

        if not pop:
            while len(selected) < num_selected:
                selected.append(secrets.SystemRandom().choice(selected))
            return list(selected[:num_selected])

        fitnesses = [max(0.0, x.get(fitness_key, 0)) for x in pop]
        total_fitness = sum(fitnesses)
        
        if total_fitness == 0:
            # All fitness values are zero, use random selection
            sample_size = min(num_selected - len(selected), len(pop))
            selected.extend(
                [pop[i] for i in sorted(secrets.SystemRandom().sample(range(len(pop)), sample_size))]
            )
            while len(selected) < num_selected:
                selected.append(secrets.SystemRandom().choice(selected))
            return list(selected[:num_selected])

        # Create cumulative fitness distribution for efficient selection
        cumulative_fitness = []
        cumsum = 0
        for fitness in fitnesses:
            cumsum += fitness
            cumulative_fitness.append(cumsum)

        # Select individuals using binary search on cumulative distribution
        remaining_selections = num_selected - len(selected)
        selected_indices = set()
        
        for _ in range(remaining_selections):
            if len(selected_indices) >= len(pop):
                break
                
            pick = secrets.SystemRandom().uniform(0, total_fitness)
            
            left, right = 0, len(cumulative_fitness) - 1
            while left < right:
                mid = (left + right) // 2
                if cumulative_fitness[mid] < pick:
                    left = mid + 1
                else:
                    right = mid
            
            original_left = left
            while left in selected_indices and left < len(pop) - 1:
                left += 1
            if left in selected_indices:
                left = 0
                while left in selected_indices and left < original_left:
                    left += 1
            
            if left < len(pop) and left not in selected_indices:
                selected.append(pop[left])
                selected_indices.add(left)

        while len(selected) < num_selected:
            selected.append(secrets.SystemRandom().choice(selected))
            
        return list(selected[:num_selected])

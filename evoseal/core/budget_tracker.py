"""Token and cost tracking for evolution cycles.

Accumulates token usage from DGM, SEAL, and fine-tuning operations
and provides cost estimation and budget tracking.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CycleRecord:
    """Record of token consumption for a single cycle."""

    cycle_number: int
    tokens: int
    dgm_tokens: int = 0
    seal_tokens: int = 0


@dataclass
class FinetuningRecord:
    """Record of token consumption for a fine-tuning checkpoint."""

    checkpoint_number: int
    tokens: int
    timestamp: str = ""


class BudgetTracker:
    """Tracks token consumption and costs across evolution cycles."""

    def __init__(self) -> None:
        """Initialize the budget tracker."""
        self.tokens_consumed_this_run = 0
        self.cycle_count = 0
        self.fine_tuning_count = 0
        self.cycle_history: list[dict[str, Any]] = []
        self.fine_tuning_history: list[dict[str, Any]] = []
        self._current_cycle_dgm_tokens = 0
        self._current_cycle_seal_tokens = 0

    def record_dgm_tokens(self, tokens: int) -> None:
        """Record tokens consumed by a DGM call.

        Args:
            tokens: Number of tokens consumed.
        """
        self.tokens_consumed_this_run += tokens
        self._current_cycle_dgm_tokens += tokens

    def record_seal_tokens(self, tokens: int) -> None:
        """Record tokens consumed by a SEAL operation.

        Args:
            tokens: Number of tokens consumed.
        """
        self.tokens_consumed_this_run += tokens
        self._current_cycle_seal_tokens += tokens

    def record_cycle_completion(self) -> None:
        """Record the completion of an evolution cycle.

        Finalizes token counts for the current cycle and resets accumulators.
        """
        self.cycle_count += 1
        cycle_total = self._current_cycle_dgm_tokens + self._current_cycle_seal_tokens

        self.cycle_history.append(
            {
                "cycle_number": self.cycle_count,
                "tokens": cycle_total,
                "dgm_tokens": self._current_cycle_dgm_tokens,
                "seal_tokens": self._current_cycle_seal_tokens,
            }
        )

        # Reset accumulators for next cycle
        self._current_cycle_dgm_tokens = 0
        self._current_cycle_seal_tokens = 0

    def record_fine_tuning_checkpoint(self, tokens: int) -> None:
        """Record tokens consumed by a fine-tuning checkpoint.

        Args:
            tokens: Number of tokens consumed during fine-tuning.
        """
        self.fine_tuning_count += 1
        self.tokens_consumed_this_run += tokens
        self.fine_tuning_history.append(
            {
                "checkpoint_number": self.fine_tuning_count,
                "tokens": tokens,
            }
        )

    def get_cost(self, cost_per_1k_tokens: float) -> float:
        """Calculate total cost from token consumption.

        Args:
            cost_per_1k_tokens: Cost per 1000 tokens (e.g., 0.005 for $0.005/1k).

        Returns:
            Total cost in the same currency unit as cost_per_1k_tokens.
        """
        return (self.tokens_consumed_this_run * cost_per_1k_tokens) / 1000

    def get_average_cost_per_cycle(self, cost_per_1k_tokens: float) -> float:
        """Calculate average cost per cycle.

        Args:
            cost_per_1k_tokens: Cost per 1000 tokens.

        Returns:
            Average cost per cycle.
        """
        if self.cycle_count == 0:
            return 0.0

        avg_tokens_per_cycle = sum(c["tokens"] for c in self.cycle_history) / self.cycle_count
        return (avg_tokens_per_cycle * cost_per_1k_tokens) / 1000

    def estimated_cycles_until_budget(
        self, budget_tokens: int, avg_tokens_per_cycle: int | None = None
    ) -> int:
        """Estimate cycles remaining until budget exhaustion.

        Args:
            budget_tokens: Total token budget for the run.
            avg_tokens_per_cycle: Average tokens per cycle. If None, calculates from history.

        Returns:
            Number of cycles estimated to fit within budget. Returns 0 if already over.
        """
        remaining_tokens = budget_tokens - self.tokens_consumed_this_run

        if remaining_tokens <= 0:
            return 0

        if avg_tokens_per_cycle is None:
            if self.cycle_count == 0:
                # Default assumption from spec
                avg_tokens_per_cycle = 4100
            else:
                avg_tokens_per_cycle = int(
                    sum(c["tokens"] for c in self.cycle_history) / self.cycle_count
                )

        return remaining_tokens // avg_tokens_per_cycle

    def get_summary(self, cost_per_1k_tokens: float) -> dict[str, Any]:
        """Get a complete summary of token and cost tracking.

        Args:
            cost_per_1k_tokens: Cost per 1000 tokens.

        Returns:
            Dictionary with comprehensive token and cost breakdown.
        """
        total_dgm_tokens = sum(c["dgm_tokens"] for c in self.cycle_history)
        total_seal_cycle_tokens = sum(c["seal_tokens"] for c in self.cycle_history)
        total_seal_finetuning_tokens = sum(c["tokens"] for c in self.fine_tuning_history)

        dgm_cost = (total_dgm_tokens * cost_per_1k_tokens) / 1000
        seal_cycle_cost = (total_seal_cycle_tokens * cost_per_1k_tokens) / 1000
        seal_finetuning_cost = (total_seal_finetuning_tokens * cost_per_1k_tokens) / 1000
        total_cost = dgm_cost + seal_cycle_cost + seal_finetuning_cost

        return {
            "total_tokens": self.tokens_consumed_this_run,
            "cycle_count": self.cycle_count,
            "fine_tuning_count": self.fine_tuning_count,
            "dgm_tokens": total_dgm_tokens,
            "dgm_cost": dgm_cost,
            "seal_cycle_tokens": total_seal_cycle_tokens,
            "seal_cycle_cost": seal_cycle_cost,
            "seal_finetuning_tokens": total_seal_finetuning_tokens,
            "seal_finetuning_cost": seal_finetuning_cost,
            "total_cost": total_cost,
        }

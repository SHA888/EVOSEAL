"""
Evolution data collector for tracking EVOSEAL's improvement patterns.

This module collects and stores evolution results that can later be used
to fine-tune Devstral, creating a bidirectional improvement loop.
"""

import asyncio
import json
import logging
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from .models import CodeMetrics, EvolutionResult, EvolutionStrategy, ImprovementType

logger = logging.getLogger(__name__)


class EvolutionDataCollector:
    """
    Collects and manages evolution data for model fine-tuning.

    This class tracks successful evolution patterns from EVOSEAL and prepares
    them for use in fine-tuning Devstral, enabling bidirectional improvement.
    """

    def __init__(
        self,
        data_dir: Optional[Path] = None,
        min_fitness_threshold: float = 0.7,
        max_memory_results: int = 1000,
        auto_save_interval: int = 50,
    ):
        """
        Initialize the evolution data collector.

        Args:
            data_dir: Directory to store evolution data
            min_fitness_threshold: Minimum fitness score to consider successful
            max_memory_results: Maximum results to keep in memory
            auto_save_interval: Save to disk every N results
        """
        self.data_dir = data_dir or Path("data/evolution_results")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.min_fitness_threshold = min_fitness_threshold
        self.max_memory_results = max_memory_results
        self.auto_save_interval = auto_save_interval

        # In-memory storage
        self.successful_results: deque = deque(maxlen=max_memory_results)
        self.failed_results: deque = deque(maxlen=max_memory_results)
        self.all_results: deque = deque(maxlen=max_memory_results * 2)

        # Statistics tracking
        self.stats = {
            "total_collected": 0,
            "successful_count": 0,
            "failed_count": 0,
            "last_save": None,
            "collection_start": datetime.now(),
        }

        # Pattern tracking
        self.strategy_performance = defaultdict(list)
        self.improvement_patterns = defaultdict(int)

        # Callbacks for real-time processing
        self.result_callbacks: List[Callable[[EvolutionResult], None]] = []

        logger.info(f"Evolution data collector initialized. Data dir: {self.data_dir}")

    async def collect_result(self, result: EvolutionResult) -> None:
        """
        Collect a single evolution result.

        Args:
            result: The evolution result to collect
        """
        try:
            # Add to appropriate collection
            self.all_results.append(result)

            if result.success and result.fitness_score >= self.min_fitness_threshold:
                self.successful_results.append(result)
                self.stats["successful_count"] += 1
                logger.debug(
                    f"Collected successful result: {result.id} (fitness: {result.fitness_score:.3f})"
                )
            else:
                self.failed_results.append(result)
                self.stats["failed_count"] += 1
                logger.debug(
                    f"Collected failed result: {result.id} (fitness: {result.fitness_score:.3f})"
                )

            # Update statistics
            self.stats["total_collected"] += 1
            self._update_pattern_tracking(result)

            # Trigger callbacks
            for callback in self.result_callbacks:
                try:
                    callback(result)
                except Exception as e:
                    logger.error(f"Error in result callback: {e}")

            # Auto-save if needed
            if self.stats["total_collected"] % self.auto_save_interval == 0:
                await self.save_data()

        except Exception as e:
            logger.error(f"Error collecting evolution result: {e}")
            raise

    def _update_pattern_tracking(self, result: EvolutionResult) -> None:
        """Update internal pattern tracking."""
        # Track strategy performance
        self.strategy_performance[result.strategy].append(result.fitness_score)

        # Track improvement patterns
        for improvement_type in result.improvement_types:
            self.improvement_patterns[improvement_type] += 1

    async def save_data(self, force: bool = False) -> None:
        """
        Save collected data to disk.

        Args:
            force: Force save even if no new data
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Save successful results
            if self.successful_results or force:
                success_file = self.data_dir / f"successful_results_{timestamp}.json"
                success_data = [result.to_dict() for result in self.successful_results]

                with open(success_file, "w") as f:
                    json.dump(success_data, f, indent=2, default=str)

                logger.info(f"Saved {len(success_data)} successful results to {success_file}")

            # Save failed results (for analysis)
            if self.failed_results or force:
                failed_file = self.data_dir / f"failed_results_{timestamp}.json"
                failed_data = [result.to_dict() for result in self.failed_results]

                with open(failed_file, "w") as f:
                    json.dump(failed_data, f, indent=2, default=str)

                logger.debug(f"Saved {len(failed_data)} failed results to {failed_file}")

            # Save statistics and patterns
            stats_file = self.data_dir / f"collection_stats_{timestamp}.json"
            stats_data = {
                "stats": self.stats.copy(),
                "strategy_performance": {str(k): v for k, v in self.strategy_performance.items()},
                "improvement_patterns": {str(k): v for k, v in self.improvement_patterns.items()},
            }
            stats_data["stats"]["last_save"] = datetime.now().isoformat()

            with open(stats_file, "w") as f:
                json.dump(stats_data, f, indent=2, default=str)

            self.stats["last_save"] = datetime.now()
            logger.info(f"Saved collection statistics to {stats_file}")

        except Exception as e:
            logger.error(f"Error saving evolution data: {e}")
            raise

    def load_historical_data(self, days_back: int = 30) -> List[EvolutionResult]:
        """
        Load historical evolution data.

        Args:
            days_back: Number of days to look back

        Returns:
            List of historical evolution results
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            historical_results = []

            # Find relevant data files
            pattern = "successful_results_*.json"
            data_files = sorted(self.data_dir.glob(pattern))

            for data_file in data_files:
                try:
                    with open(data_file) as f:
                        data = json.load(f)

                    for result_dict in data:
                        result = EvolutionResult.from_dict(result_dict)
                        if result.timestamp >= cutoff_date:
                            historical_results.append(result)

                except Exception as e:
                    logger.warning(f"Error loading data file {data_file}: {e}")
                    continue

            logger.info(
                f"Loaded {len(historical_results)} historical results from last {days_back} days"
            )
            return historical_results

        except Exception as e:
            logger.error(f"Error loading historical data: {e}")
            return []

    def get_training_candidates(self, min_samples: int = 100) -> List[EvolutionResult]:
        """
        Get evolution results suitable for training.

        Args:
            min_samples: Minimum number of samples required

        Returns:
            List of high-quality evolution results for training
        """
        # Combine in-memory and recent historical data
        candidates = list(self.successful_results)

        if len(candidates) < min_samples:
            # Load more historical data
            historical = self.load_historical_data(days_back=7)
            candidates.extend(historical)

        # Filter and sort by quality
        high_quality = [
            result
            for result in candidates
            if result.fitness_score >= self.min_fitness_threshold
            and result.improvement_percentage > 5.0  # At least 5% improvement
        ]

        # Sort by fitness score (best first)
        high_quality.sort(key=lambda x: x.fitness_score, reverse=True)

        logger.info(f"Found {len(high_quality)} high-quality training candidates")
        return high_quality

    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics about collected data."""
        runtime = datetime.now() - self.stats["collection_start"]

        # Calculate strategy effectiveness
        strategy_stats = {}
        for strategy, scores in self.strategy_performance.items():
            if scores:
                strategy_stats[str(strategy)] = {
                    "count": len(scores),
                    "avg_fitness": sum(scores) / len(scores),
                    "max_fitness": max(scores),
                    "min_fitness": min(scores),
                }

        return {
            "collection_stats": {
                **self.stats,
                "runtime_hours": runtime.total_seconds() / 3600,
                "success_rate": (
                    self.stats["successful_count"] / self.stats["total_collected"]
                    if self.stats["total_collected"] > 0
                    else 0
                ),
                "collection_rate_per_hour": (
                    self.stats["total_collected"] / max(1, runtime.total_seconds() / 3600)
                ),
            },
            "strategy_performance": strategy_stats,
            "improvement_patterns": {str(k): v for k, v in self.improvement_patterns.items()},
            "memory_usage": {
                "successful_results": len(self.successful_results),
                "failed_results": len(self.failed_results),
                "total_in_memory": len(self.all_results),
            },
        }

    def add_result_callback(self, callback: Callable[[EvolutionResult], None]) -> None:
        """Add a callback to be called when new results are collected."""
        self.result_callbacks.append(callback)

    def clear_memory(self) -> None:
        """Clear in-memory results (data on disk is preserved)."""
        self.successful_results.clear()
        self.failed_results.clear()
        self.all_results.clear()
        logger.info("Cleared in-memory evolution results")


# Convenience functions for creating evolution results
def create_evolution_result(
    original_code: str,
    improved_code: str,
    fitness_score: float,
    strategy: EvolutionStrategy = EvolutionStrategy.GENETIC_ALGORITHM,
    task_description: str = "",
    provider_used: str = "ollama",
    **kwargs,
) -> EvolutionResult:
    """
    Create an evolution result with sensible defaults.

    This is a helper function for easily creating EvolutionResult objects
    from EVOSEAL's evolution cycles.
    """
    # Calculate basic metrics (simplified for now)
    original_lines = len(original_code.split("\n"))
    improved_lines = len(improved_code.split("\n"))

    original_metrics = CodeMetrics(
        lines_of_code=original_lines,
        cyclomatic_complexity=1.0,  # Placeholder
        maintainability_index=50.0,  # Placeholder
        test_coverage=0.0,  # Placeholder
        execution_time=1.0,  # Placeholder
        memory_usage=1.0,  # Placeholder
        readability_score=50.0,  # Placeholder
    )

    improved_metrics = CodeMetrics(
        lines_of_code=improved_lines,
        cyclomatic_complexity=1.0,  # Placeholder
        maintainability_index=60.0,  # Placeholder
        test_coverage=0.0,  # Placeholder
        execution_time=0.8,  # Placeholder improvement
        memory_usage=0.9,  # Placeholder improvement
        readability_score=70.0,  # Placeholder improvement
    )

    # Determine improvement types (simplified)
    improvement_types = []
    if improved_lines < original_lines:
        improvement_types.append(ImprovementType.EFFICIENCY)
    if fitness_score > 0.8:
        improvement_types.append(ImprovementType.PERFORMANCE)
    if not improvement_types:
        improvement_types.append(ImprovementType.READABILITY)

    improvement_percentage = ((fitness_score - 0.5) / 0.5) * 100  # Simplified calculation

    return EvolutionResult(
        id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        original_code=original_code,
        improved_code=improved_code,
        strategy=strategy,
        generation=kwargs.get("generation", 1),
        iteration=kwargs.get("iteration", 1),
        fitness_score=fitness_score,
        improvement_percentage=max(0, improvement_percentage),
        original_metrics=original_metrics,
        improved_metrics=improved_metrics,
        improvement_types=improvement_types,
        success=fitness_score >= 0.7,
        task_description=task_description,
        provider_used=provider_used,
        model_version=kwargs.get("model_version", "devstral:latest"),
        metadata=kwargs.get("metadata", {}),
    )

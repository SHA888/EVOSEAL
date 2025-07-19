"""Integration between evolution pipeline and experiment tracking.

This module provides integration between the evolution pipeline and the experiment
tracking system, enabling automatic experiment creation, version control, and
result tracking during evolution runs.
"""

from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..models.experiment import (
    Experiment,
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    MetricType,
    create_experiment,
)
from .experiment_database import ExperimentDatabase
from .version_database import VersionDatabase
from .version_tracker import VersionTracker

logger = logging.getLogger(__name__)


class ExperimentIntegration:
    """Integrates experiment tracking with the evolution pipeline."""

    def __init__(
        self,
        version_tracker: VersionTracker,
        auto_commit: bool = True,
        auto_tag: bool = True,
        track_metrics: bool = True,
    ):
        """Initialize experiment integration.

        Args:
            version_tracker: Version tracker instance
            auto_commit: Whether to automatically commit changes
            auto_tag: Whether to automatically create git tags
            track_metrics: Whether to automatically track metrics
        """
        self.version_tracker = version_tracker
        self.auto_commit = auto_commit
        self.auto_tag = auto_tag
        self.track_metrics = track_metrics

        self.current_experiment: Optional[Experiment] = None
        self._iteration_count = 0
        self._generation_count = 0

    def create_evolution_experiment(
        self,
        name: str,
        config: Dict[str, Any],
        repository_name: Optional[str] = None,
        branch: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        **metadata: Any,
    ) -> Experiment:
        """Create an experiment for an evolution run.

        Args:
            name: Name of the experiment
            config: Evolution configuration dictionary
            repository_name: Git repository name
            branch: Git branch
            description: Experiment description
            tags: List of tags
            created_by: Creator identifier
            **metadata: Additional metadata

        Returns:
            Created experiment
        """
        # Convert config to ExperimentConfig
        experiment_config = self._convert_to_experiment_config(config)

        # Create experiment with version control
        experiment = self.version_tracker.create_experiment_with_version(
            name=name,
            config=experiment_config,
            repository_name=repository_name,
            branch=branch,
            description=description,
            tags=tags or [],
            created_by=created_by,
            **metadata,
        )

        self.current_experiment = experiment
        logger.info(f"Created evolution experiment {experiment.id}: {name}")
        return experiment

    def start_evolution_experiment(self, experiment_id: Optional[str] = None) -> Experiment:
        """Start an evolution experiment.

        Args:
            experiment_id: Optional experiment ID (uses current if not provided)

        Returns:
            Started experiment
        """
        if experiment_id:
            experiment = self.version_tracker.experiment_db.get_experiment(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")
            self.current_experiment = experiment
        elif not self.current_experiment:
            raise ValueError("No current experiment to start")
        else:
            experiment = self.current_experiment

        # Start the experiment with version control
        experiment = self.version_tracker.start_experiment(
            experiment.id, auto_commit=self.auto_commit
        )

        self.current_experiment = experiment
        self._iteration_count = 0
        self._generation_count = 0

        logger.info(f"Started evolution experiment {experiment.id}")
        return experiment

    def complete_evolution_experiment(
        self, result: Optional[ExperimentResult] = None, experiment_id: Optional[str] = None
    ) -> Experiment:
        """Complete an evolution experiment.

        Args:
            result: Optional experiment result
            experiment_id: Optional experiment ID (uses current if not provided)

        Returns:
            Completed experiment
        """
        if experiment_id:
            experiment = self.version_tracker.experiment_db.get_experiment(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")
        elif not self.current_experiment:
            raise ValueError("No current experiment to complete")
        else:
            experiment = self.current_experiment

        # Set result if provided
        if result:
            experiment.result = result
        elif not experiment.result:
            # Create a basic result from tracked metrics
            experiment.result = self._create_result_from_metrics(experiment)

        # Complete the experiment with version control
        experiment = self.version_tracker.complete_experiment(
            experiment.id, auto_commit=self.auto_commit, create_tag=self.auto_tag
        )

        self.current_experiment = None
        logger.info(f"Completed evolution experiment {experiment.id}")
        return experiment

    def fail_evolution_experiment(
        self, error: Exception, experiment_id: Optional[str] = None
    ) -> Experiment:
        """Mark an evolution experiment as failed.

        Args:
            error: Exception that caused the failure
            experiment_id: Optional experiment ID (uses current if not provided)

        Returns:
            Failed experiment
        """
        if experiment_id:
            experiment = self.version_tracker.experiment_db.get_experiment(experiment_id)
            if not experiment:
                raise ValueError(f"Experiment {experiment_id} not found")
        elif not self.current_experiment:
            raise ValueError("No current experiment to fail")
        else:
            experiment = self.current_experiment

        # Mark as failed
        experiment.fail(error_message=str(error), error_traceback=traceback.format_exc())

        # Save to database
        self.version_tracker.experiment_db.save_experiment(experiment)

        self.current_experiment = None
        logger.error(f"Failed evolution experiment {experiment.id}: {error}")
        return experiment

    def track_iteration_start(self, iteration: int, **metadata: Any) -> None:
        """Track the start of an evolution iteration.

        Args:
            iteration: Iteration number
            **metadata: Additional metadata
        """
        if not self.current_experiment or not self.track_metrics:
            return

        self._iteration_count = iteration

        self.current_experiment.add_metric(
            name="iteration_started",
            value=iteration,
            metric_type=MetricType.CUSTOM,
            iteration=iteration,
            **metadata,
        )

        # Save experiment
        self.version_tracker.experiment_db.save_experiment(self.current_experiment)

    def track_iteration_complete(
        self,
        iteration: int,
        fitness_scores: Optional[List[float]] = None,
        best_fitness: Optional[float] = None,
        **metrics: Any,
    ) -> None:
        """Track the completion of an evolution iteration.

        Args:
            iteration: Iteration number
            fitness_scores: List of fitness scores for the population
            best_fitness: Best fitness score in this iteration
            **metrics: Additional metrics to track
        """
        if not self.current_experiment or not self.track_metrics:
            return

        # Track completion
        self.current_experiment.add_metric(
            name="iteration_completed",
            value=iteration,
            metric_type=MetricType.CUSTOM,
            iteration=iteration,
        )

        # Track fitness metrics
        if fitness_scores:
            self.current_experiment.add_metric(
                name="population_fitness_avg",
                value=sum(fitness_scores) / len(fitness_scores),
                metric_type=MetricType.CUSTOM,
                iteration=iteration,
            )

            self.current_experiment.add_metric(
                name="population_fitness_max",
                value=max(fitness_scores),
                metric_type=MetricType.CUSTOM,
                iteration=iteration,
            )

            self.current_experiment.add_metric(
                name="population_fitness_min",
                value=min(fitness_scores),
                metric_type=MetricType.CUSTOM,
                iteration=iteration,
            )

        if best_fitness is not None:
            self.current_experiment.add_metric(
                name="best_fitness",
                value=best_fitness,
                metric_type=MetricType.CUSTOM,
                iteration=iteration,
            )

        # Track additional metrics
        for metric_name, value in metrics.items():
            self.current_experiment.add_metric(
                name=metric_name, value=value, metric_type=MetricType.CUSTOM, iteration=iteration
            )

        # Save experiment
        self.version_tracker.experiment_db.save_experiment(self.current_experiment)

    def track_variant_creation(
        self,
        variant_id: str,
        source: str,
        test_results: Any,
        eval_score: float,
        parent_ids: Optional[List[str]] = None,
        **metadata: Any,
    ) -> None:
        """Track creation of a code variant.

        Args:
            variant_id: Unique identifier for the variant
            source: Source code of the variant
            test_results: Test results for the variant
            eval_score: Evaluation score
            parent_ids: Parent variant IDs
            **metadata: Additional metadata
        """
        if not self.current_experiment:
            return

        # Add to version database with experiment association
        self.version_tracker.version_db.add_variant(
            variant_id=variant_id,
            source=source,
            test_results=test_results,
            eval_score=eval_score,
            parent_ids=parent_ids,
            metadata=metadata,
            experiment_id=self.current_experiment.id,
        )

        # Track as metric if enabled
        if self.track_metrics:
            self.current_experiment.add_metric(
                name="variant_created",
                value=variant_id,
                metric_type=MetricType.CUSTOM,
                iteration=self._iteration_count,
                variant_score=eval_score,
            )

            # Save experiment
            self.version_tracker.experiment_db.save_experiment(self.current_experiment)

    def track_performance_metrics(self, **metrics: Any) -> None:
        """Track performance metrics.

        Args:
            **metrics: Performance metrics to track
        """
        if not self.current_experiment or not self.track_metrics:
            return

        for metric_name, value in metrics.items():
            # Determine metric type based on name
            metric_type = MetricType.CUSTOM
            if "time" in metric_name.lower():
                metric_type = MetricType.EXECUTION_TIME
            elif "memory" in metric_name.lower():
                metric_type = MetricType.MEMORY_USAGE
            elif "accuracy" in metric_name.lower():
                metric_type = MetricType.ACCURACY
            elif "loss" in metric_name.lower():
                metric_type = MetricType.LOSS

            self.current_experiment.add_metric(
                name=metric_name,
                value=value,
                metric_type=metric_type,
                iteration=self._iteration_count,
            )

        # Save experiment
        self.version_tracker.experiment_db.save_experiment(self.current_experiment)

    def create_checkpoint(self, checkpoint_name: Optional[str] = None) -> str:
        """Create a checkpoint of the current experiment.

        Args:
            checkpoint_name: Optional name for the checkpoint

        Returns:
            Checkpoint ID
        """
        if not self.current_experiment:
            raise ValueError("No current experiment for checkpoint")

        checkpoint_id = self.version_tracker.create_checkpoint(
            self.current_experiment.id, checkpoint_name=checkpoint_name
        )

        logger.info(
            f"Created checkpoint {checkpoint_id} for experiment {self.current_experiment.id}"
        )
        return checkpoint_id

    def add_artifact(
        self,
        name: str,
        artifact_type: str,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        **metadata: Any,
    ) -> Optional[str]:
        """Add an artifact to the current experiment.

        Args:
            name: Artifact name
            artifact_type: Type of artifact
            file_path: Optional file path
            content: Optional content
            **metadata: Additional metadata

        Returns:
            Artifact ID if successful
        """
        if not self.current_experiment:
            return None

        artifact = self.current_experiment.add_artifact(
            name=name, artifact_type=artifact_type, file_path=file_path, content=content, **metadata
        )

        # Save experiment
        self.version_tracker.experiment_db.save_experiment(self.current_experiment)

        return artifact.id

    def get_experiment_summary(self, experiment_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a summary of an experiment.

        Args:
            experiment_id: Optional experiment ID (uses current if not provided)

        Returns:
            Experiment summary
        """
        if experiment_id:
            experiment = self.version_tracker.experiment_db.get_experiment(experiment_id)
        elif self.current_experiment:
            experiment = self.current_experiment
        else:
            raise ValueError("No experiment specified or current")

        if not experiment:
            raise ValueError(f"Experiment {experiment_id} not found")

        # Get variant statistics
        variant_stats = self.version_tracker.version_db.get_variant_statistics(experiment.id)

        # Get latest metrics
        latest_metrics = {}
        for metric in experiment.metrics:
            if (
                metric.name not in latest_metrics
                or metric.timestamp > latest_metrics[metric.name].timestamp
            ):
                latest_metrics[metric.name] = metric

        return {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "status": experiment.status.value,
            "created_at": experiment.created_at.isoformat(),
            "duration": experiment.duration(),
            "git_info": {
                "commit": experiment.git_commit,
                "branch": experiment.git_branch,
                "repository": experiment.git_repository,
            },
            "variant_statistics": variant_stats,
            "latest_metrics": {name: metric.value for name, metric in latest_metrics.items()},
            "artifact_count": len(experiment.artifacts),
            "total_metrics": len(experiment.metrics),
        }

    def _convert_to_experiment_config(self, config: Dict[str, Any]) -> ExperimentConfig:
        """Convert a configuration dictionary to ExperimentConfig.

        Args:
            config: Configuration dictionary

        Returns:
            ExperimentConfig instance
        """
        # Extract known parameters
        experiment_config = ExperimentConfig()

        # Map common parameters
        if "experiment_type" in config:
            experiment_config.experiment_type = ExperimentType(config["experiment_type"])

        if "seed" in config:
            experiment_config.seed = config["seed"]

        if "max_iterations" in config:
            experiment_config.max_iterations = config["max_iterations"]

        if "population_size" in config:
            experiment_config.population_size = config["population_size"]

        if "mutation_rate" in config:
            experiment_config.mutation_rate = config["mutation_rate"]

        if "crossover_rate" in config:
            experiment_config.crossover_rate = config["crossover_rate"]

        if "selection_pressure" in config:
            experiment_config.selection_pressure = config["selection_pressure"]

        # Store component-specific configs
        if "dgm" in config:
            experiment_config.dgm_config = config["dgm"]

        if "openevolve" in config:
            experiment_config.openevolve_config = config["openevolve"]

        if "seal" in config:
            experiment_config.seal_config = config["seal"]

        # Store any remaining parameters as custom
        known_params = {
            "experiment_type",
            "seed",
            "max_iterations",
            "population_size",
            "mutation_rate",
            "crossover_rate",
            "selection_pressure",
            "dgm",
            "openevolve",
            "seal",
        }

        for key, value in config.items():
            if key not in known_params:
                experiment_config.custom_params[key] = value

        return experiment_config

    def _create_result_from_metrics(self, experiment: Experiment) -> ExperimentResult:
        """Create an experiment result from tracked metrics.

        Args:
            experiment: Experiment to create result for

        Returns:
            ExperimentResult instance
        """
        result = ExperimentResult()

        # Get final metrics
        final_metrics = {}
        for metric in experiment.metrics:
            if (
                metric.name not in final_metrics
                or metric.timestamp > final_metrics[metric.name].timestamp
            ):
                final_metrics[metric.name] = metric.value

        result.final_metrics = final_metrics

        # Extract specific metrics
        if "best_fitness" in final_metrics:
            result.best_fitness = final_metrics["best_fitness"]

        if "iteration_completed" in final_metrics:
            result.generations_completed = final_metrics["iteration_completed"]

        # Calculate execution time
        if experiment.started_at and experiment.completed_at:
            result.execution_time = (
                experiment.completed_at - experiment.started_at
            ).total_seconds()

        return result


def create_experiment_integration(
    work_dir: Union[str, Path],
    auto_commit: bool = True,
    auto_tag: bool = True,
    track_metrics: bool = True,
) -> ExperimentIntegration:
    """Create an experiment integration with default configuration.

    Args:
        work_dir: Working directory
        auto_commit: Whether to automatically commit changes
        auto_tag: Whether to automatically create git tags
        track_metrics: Whether to automatically track metrics

    Returns:
        ExperimentIntegration instance
    """
    from .version_tracker import create_version_tracker

    version_tracker = create_version_tracker(work_dir)

    return ExperimentIntegration(
        version_tracker=version_tracker,
        auto_commit=auto_commit,
        auto_tag=auto_tag,
        track_metrics=track_metrics,
    )

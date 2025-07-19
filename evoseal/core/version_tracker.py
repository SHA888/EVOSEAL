"""Version control and experiment tracking integration.

This module provides integration between git version control and experiment tracking,
enabling reproducible experiments with full version history and artifact management.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

from ..models.experiment import (
    Experiment,
    ExperimentArtifact,
    ExperimentConfig,
    ExperimentStatus,
    create_experiment,
)
from .experiment_database import ExperimentDatabase
from .repository import RepositoryManager
from .version_database import VersionDatabase

logger = logging.getLogger(__name__)


class VersionTrackingError(Exception):
    """Base exception for version tracking errors."""

    pass


class VersionTracker:
    """Integrates version control with experiment tracking."""

    def __init__(
        self,
        work_dir: Path,
        experiment_db: Optional[ExperimentDatabase] = None,
        version_db: Optional[VersionDatabase] = None,
        repo_manager: Optional[RepositoryManager] = None,
    ):
        """Initialize the version tracker.

        Args:
            work_dir: Working directory for repositories and experiments
            experiment_db: Experiment database instance
            version_db: Version database instance
            repo_manager: Repository manager instance
        """
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize databases
        self.experiment_db = experiment_db or ExperimentDatabase(self.work_dir / "experiments.db")
        self.version_db = version_db or VersionDatabase()
        self.repo_manager = repo_manager or RepositoryManager(self.work_dir)

        # Create directories
        self.experiments_dir = self.work_dir / "experiments"
        self.artifacts_dir = self.work_dir / "artifacts"
        self.checkpoints_dir = self.work_dir / "checkpoints"

        for directory in [self.experiments_dir, self.artifacts_dir, self.checkpoints_dir]:
            directory.mkdir(parents=True, exist_ok=True)

    def create_experiment_with_version(
        self,
        name: str,
        config: ExperimentConfig,
        repository_name: Optional[str] = None,
        branch: Optional[str] = None,
        description: str = "",
        tags: Optional[List[str]] = None,
        created_by: Optional[str] = None,
        **metadata: Any,
    ) -> Experiment:
        """Create a new experiment with version control information.

        Args:
            name: Name of the experiment
            config: Experiment configuration
            repository_name: Name of the git repository
            branch: Git branch to use
            description: Experiment description
            tags: List of tags
            created_by: Creator identifier
            **metadata: Additional metadata

        Returns:
            Created experiment with version information
        """
        # Get git information if repository is specified
        git_commit = None
        git_branch = None
        git_repository = None
        code_version = None

        if repository_name:
            repo = self.repo_manager.get_repository(repository_name)
            if repo:
                try:
                    git_commit = repo.head.commit.hexsha
                    git_branch = repo.active_branch.name
                    git_repository = repository_name
                    code_version = f"{git_branch}@{git_commit[:8]}"

                    # Ensure we're on the right branch
                    if branch and repo.active_branch.name != branch:
                        self.repo_manager.checkout_branch(repository_name, branch)
                        git_branch = branch
                        code_version = f"{git_branch}@{git_commit[:8]}"

                except Exception as e:
                    logger.warning(f"Could not get git information: {e}")

        # Create experiment
        experiment = create_experiment(
            name=name,
            config=config,
            description=description,
            tags=tags or [],
            created_by=created_by,
            **metadata,
        )

        # Set version control information
        experiment.git_commit = git_commit
        experiment.git_branch = git_branch
        experiment.git_repository = git_repository
        experiment.code_version = code_version

        # Save to database
        self.experiment_db.save_experiment(experiment)

        logger.info(f"Created experiment {experiment.id} with version {code_version}")
        return experiment

    def start_experiment(
        self, experiment_id: str, auto_commit: bool = True, commit_message: Optional[str] = None
    ) -> Experiment:
        """Start an experiment with optional auto-commit.

        Args:
            experiment_id: ID of the experiment to start
            auto_commit: Whether to automatically commit current changes
            commit_message: Custom commit message

        Returns:
            Updated experiment
        """
        experiment = self.experiment_db.get_experiment(experiment_id)
        if not experiment:
            raise VersionTrackingError(f"Experiment {experiment_id} not found")

        # Auto-commit if requested and repository is available
        if auto_commit and experiment.git_repository:
            repo = self.repo_manager.get_repository(experiment.git_repository)
            if repo and repo.is_dirty():
                message = (
                    commit_message or f"Auto-commit before starting experiment {experiment.name}"
                )
                success = self.repo_manager.commit_changes(experiment.git_repository, message)
                if success:
                    # Update experiment with new commit
                    experiment.git_commit = repo.head.commit.hexsha
                    experiment.code_version = f"{experiment.git_branch}@{experiment.git_commit[:8]}"

        # Start the experiment
        experiment.start()

        # Create experiment directory
        exp_dir = self.experiments_dir / experiment.id
        exp_dir.mkdir(exist_ok=True)

        # Save experiment snapshot
        self._save_experiment_snapshot(experiment)

        # Save to database
        self.experiment_db.save_experiment(experiment)

        logger.info(f"Started experiment {experiment.id}")
        return experiment

    def complete_experiment(
        self,
        experiment_id: str,
        auto_commit: bool = True,
        commit_message: Optional[str] = None,
        create_tag: bool = True,
    ) -> Experiment:
        """Complete an experiment with optional version control actions.

        Args:
            experiment_id: ID of the experiment to complete
            auto_commit: Whether to automatically commit results
            commit_message: Custom commit message
            create_tag: Whether to create a git tag for the experiment

        Returns:
            Updated experiment
        """
        experiment = self.experiment_db.get_experiment(experiment_id)
        if not experiment:
            raise VersionTrackingError(f"Experiment {experiment_id} not found")

        # Complete the experiment
        experiment.complete()

        # Auto-commit if requested
        if auto_commit and experiment.git_repository:
            repo = self.repo_manager.get_repository(experiment.git_repository)
            if repo and repo.is_dirty():
                message = commit_message or f"Results from experiment {experiment.name}"
                self.repo_manager.commit_changes(experiment.git_repository, message)

        # Create git tag if requested
        if create_tag and experiment.git_repository:
            tag_name = f"experiment-{experiment.id[:8]}"
            try:
                repo = self.repo_manager.get_repository(experiment.git_repository)
                if repo:
                    repo.create_tag(tag_name, message=f"Experiment: {experiment.name}")
                    logger.info(f"Created git tag {tag_name} for experiment {experiment.id}")
            except Exception as e:
                logger.warning(f"Could not create git tag: {e}")

        # Archive experiment artifacts
        self._archive_experiment_artifacts(experiment)

        # Save to database
        self.experiment_db.save_experiment(experiment)

        logger.info(f"Completed experiment {experiment.id}")
        return experiment

    def create_checkpoint(
        self,
        experiment_id: str,
        checkpoint_name: Optional[str] = None,
        include_artifacts: bool = True,
    ) -> str:
        """Create a checkpoint of the current experiment state.

        Args:
            experiment_id: ID of the experiment
            checkpoint_name: Optional name for the checkpoint
            include_artifacts: Whether to include artifacts in the checkpoint

        Returns:
            Checkpoint ID
        """
        experiment = self.experiment_db.get_experiment(experiment_id)
        if not experiment:
            raise VersionTrackingError(f"Experiment {experiment_id} not found")

        # Generate checkpoint ID
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        checkpoint_id = f"{experiment_id}_{timestamp}"
        if checkpoint_name:
            checkpoint_id += f"_{checkpoint_name}"

        # Create checkpoint directory
        checkpoint_dir = self.checkpoints_dir / checkpoint_id
        checkpoint_dir.mkdir(exist_ok=True)

        # Save experiment state
        experiment_file = checkpoint_dir / "experiment.json"
        with open(experiment_file, 'w') as f:
            f.write(experiment.to_json())

        # Copy artifacts if requested
        if include_artifacts:
            artifacts_dir = checkpoint_dir / "artifacts"
            artifacts_dir.mkdir(exist_ok=True)

            for artifact in experiment.artifacts:
                if artifact.file_path and Path(artifact.file_path).exists():
                    dest_path = artifacts_dir / Path(artifact.file_path).name
                    shutil.copy2(artifact.file_path, dest_path)

        # Save checkpoint metadata
        checkpoint_metadata = {
            "checkpoint_id": checkpoint_id,
            "experiment_id": experiment_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "git_commit": experiment.git_commit,
            "git_branch": experiment.git_branch,
            "experiment_status": experiment.status.value,
            "include_artifacts": include_artifacts,
        }

        metadata_file = checkpoint_dir / "metadata.json"
        with open(metadata_file, 'w') as f:
            json.dump(checkpoint_metadata, f, indent=2)

        logger.info(f"Created checkpoint {checkpoint_id} for experiment {experiment_id}")
        return checkpoint_id

    def restore_checkpoint(self, checkpoint_id: str) -> Experiment:
        """Restore an experiment from a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to restore

        Returns:
            Restored experiment
        """
        checkpoint_dir = self.checkpoints_dir / checkpoint_id
        if not checkpoint_dir.exists():
            raise VersionTrackingError(f"Checkpoint {checkpoint_id} not found")

        # Load experiment from checkpoint
        experiment_file = checkpoint_dir / "experiment.json"
        if not experiment_file.exists():
            raise VersionTrackingError(f"Experiment data not found in checkpoint {checkpoint_id}")

        with open(experiment_file, 'r') as f:
            experiment = Experiment.from_json(f.read())

        # Restore artifacts if they exist
        artifacts_dir = checkpoint_dir / "artifacts"
        if artifacts_dir.exists():
            for artifact in experiment.artifacts:
                if artifact.file_path:
                    source_path = artifacts_dir / Path(artifact.file_path).name
                    if source_path.exists():
                        dest_path = Path(artifact.file_path)
                        dest_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(source_path, dest_path)

        # Save restored experiment to database
        self.experiment_db.save_experiment(experiment)

        logger.info(f"Restored experiment {experiment.id} from checkpoint {checkpoint_id}")
        return experiment

    def compare_experiments(self, experiment_ids: List[str]) -> Dict[str, Any]:
        """Compare multiple experiments.

        Args:
            experiment_ids: List of experiment IDs to compare

        Returns:
            Comparison results
        """
        experiments = []
        for exp_id in experiment_ids:
            experiment = self.experiment_db.get_experiment(exp_id)
            if experiment:
                experiments.append(experiment)
            else:
                logger.warning(f"Experiment {exp_id} not found for comparison")

        if len(experiments) < 2:
            raise VersionTrackingError("At least 2 experiments required for comparison")

        # Compare configurations
        config_comparison = self._compare_configurations([exp.config for exp in experiments])

        # Compare results
        results_comparison = self._compare_results([exp.result for exp in experiments])

        # Compare version information
        version_comparison = self._compare_versions(experiments)

        # Compare metrics
        metrics_comparison = self._compare_metrics(experiments)

        return {
            "experiments": [{"id": exp.id, "name": exp.name} for exp in experiments],
            "configurations": config_comparison,
            "results": results_comparison,
            "versions": version_comparison,
            "metrics": metrics_comparison,
            "comparison_timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_experiment_lineage(self, experiment_id: str) -> Dict[str, Any]:
        """Get the lineage of an experiment (ancestors and descendants).

        Args:
            experiment_id: ID of the experiment

        Returns:
            Lineage information
        """
        experiment = self.experiment_db.get_experiment(experiment_id)
        if not experiment:
            raise VersionTrackingError(f"Experiment {experiment_id} not found")

        # Get ancestors
        ancestors = []
        current_id = experiment.parent_experiment_id
        while current_id:
            parent = self.experiment_db.get_experiment(current_id)
            if parent:
                ancestors.append(
                    {
                        "id": parent.id,
                        "name": parent.name,
                        "created_at": parent.created_at.isoformat(),
                    }
                )
                current_id = parent.parent_experiment_id
            else:
                break

        # Get descendants
        descendants = []
        all_experiments = self.experiment_db.list_experiments()
        for exp in all_experiments:
            if exp.parent_experiment_id == experiment_id:
                descendants.append(
                    {"id": exp.id, "name": exp.name, "created_at": exp.created_at.isoformat()}
                )

        return {
            "experiment_id": experiment_id,
            "ancestors": ancestors,
            "descendants": descendants,
            "total_ancestors": len(ancestors),
            "total_descendants": len(descendants),
        }

    def _save_experiment_snapshot(self, experiment: Experiment) -> None:
        """Save a snapshot of the experiment configuration."""
        exp_dir = self.experiments_dir / experiment.id
        snapshot_file = exp_dir / "snapshot.json"

        snapshot_data = {
            "experiment_id": experiment.id,
            "name": experiment.name,
            "config": experiment.config.model_dump(),
            "git_commit": experiment.git_commit,
            "git_branch": experiment.git_branch,
            "created_at": experiment.created_at.isoformat(),
            "snapshot_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        with open(snapshot_file, 'w') as f:
            json.dump(snapshot_data, f, indent=2)

    def _archive_experiment_artifacts(self, experiment: Experiment) -> None:
        """Archive experiment artifacts."""
        if not experiment.artifacts:
            return

        archive_dir = self.artifacts_dir / experiment.id
        archive_dir.mkdir(exist_ok=True)

        for artifact in experiment.artifacts:
            if artifact.file_path and Path(artifact.file_path).exists():
                dest_path = archive_dir / f"{artifact.id}_{Path(artifact.file_path).name}"
                shutil.copy2(artifact.file_path, dest_path)

                # Update artifact path to archived location
                artifact.file_path = str(dest_path)

    def _compare_configurations(self, configs: List[ExperimentConfig]) -> Dict[str, Any]:
        """Compare experiment configurations."""
        if not configs:
            return {}

        # Find common and different parameters
        all_params = set()
        for config in configs:
            all_params.update(config.model_dump().keys())

        common_params = {}
        different_params = {}

        for param in all_params:
            values = []
            for config in configs:
                config_dict = config.model_dump()
                values.append(config_dict.get(param))

            if len(set(str(v) for v in values)) == 1:
                common_params[param] = values[0]
            else:
                different_params[param] = values

        return {"common_parameters": common_params, "different_parameters": different_params}

    def _compare_results(self, results: List[Optional[Any]]) -> Dict[str, Any]:
        """Compare experiment results."""
        valid_results = [r for r in results if r is not None]
        if not valid_results:
            return {"message": "No results to compare"}

        # Compare final metrics
        all_metrics = set()
        for result in valid_results:
            if hasattr(result, 'final_metrics'):
                all_metrics.update(result.final_metrics.keys())

        metric_comparison = {}
        for metric in all_metrics:
            values = []
            for result in valid_results:
                if hasattr(result, 'final_metrics'):
                    values.append(result.final_metrics.get(metric))
                else:
                    values.append(None)
            metric_comparison[metric] = values

        return {"metric_comparison": metric_comparison, "result_count": len(valid_results)}

    def _compare_versions(self, experiments: List[Experiment]) -> Dict[str, Any]:
        """Compare version information."""
        version_info = []
        for exp in experiments:
            version_info.append(
                {
                    "experiment_id": exp.id,
                    "git_commit": exp.git_commit,
                    "git_branch": exp.git_branch,
                    "git_repository": exp.git_repository,
                    "code_version": exp.code_version,
                }
            )

        # Check if all experiments use the same version
        commits = set(exp.git_commit for exp in experiments if exp.git_commit)
        branches = set(exp.git_branch for exp in experiments if exp.git_branch)

        return {
            "version_details": version_info,
            "same_commit": len(commits) <= 1,
            "same_branch": len(branches) <= 1,
            "unique_commits": len(commits),
            "unique_branches": len(branches),
        }

    def _compare_metrics(self, experiments: List[Experiment]) -> Dict[str, Any]:
        """Compare metrics across experiments."""
        all_metric_names = set()
        for exp in experiments:
            for metric in exp.metrics:
                all_metric_names.add(metric.name)

        metric_comparison = {}
        for metric_name in all_metric_names:
            values = []
            for exp in experiments:
                exp_metrics = [m for m in exp.metrics if m.name == metric_name]
                if exp_metrics:
                    # Use the latest value
                    latest_metric = max(exp_metrics, key=lambda m: m.timestamp)
                    values.append(latest_metric.value)
                else:
                    values.append(None)
            metric_comparison[metric_name] = values

        return metric_comparison

    def close(self) -> None:
        """Close all database connections."""
        if hasattr(self.experiment_db, 'close'):
            self.experiment_db.close()


def create_version_tracker(
    work_dir: Union[str, Path], db_path: Optional[Union[str, Path]] = None
) -> VersionTracker:
    """Create a version tracker with default configuration.

    Args:
        work_dir: Working directory for the tracker
        db_path: Optional path to experiment database

    Returns:
        Configured VersionTracker instance
    """
    work_dir = Path(work_dir)

    if db_path is None:
        db_path = work_dir / "experiments.db"

    experiment_db = ExperimentDatabase(db_path)
    version_db = VersionDatabase()
    repo_manager = RepositoryManager(work_dir)

    return VersionTracker(
        work_dir=work_dir,
        experiment_db=experiment_db,
        version_db=version_db,
        repo_manager=repo_manager,
    )

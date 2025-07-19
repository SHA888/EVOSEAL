"""
Checkpoint Manager for Workflow Orchestration

Handles creation, storage, retrieval, and management of workflow checkpoints.
"""

from __future__ import annotations

import json
import logging
import pickle  # nosec B403 - Used safely for checkpoint serialization in controlled environment
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .types import CheckpointType, ExecutionContext, OrchestrationState

logger = logging.getLogger(__name__)


@dataclass
class CheckpointMetadata:
    """Metadata for workflow checkpoints."""

    checkpoint_id: str
    timestamp: datetime
    checkpoint_type: CheckpointType
    state: OrchestrationState
    iteration: int
    stage: str
    success_count: int
    failure_count: int
    total_execution_time: float
    memory_usage: float
    cpu_usage: float
    experiment_id: Optional[str] = None
    version_id: Optional[str] = None
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


class CheckpointManager:
    """
    Manages workflow checkpoints for state persistence and recovery.

    Provides functionality to create, store, retrieve, and manage checkpoints
    throughout the workflow execution lifecycle.
    """

    def __init__(self, checkpoint_dir: Path):
        """Initialize the checkpoint manager.

        Args:
            checkpoint_dir: Directory for storing checkpoint files
        """
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # In-memory checkpoint registry
        self.checkpoints: Dict[str, CheckpointMetadata] = {}

        # Load existing checkpoints
        self._load_existing_checkpoints()

        logger.info(f"CheckpointManager initialized with directory: {checkpoint_dir}")

    def _load_existing_checkpoints(self) -> None:
        """Load existing checkpoints from disk."""
        try:
            for checkpoint_file in self.checkpoint_dir.glob("*.json"):
                try:
                    with open(checkpoint_file, 'r') as f:
                        checkpoint_data = json.load(f)

                    metadata_dict = checkpoint_data.get("metadata", {})
                    if metadata_dict:
                        # Convert string timestamp back to datetime
                        if isinstance(metadata_dict.get("timestamp"), str):
                            metadata_dict["timestamp"] = datetime.fromisoformat(
                                metadata_dict["timestamp"]
                            )

                        # Convert enum strings back to enums
                        if isinstance(metadata_dict.get("checkpoint_type"), str):
                            metadata_dict["checkpoint_type"] = CheckpointType(
                                metadata_dict["checkpoint_type"]
                            )

                        if isinstance(metadata_dict.get("state"), str):
                            metadata_dict["state"] = OrchestrationState(metadata_dict["state"])

                        metadata = CheckpointMetadata(**metadata_dict)
                        self.checkpoints[metadata.checkpoint_id] = metadata

                except Exception as e:
                    logger.warning(f"Failed to load checkpoint {checkpoint_file}: {e}")

        except Exception as e:
            logger.error(f"Failed to load existing checkpoints: {e}")

    async def create_checkpoint(
        self,
        checkpoint_type: CheckpointType,
        execution_context: ExecutionContext,
        workflow_steps: List[Any],
        step_results: Dict[str, Any],
        state: OrchestrationState,
        resource_usage: Dict[str, Any],
        custom_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create a new checkpoint.

        Args:
            checkpoint_type: Type of checkpoint to create
            execution_context: Current execution context
            workflow_steps: Current workflow steps
            step_results: Current step results
            state: Current orchestration state
            resource_usage: Current resource usage
            custom_metadata: Optional custom metadata

        Returns:
            Checkpoint ID
        """
        checkpoint_id = f"checkpoint_{int(time.time())}_{uuid.uuid4().hex[:8]}"

        # Create checkpoint metadata
        metadata = CheckpointMetadata(
            checkpoint_id=checkpoint_id,
            timestamp=datetime.utcnow(),
            checkpoint_type=checkpoint_type,
            state=state,
            iteration=execution_context.current_iteration,
            stage=execution_context.current_stage,
            success_count=0,  # TODO: Calculate from step_results
            failure_count=0,  # TODO: Calculate from step_results
            total_execution_time=(datetime.utcnow() - execution_context.start_time).total_seconds(),
            memory_usage=resource_usage.get("memory_percent", 0),
            cpu_usage=resource_usage.get("cpu_percent", 0),
            experiment_id=execution_context.experiment_id,
            custom_metadata=custom_metadata or {},
        )

        # Prepare checkpoint data
        checkpoint_data = {
            "metadata": self._serialize_metadata(metadata),
            "execution_context": self._serialize_execution_context(execution_context),
            "workflow_steps": [self._serialize_step(step) for step in workflow_steps],
            "step_results": step_results,
            "state": state.value,
            "created_at": datetime.utcnow().isoformat(),
        }

        # Save checkpoint to JSON file
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
        with open(checkpoint_file, 'w') as f:
            json.dump(checkpoint_data, f, indent=2, default=str)

        # Save binary state for complex objects
        binary_file = self.checkpoint_dir / f"{checkpoint_id}.pkl"
        with open(binary_file, 'wb') as f:
            pickle.dump(  # nosec B301 - Serializing trusted checkpoint data
                {
                    "step_results": step_results,
                    "custom_state": custom_metadata or {},
                },
                f,
            )

        # Store in memory registry
        self.checkpoints[checkpoint_id] = metadata

        logger.info(f"Created checkpoint: {checkpoint_id} (type: {checkpoint_type.value})")
        return checkpoint_id

    def _serialize_metadata(self, metadata: CheckpointMetadata) -> Dict[str, Any]:
        """Serialize checkpoint metadata for JSON storage."""
        return {
            "checkpoint_id": metadata.checkpoint_id,
            "timestamp": metadata.timestamp.isoformat(),
            "checkpoint_type": metadata.checkpoint_type.value,
            "state": metadata.state.value,
            "iteration": metadata.iteration,
            "stage": metadata.stage,
            "success_count": metadata.success_count,
            "failure_count": metadata.failure_count,
            "total_execution_time": metadata.total_execution_time,
            "memory_usage": metadata.memory_usage,
            "cpu_usage": metadata.cpu_usage,
            "experiment_id": metadata.experiment_id,
            "version_id": metadata.version_id,
            "custom_metadata": metadata.custom_metadata,
        }

    def _serialize_execution_context(self, context: ExecutionContext) -> Dict[str, Any]:
        """Serialize execution context for JSON storage."""
        return {
            "workflow_id": context.workflow_id,
            "experiment_id": context.experiment_id,
            "start_time": context.start_time.isoformat(),
            "current_iteration": context.current_iteration,
            "current_stage": context.current_stage,
            "total_iterations": context.total_iterations,
            "state": context.state.value,
            "checkpoint_interval": context.checkpoint_interval,
            "last_checkpoint": (
                context.last_checkpoint.isoformat() if context.last_checkpoint else None
            ),
            "resource_limits": context.resource_limits,
            "custom_context": context.custom_context,
        }

    def _serialize_step(self, step: Any) -> Dict[str, Any]:
        """Serialize workflow step for JSON storage."""
        if hasattr(step, '__dict__'):
            return step.__dict__
        return str(step)

    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a checkpoint by ID.

        Args:
            checkpoint_id: ID of the checkpoint to retrieve

        Returns:
            Checkpoint data or None if not found
        """
        checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_file.exists():
            logger.warning(f"Checkpoint {checkpoint_id} not found")
            return None

        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)

            # Load binary data if available
            binary_file = self.checkpoint_dir / f"{checkpoint_id}.pkl"
            if binary_file.exists():
                with open(binary_file, 'rb') as f:
                    binary_data = pickle.load(f)  # nosec B301 - Loading trusted checkpoint data
                checkpoint_data["binary_data"] = binary_data

            return checkpoint_data

        except Exception as e:
            logger.error(f"Failed to load checkpoint {checkpoint_id}: {e}")
            return None

    def list_checkpoints(
        self,
        checkpoint_type: Optional[CheckpointType] = None,
        experiment_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[CheckpointMetadata]:
        """List available checkpoints with optional filtering.

        Args:
            checkpoint_type: Filter by checkpoint type
            experiment_id: Filter by experiment ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata
        """
        checkpoints = list(self.checkpoints.values())

        # Apply filters
        if checkpoint_type:
            checkpoints = [cp for cp in checkpoints if cp.checkpoint_type == checkpoint_type]

        if experiment_id:
            checkpoints = [cp for cp in checkpoints if cp.experiment_id == experiment_id]

        # Sort by timestamp (newest first)
        checkpoints.sort(key=lambda cp: cp.timestamp, reverse=True)

        # Apply limit
        if limit:
            checkpoints = checkpoints[:limit]

        return checkpoints

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint.

        Args:
            checkpoint_id: ID of the checkpoint to delete

        Returns:
            True if deleted successfully
        """
        try:
            # Remove files
            checkpoint_file = self.checkpoint_dir / f"{checkpoint_id}.json"
            binary_file = self.checkpoint_dir / f"{checkpoint_id}.pkl"

            if checkpoint_file.exists():
                checkpoint_file.unlink()

            if binary_file.exists():
                binary_file.unlink()

            # Remove from memory registry
            if checkpoint_id in self.checkpoints:
                del self.checkpoints[checkpoint_id]

            logger.info(f"Deleted checkpoint: {checkpoint_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete checkpoint {checkpoint_id}: {e}")
            return False

    def cleanup_old_checkpoints(
        self,
        max_age_days: int = 30,
        max_count: int = 100,
        keep_milestone: bool = True,
    ) -> int:
        """Clean up old checkpoints based on age and count limits.

        Args:
            max_age_days: Maximum age in days for checkpoints
            max_count: Maximum number of checkpoints to keep
            keep_milestone: Whether to preserve milestone checkpoints

        Returns:
            Number of checkpoints deleted
        """
        deleted_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=max_age_days)

        # Get all checkpoints sorted by timestamp
        all_checkpoints = sorted(
            self.checkpoints.values(), key=lambda cp: cp.timestamp, reverse=True
        )

        # Identify checkpoints to delete
        to_delete = []

        # Delete by age
        for checkpoint in all_checkpoints:
            if checkpoint.timestamp < cutoff_date:
                if not (keep_milestone and checkpoint.checkpoint_type == CheckpointType.MILESTONE):
                    to_delete.append(checkpoint.checkpoint_id)

        # Delete by count (keep newest)
        if len(all_checkpoints) > max_count:
            excess_checkpoints = all_checkpoints[max_count:]
            for checkpoint in excess_checkpoints:
                if checkpoint.checkpoint_id not in to_delete:
                    if not (
                        keep_milestone and checkpoint.checkpoint_type == CheckpointType.MILESTONE
                    ):
                        to_delete.append(checkpoint.checkpoint_id)

        # Perform deletions
        for checkpoint_id in to_delete:
            if self.delete_checkpoint(checkpoint_id):
                deleted_count += 1

        logger.info(f"Cleaned up {deleted_count} old checkpoints")
        return deleted_count

    def get_latest_checkpoint(
        self,
        experiment_id: Optional[str] = None,
        checkpoint_type: Optional[CheckpointType] = None,
    ) -> Optional[CheckpointMetadata]:
        """Get the most recent checkpoint.

        Args:
            experiment_id: Filter by experiment ID
            checkpoint_type: Filter by checkpoint type

        Returns:
            Latest checkpoint metadata or None
        """
        checkpoints = self.list_checkpoints(
            checkpoint_type=checkpoint_type, experiment_id=experiment_id, limit=1
        )

        return checkpoints[0] if checkpoints else None

    def get_checkpoint_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored checkpoints.

        Returns:
            Dictionary with checkpoint statistics
        """
        checkpoints = list(self.checkpoints.values())

        if not checkpoints:
            return {
                "total_count": 0,
                "by_type": {},
                "by_experiment": {},
                "oldest": None,
                "newest": None,
                "total_size_mb": 0,
            }

        # Count by type
        by_type = {}
        for checkpoint in checkpoints:
            type_name = checkpoint.checkpoint_type.value
            by_type[type_name] = by_type.get(type_name, 0) + 1

        # Count by experiment
        by_experiment = {}
        for checkpoint in checkpoints:
            exp_id = checkpoint.experiment_id or "unknown"
            by_experiment[exp_id] = by_experiment.get(exp_id, 0) + 1

        # Calculate total size
        total_size = 0
        for file_path in self.checkpoint_dir.glob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return {
            "total_count": len(checkpoints),
            "by_type": by_type,
            "by_experiment": by_experiment,
            "oldest": min(checkpoints, key=lambda cp: cp.timestamp).timestamp.isoformat(),
            "newest": max(checkpoints, key=lambda cp: cp.timestamp).timestamp.isoformat(),
            "total_size_mb": round(total_size / (1024 * 1024), 2),
        }

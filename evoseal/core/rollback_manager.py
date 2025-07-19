"""Rollback management system for EVOSEAL evolution pipeline.

This module provides rollback capabilities including manual rollback,
automatic rollback on failures, and rollback history tracking.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .checkpoint_manager import CheckpointError, CheckpointManager
from .logging_system import get_logger

logger = get_logger(__name__)


class RollbackError(Exception):
    """Base exception for rollback operations."""

    pass


class RollbackManager:
    """Manages rollback operations for the EVOSEAL evolution pipeline.

    Provides functionality for manual and automatic rollbacks with
    comprehensive history tracking and integration with checkpoint management.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        checkpoint_manager: CheckpointManager,
        version_manager: Optional[Any] = None,
    ):
        """Initialize the rollback manager.

        Args:
            config: Configuration dictionary
            checkpoint_manager: CheckpointManager instance
            version_manager: Version manager instance (optional)
        """
        self.config = config
        self.checkpoint_manager = checkpoint_manager
        self.version_manager = version_manager

        # Rollback history: List of rollback events
        self.rollback_history: List[Dict[str, Any]] = []

        # Configuration
        self.auto_rollback_enabled = config.get('auto_rollback_enabled', True)
        self.rollback_threshold = config.get('rollback_threshold', 0.1)  # 10% regression threshold
        self.max_rollback_attempts = config.get('max_rollback_attempts', 3)
        self.rollback_history_file = Path(
            config.get('rollback_history_file', './rollback_history.json')
        )

        # Load existing rollback history
        self._load_rollback_history()

        logger.info("RollbackManager initialized")

    def rollback_to_version(self, version_id: str, reason: str = 'manual_rollback') -> bool:
        """Rollback to a specific version.

        Args:
            version_id: ID of the version to rollback to
            reason: Reason for the rollback

        Returns:
            True if rollback was successful

        Raises:
            RollbackError: If rollback fails
        """
        try:
            # Check if checkpoint exists
            checkpoint_path = self.checkpoint_manager.get_checkpoint_path(version_id)
            if not checkpoint_path:
                raise RollbackError(f"No checkpoint found for version {version_id}")

            # Get working directory
            working_dir = self._get_working_directory()

            # Restore checkpoint to working directory
            success = self.checkpoint_manager.restore_checkpoint(version_id, working_dir)
            if not success:
                raise RollbackError(f"Failed to restore checkpoint for version {version_id}")

            # Record rollback event
            rollback_event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version_id': version_id,
                'reason': reason,
                'success': True,
                'working_directory': str(working_dir),
            }
            self.rollback_history.append(rollback_event)
            self._save_rollback_history()

            logger.info(f"Successfully rolled back to version {version_id} (reason: {reason})")
            return True

        except Exception as e:
            # Record failed rollback event
            rollback_event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version_id': version_id,
                'reason': reason,
                'success': False,
                'error': str(e),
            }
            self.rollback_history.append(rollback_event)
            self._save_rollback_history()

            raise RollbackError(f"Rollback to version {version_id} failed: {e}") from e

    def auto_rollback_on_failure(
        self,
        version_id: str,
        test_results: List[Dict[str, Any]],
        metrics_comparison: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Automatically rollback if tests fail or metrics regress.

        Args:
            version_id: ID of the version that failed
            test_results: List of test results
            metrics_comparison: Optional metrics comparison data

        Returns:
            True if rollback was performed, False otherwise
        """
        if not self.auto_rollback_enabled:
            logger.debug("Auto-rollback is disabled")
            return False

        try:
            # Check if rollback is needed based on test results
            should_rollback = False
            rollback_reasons = []

            # Check test failures
            if any(r.get('status') == 'fail' for r in test_results):
                should_rollback = True
                rollback_reasons.append('test_failure')
                failed_tests = [r for r in test_results if r.get('status') == 'fail']
                logger.warning(f"Found {len(failed_tests)} failed tests")

            # Check metrics regression if provided
            if metrics_comparison:
                regressions = self._detect_regressions(metrics_comparison)
                if regressions:
                    should_rollback = True
                    rollback_reasons.append('metrics_regression')
                    logger.warning(f"Found metrics regressions: {list(regressions.keys())}")

            if not should_rollback:
                logger.debug("No rollback needed - tests passed and no regressions detected")
                return False

            # Find the parent version to rollback to
            parent_id = self._find_parent_version(version_id)
            if not parent_id:
                logger.error(f"No parent version found for version {version_id}")
                return False

            # Perform rollback
            reason = f"auto_rollback: {', '.join(rollback_reasons)}"
            success = self.rollback_to_version(parent_id, reason)

            # Record auto-rollback event with details
            rollback_event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version_id': parent_id,
                'from_version': version_id,
                'reason': reason,
                'test_results': test_results,
                'metrics_comparison': metrics_comparison,
                'rollback_reasons': rollback_reasons,
                'success': success,
            }
            self.rollback_history.append(rollback_event)
            self._save_rollback_history()

            if success:
                logger.info(
                    f"Auto-rollback successful: rolled back from {version_id} to {parent_id}"
                )
            else:
                logger.error(
                    f"Auto-rollback failed: could not rollback from {version_id} to {parent_id}"
                )

            return success

        except Exception as e:
            logger.error(f"Auto-rollback failed with exception: {e}")
            return False

    def get_rollback_history(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Get the history of rollback events.

        Args:
            limit: Maximum number of events to return (most recent first)

        Returns:
            List of rollback events
        """
        history = sorted(self.rollback_history, key=lambda x: x.get('timestamp', ''), reverse=True)
        if limit:
            history = history[:limit]
        return history

    def get_rollback_stats(self) -> Dict[str, Any]:
        """Get rollback statistics.

        Returns:
            Dictionary with rollback statistics
        """
        total_rollbacks = len(self.rollback_history)
        successful_rollbacks = len([r for r in self.rollback_history if r.get('success', False)])
        auto_rollbacks = len(
            [r for r in self.rollback_history if 'auto_rollback' in r.get('reason', '')]
        )
        manual_rollbacks = total_rollbacks - auto_rollbacks

        # Count rollback reasons
        reason_counts = {}
        for rollback in self.rollback_history:
            reason = rollback.get('reason', 'unknown')
            reason_counts[reason] = reason_counts.get(reason, 0) + 1

        return {
            'total_rollbacks': total_rollbacks,
            'successful_rollbacks': successful_rollbacks,
            'failed_rollbacks': total_rollbacks - successful_rollbacks,
            'success_rate': successful_rollbacks / total_rollbacks if total_rollbacks > 0 else 0.0,
            'auto_rollbacks': auto_rollbacks,
            'manual_rollbacks': manual_rollbacks,
            'reason_counts': reason_counts,
            'auto_rollback_enabled': self.auto_rollback_enabled,
            'rollback_threshold': self.rollback_threshold,
        }

    def clear_rollback_history(self) -> None:
        """Clear the rollback history."""
        self.rollback_history = []
        self._save_rollback_history()
        logger.info("Rollback history cleared")

    def can_rollback_to_version(self, version_id: str) -> bool:
        """Check if rollback to a specific version is possible.

        Args:
            version_id: ID of the version to check

        Returns:
            True if rollback is possible
        """
        checkpoint_path = self.checkpoint_manager.get_checkpoint_path(version_id)
        return checkpoint_path is not None

    def get_available_rollback_targets(self) -> List[Dict[str, Any]]:
        """Get list of available rollback targets.

        Returns:
            List of checkpoint metadata for available rollback targets
        """
        return self.checkpoint_manager.list_checkpoints()

    def _find_parent_version(self, version_id: str) -> Optional[str]:
        """Find the parent version for a given version.

        Args:
            version_id: ID of the version

        Returns:
            Parent version ID or None if not found
        """
        metadata = self.checkpoint_manager.get_checkpoint_metadata(version_id)
        if metadata:
            return metadata.get('parent_id')

        # Fallback: find the most recent checkpoint before this one
        checkpoints = self.checkpoint_manager.list_checkpoints()
        checkpoints = [cp for cp in checkpoints if cp.get('version_id') != version_id]

        if checkpoints:
            # Sort by checkpoint time and return the most recent
            checkpoints.sort(key=lambda x: x.get('checkpoint_time', ''), reverse=True)
            return checkpoints[0].get('version_id')

        return None

    def _detect_regressions(self, metrics_comparison: Dict[str, Any]) -> Dict[str, Any]:
        """Detect regressions in metrics comparison.

        Args:
            metrics_comparison: Metrics comparison data

        Returns:
            Dictionary of detected regressions
        """
        regressions = {}

        for metric_name, comparison in metrics_comparison.items():
            if isinstance(comparison, dict):
                change_pct = comparison.get('change_pct', 0)

                # Define regression criteria based on metric type
                if metric_name in ['success_rate', 'accuracy', 'precision', 'recall', 'f1_score']:
                    # Higher is better - regression if decrease > threshold
                    if change_pct < -self.rollback_threshold * 100:
                        regressions[metric_name] = comparison
                elif metric_name in ['duration_sec', 'memory_mb', 'cpu_percent', 'error_rate']:
                    # Lower is better - regression if increase > threshold
                    if change_pct > self.rollback_threshold * 100:
                        regressions[metric_name] = comparison

        return regressions

    def _get_working_directory(self) -> Path:
        """Get the working directory for rollback operations.

        Returns:
            Path to the working directory
        """
        if self.version_manager and hasattr(self.version_manager, 'working_dir'):
            return Path(self.version_manager.working_dir)

        # Fallback to current directory
        return Path.cwd()

    def _load_rollback_history(self) -> None:
        """Load rollback history from file."""
        if self.rollback_history_file.exists():
            try:
                with open(self.rollback_history_file, 'r', encoding='utf-8') as f:
                    self.rollback_history = json.load(f)
                logger.debug(f"Loaded {len(self.rollback_history)} rollback events from history")
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load rollback history: {e}")
                self.rollback_history = []

    def _save_rollback_history(self) -> None:
        """Save rollback history to file."""
        try:
            self.rollback_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.rollback_history_file, 'w', encoding='utf-8') as f:
                json.dump(self.rollback_history, f, indent=2, default=str)
        except OSError as e:
            logger.error(f"Failed to save rollback history: {e}")

    def __str__(self) -> str:
        """String representation of the rollback manager."""
        stats = self.get_rollback_stats()
        return (
            f"RollbackManager("
            f"total_rollbacks={stats['total_rollbacks']}, "
            f"success_rate={stats['success_rate']:.2%}, "
            f"auto_enabled={self.auto_rollback_enabled})"
        )

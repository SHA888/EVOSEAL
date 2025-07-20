"""Rollback management system for EVOSEAL evolution pipeline.

This module provides rollback capabilities including manual rollback,
automatic rollback on failures, and rollback history tracking.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from .checkpoint_manager import CheckpointError, CheckpointManager
from .events import EventType, publish
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

            # Get working directory with safety checks
            working_dir = self._get_working_directory()

            # CRITICAL SAFETY: Validate rollback target directory
            self._validate_rollback_target(working_dir)

            # Restore checkpoint to working directory
            success = self.checkpoint_manager.restore_checkpoint(version_id, working_dir)
            if not success:
                raise RollbackError(f"Failed to restore checkpoint for version {version_id}")

            # Post-rollback verification
            verification_result = self._verify_rollback_success(version_id, working_dir)
            if not verification_result['success']:
                logger.error(f"Post-rollback verification failed: {verification_result['error']}")
                # Don't raise exception here - rollback succeeded but verification failed
                # This is logged for monitoring but doesn't fail the rollback

            # Record rollback event
            rollback_event = {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version_id': version_id,
                'reason': reason,
                'success': True,
                'working_directory': str(working_dir),
                'safety_validated': True,
                'verification_result': verification_result,
            }
            self.rollback_history.append(rollback_event)
            self._save_rollback_history()

            # Publish rollback success event
            try:
                publish(
                    EventType.ROLLBACK_COMPLETED,
                    source="rollback_manager",
                    version_id=version_id,
                    reason=reason,
                    working_directory=str(working_dir),
                    verification_passed=verification_result['success']
                )
            except Exception as e:
                logger.warning(f"Failed to publish rollback event: {e}")

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

            # Attempt failure recovery if enabled
            if self.config.get('enable_rollback_failure_recovery', True):
                logger.info(f"Attempting rollback failure recovery for version {version_id}")
                recovery_result = self.handle_rollback_failure(version_id, str(e))
                
                if recovery_result['success']:
                    logger.info(f"Rollback failure recovery successful: {recovery_result['recovery_strategy']}")
                    return True  # Recovery succeeded, don't raise exception
                else:
                    logger.error(f"Rollback failure recovery failed: {recovery_result.get('error', 'Unknown error')}")

            raise RollbackError(f"Rollback to version {version_id} failed: {e}") from e

    def _validate_rollback_target(self, target_dir: Path) -> None:
        """Validate that the rollback target directory is safe.

        Args:
            target_dir: Target directory for rollback

        Raises:
            RollbackError: If target directory is unsafe
        """
        target_resolved = target_dir.resolve()
        current_dir = Path.cwd().resolve()

        # EXCEPTION: Allow safe fallback directory created by EVOSEAL
        safe_fallback_dir = (current_dir / '.evoseal' / 'rollback_target').resolve()
        if target_resolved == safe_fallback_dir:
            logger.info(f"Using safe EVOSEAL fallback directory: {target_resolved}")
            return

        # CRITICAL SAFETY: Never allow rollback to current working directory
        if target_resolved == current_dir:
            raise RollbackError(
                f"SAFETY ERROR: Cannot rollback to current working directory {current_dir}. "
                "This would delete the entire codebase! Configure a proper working directory."
            )

        # CRITICAL SAFETY: Never allow rollback to parent directories of current directory
        try:
            current_dir.relative_to(target_resolved)
            raise RollbackError(
                f"SAFETY ERROR: Cannot rollback to parent directory {target_resolved} "
                f"of current directory {current_dir}. This could delete the codebase!"
            )
        except ValueError:
            # target_dir is not a parent of current_dir, which is good
            pass

        # CRITICAL SAFETY: Warn about potentially dangerous directories
        dangerous_patterns = ['/', '/home', '/usr', '/var', '/etc', '/opt']
        target_str = str(target_resolved)

        for pattern in dangerous_patterns:
            if target_str == pattern or target_str.startswith(pattern + '/'):
                if len(target_str.split('/')) <= 3:  # Very shallow paths are dangerous
                    raise RollbackError(
                        f"SAFETY ERROR: Rollback target {target_resolved} appears to be "
                        f"a system directory. This is extremely dangerous!"
                    )

        logger.info(f"Rollback target validation passed: {target_resolved}")

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

            # Publish rollback initiated event
            try:
                publish(
                    EventType.ROLLBACK_INITIATED,
                    source="rollback_manager",
                    version_id=parent_id,
                    from_version=version_id,
                    reason=f"auto_rollback: {', '.join(rollback_reasons)}",
                    rollback_reasons=rollback_reasons
                )
            except Exception as e:
                logger.warning(f"Failed to publish rollback initiated event: {e}")

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

        CRITICAL SAFETY: Never rollback to dangerous directories
        to prevent accidental deletion of the entire codebase.

        Returns:
            Path to a safe rollback target directory
        """
        if self.version_manager and hasattr(self.version_manager, 'working_dir'):
            working_dir = Path(self.version_manager.working_dir).resolve()
            current_dir = Path.cwd().resolve()

            # Check if the working directory is safe
            is_safe = True

            # CRITICAL SAFETY: Never use current directory
            if working_dir == current_dir:
                is_safe = False
                logger.warning(
                    f"Version manager working directory is current directory: {working_dir}"
                )

            # CRITICAL SAFETY: Never use parent directories of current directory
            try:
                current_dir.relative_to(working_dir)
                is_safe = False
                logger.warning(
                    f"Version manager working directory is parent of current directory: {working_dir}"
                )
            except ValueError:
                # working_dir is not a parent of current_dir, which is good
                pass

            # CRITICAL SAFETY: Check for dangerous system directories
            dangerous_patterns = ['/', '/home', '/usr', '/var', '/etc', '/opt']
            working_dir_str = str(working_dir)
            for pattern in dangerous_patterns:
                if working_dir_str == pattern or (
                    working_dir_str.startswith(pattern + '/')
                    and len(working_dir_str.split('/')) <= 3
                ):
                    is_safe = False
                    logger.warning(
                        f"Version manager working directory appears to be a system directory: {working_dir}"
                    )
                    break

            # If the working directory is safe, use it
            if is_safe:
                return working_dir

        # CRITICAL SAFETY: Create a safe rollback target directory
        # Never use current working directory to prevent codebase deletion
        safe_rollback_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        safe_rollback_dir.mkdir(parents=True, exist_ok=True)

        logger.warning(
            f"Using safe rollback directory: {safe_rollback_dir}. "
            "Configure version_manager.working_dir for production use."
        )

        return safe_rollback_dir

    def _verify_rollback_success(self, version_id: str, working_dir: Path) -> Dict[str, Any]:
        """Verify that rollback was successful.
        
        Args:
            version_id: ID of the version that was rolled back to
            working_dir: Directory where rollback was performed
            
        Returns:
            Dictionary with verification results
        """
        try:
            # Basic verification: check if working directory exists and has content
            if not working_dir.exists():
                return {
                    'success': False,
                    'error': f'Working directory does not exist: {working_dir}'
                }
            
            # Check if directory has any files
            files = list(working_dir.iterdir())
            if not files:
                return {
                    'success': False,
                    'error': f'Working directory is empty: {working_dir}'
                }
            
            # Verify checkpoint integrity if possible
            try:
                checkpoint_path = self.checkpoint_manager.get_checkpoint_path(version_id)
                if checkpoint_path and hasattr(self.checkpoint_manager, 'verify_checkpoint_integrity'):
                    integrity_check = self.checkpoint_manager.verify_checkpoint_integrity(version_id)
                    if not integrity_check:
                        logger.warning(f"Checkpoint integrity verification failed for {version_id}")
                        # Don't fail verification for this - it's a warning
            except Exception as e:
                logger.warning(f"Could not verify checkpoint integrity: {e}")
            
            # Publish verification success event
            try:
                publish(
                    EventType.ROLLBACK_VERIFICATION_PASSED,
                    source="rollback_manager",
                    version_id=version_id,
                    working_directory=str(working_dir),
                    file_count=len(files)
                )
            except Exception as e:
                logger.warning(f"Failed to publish verification event: {e}")
            
            return {
                'success': True,
                'file_count': len(files),
                'working_directory': str(working_dir)
            }
            
        except Exception as e:
            # Publish verification failure event
            try:
                publish(
                    EventType.ROLLBACK_VERIFICATION_FAILED,
                    source="rollback_manager",
                    version_id=version_id,
                    working_directory=str(working_dir),
                    error=str(e)
                )
            except Exception as pub_e:
                logger.warning(f"Failed to publish verification failure event: {pub_e}")
            
            return {
                'success': False,
                'error': str(e)
            }

    def cascading_rollback(self, failed_version_id: str, max_attempts: int = 3) -> Dict[str, Any]:
        """Perform cascading rollback when multiple rollbacks are needed.
        
        Args:
            failed_version_id: ID of the version that failed
            max_attempts: Maximum number of rollback attempts
            
        Returns:
            Dictionary with cascading rollback results
        """
        try:
            # Publish cascading rollback started event
            publish(
                EventType.CASCADING_ROLLBACK_STARTED,
                source="rollback_manager",
                failed_version_id=failed_version_id,
                max_attempts=max_attempts
            )
            
            current_version = failed_version_id
            rollback_chain = []
            
            for attempt in range(max_attempts):
                logger.info(f"Cascading rollback attempt {attempt + 1}/{max_attempts} for version {current_version}")
                
                # Find parent version
                parent_version = self._find_parent_version(current_version)
                if not parent_version:
                    logger.error(f"No parent version found for {current_version} - cascading rollback stopped")
                    break
                
                try:
                    # Attempt rollback
                    success = self.rollback_to_version(
                        parent_version, 
                        f"cascading_rollback_attempt_{attempt + 1}_from_{failed_version_id}"
                    )
                    
                    rollback_chain.append({
                        'from_version': current_version,
                        'to_version': parent_version,
                        'attempt': attempt + 1,
                        'success': success
                    })
                    
                    if success:
                        logger.info(f"Cascading rollback successful at attempt {attempt + 1}: {parent_version}")
                        
                        # Publish cascading rollback completed event
                        publish(
                            EventType.CASCADING_ROLLBACK_COMPLETED,
                            source="rollback_manager",
                            failed_version_id=failed_version_id,
                            successful_version_id=parent_version,
                            attempts=attempt + 1,
                            rollback_chain=rollback_chain
                        )
                        
                        return {
                            'success': True,
                            'final_version': parent_version,
                            'attempts': attempt + 1,
                            'rollback_chain': rollback_chain
                        }
                    else:
                        logger.warning(f"Rollback to {parent_version} failed, trying next parent")
                        current_version = parent_version
                        
                except Exception as e:
                    logger.error(f"Exception during cascading rollback attempt {attempt + 1}: {e}")
                    rollback_chain.append({
                        'from_version': current_version,
                        'to_version': parent_version,
                        'attempt': attempt + 1,
                        'success': False,
                        'error': str(e)
                    })
                    current_version = parent_version
            
            # All attempts failed
            logger.error(f"Cascading rollback failed after {max_attempts} attempts")
            return {
                'success': False,
                'attempts': max_attempts,
                'rollback_chain': rollback_chain,
                'error': 'All cascading rollback attempts failed'
            }
            
        except Exception as e:
            logger.error(f"Cascading rollback failed with exception: {e}")
            return {
                'success': False,
                'error': str(e),
                'rollback_chain': rollback_chain if 'rollback_chain' in locals() else []
            }

    def handle_rollback_failure(self, version_id: str, error: str, attempt_count: int = 1) -> Dict[str, Any]:
        """Handle rollback failures with recovery strategies.
        
        Args:
            version_id: ID of the version that failed to rollback
            error: Error message from the failed rollback
            attempt_count: Number of attempts made
            
        Returns:
            Dictionary with failure handling results
        """
        try:
            logger.error(f"Handling rollback failure for version {version_id}: {error}")
            
            # Publish rollback failure event
            publish(
                EventType.ROLLBACK_FAILED,
                source="rollback_manager",
                version_id=version_id,
                error=error,
                attempt_count=attempt_count
            )
            
            recovery_actions = []
            
            # Strategy 1: Try cascading rollback if not already attempted
            if attempt_count == 1 and self.config.get('enable_cascading_rollback', True):
                logger.info("Attempting cascading rollback as recovery strategy")
                cascading_result = self.cascading_rollback(version_id)
                recovery_actions.append({
                    'strategy': 'cascading_rollback',
                    'result': cascading_result
                })
                
                if cascading_result['success']:
                    return {
                        'success': True,
                        'recovery_strategy': 'cascading_rollback',
                        'final_version': cascading_result['final_version'],
                        'recovery_actions': recovery_actions
                    }
            
            # Strategy 2: Try to find a known good version
            known_good_versions = self._find_known_good_versions()
            if known_good_versions:
                logger.info(f"Attempting rollback to known good version: {known_good_versions[0]}")
                try:
                    success = self.rollback_to_version(
                        known_good_versions[0], 
                        f"recovery_rollback_from_failed_{version_id}"
                    )
                    recovery_actions.append({
                        'strategy': 'known_good_version',
                        'target_version': known_good_versions[0],
                        'success': success
                    })
                    
                    if success:
                        return {
                            'success': True,
                            'recovery_strategy': 'known_good_version',
                            'final_version': known_good_versions[0],
                            'recovery_actions': recovery_actions
                        }
                except Exception as e:
                    logger.error(f"Recovery rollback to known good version failed: {e}")
                    recovery_actions[-1]['error'] = str(e)
            
            # All recovery strategies failed
            logger.error(f"All recovery strategies failed for rollback of version {version_id}")
            return {
                'success': False,
                'error': 'All recovery strategies failed',
                'recovery_actions': recovery_actions
            }
            
        except Exception as e:
            logger.error(f"Exception in rollback failure handling: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _find_known_good_versions(self) -> List[str]:
        """Find versions that are known to be good based on rollback history.
        
        Returns:
            List of version IDs that have successful rollback history
        """
        try:
            # Get successful rollbacks from history
            successful_rollbacks = [
                event for event in self.rollback_history 
                if event.get('success', False) and 'version_id' in event
            ]
            
            # Count successful rollbacks per version
            version_success_count = {}
            for event in successful_rollbacks:
                version_id = event['version_id']
                version_success_count[version_id] = version_success_count.get(version_id, 0) + 1
            
            # Sort by success count (most successful first)
            known_good = sorted(
                version_success_count.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            
            return [version_id for version_id, _ in known_good[:5]]  # Return top 5
            
        except Exception as e:
            logger.error(f"Error finding known good versions: {e}")
            return []

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

"""Safety integration system for EVOSEAL evolution pipeline.

This module provides comprehensive safety integration that coordinates
checkpoint management, rollback capabilities, and regression detection
to ensure safe evolution pipeline execution.
"""

from typing import Any, Dict, List, Optional, Tuple, Union

from .checkpoint_manager import CheckpointManager
from .logging_system import get_logger
from .metrics_tracker import MetricsTracker
from .regression_detector import RegressionDetector
from .rollback_manager import RollbackManager

logger = get_logger(__name__)


class SafetyIntegration:
    """Integrates all safety mechanisms for the EVOSEAL evolution pipeline.

    Coordinates checkpoint management, rollback capabilities, and regression
    detection to provide comprehensive safety for evolution operations.
    """

    def __init__(
        self,
        config: Dict[str, Any],
        metrics_tracker: Optional[MetricsTracker] = None,
        version_manager: Optional[Any] = None,
    ):
        """Initialize the safety integration system.

        Args:
            config: Configuration dictionary
            metrics_tracker: MetricsTracker instance
            version_manager: Version manager instance
        """
        self.config = config
        self.version_manager = version_manager

        # Initialize components
        checkpoint_config = config.get('checkpoints', {})
        rollback_config = config.get('rollback', {})
        regression_config = config.get('regression', {})

        self.checkpoint_manager = CheckpointManager(checkpoint_config)
        self.rollback_manager = RollbackManager(
            rollback_config, self.checkpoint_manager, version_manager
        )

        # Initialize metrics tracker if not provided
        if metrics_tracker is None:
            metrics_tracker = MetricsTracker()
        self.metrics_tracker = metrics_tracker

        self.regression_detector = RegressionDetector(regression_config, self.metrics_tracker)

        # Safety configuration
        self.auto_checkpoint = config.get('auto_checkpoint', True)
        self.auto_rollback = config.get('auto_rollback', True)
        self.safety_checks_enabled = config.get('safety_checks_enabled', True)

        logger.info("SafetyIntegration initialized with all safety components")

    def create_safety_checkpoint(
        self,
        version_id: str,
        version_data: Union[Dict[str, Any], Any],
        test_results: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        """Create a safety checkpoint with test results and metrics.

        Args:
            version_id: Unique identifier for the version
            version_data: Version data to checkpoint
            test_results: Optional test results to include

        Returns:
            Path to the created checkpoint
        """
        try:
            # Add test results to version data if provided
            if test_results and isinstance(version_data, dict):
                version_data = version_data.copy()
                version_data['test_results'] = test_results
                version_data['safety_checkpoint'] = True
                version_data['checkpoint_timestamp'] = self._get_current_timestamp()

            # Create checkpoint
            checkpoint_path = self.checkpoint_manager.create_checkpoint(version_id, version_data)

            # Record metrics if test results are available
            if test_results:
                self.metrics_tracker.add_metrics(test_results)

            logger.info(f"Created safety checkpoint for version {version_id}")
            return checkpoint_path

        except Exception as e:
            logger.error(f"Failed to create safety checkpoint for version {version_id}: {e}")
            raise

    def validate_version_safety(
        self, current_version_id: str, new_version_id: str, test_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate the safety of a new version against the current version.

        Args:
            current_version_id: ID of the current/baseline version
            new_version_id: ID of the new version to validate
            test_results: Test results for the new version

        Returns:
            Safety validation results
        """
        validation_results = {
            'is_safe': True,
            'test_passed': True,
            'regression_detected': False,
            'rollback_recommended': False,
            'safety_score': 1.0,
            'issues': [],
            'recommendations': [],
        }

        try:
            # Check test results
            failed_tests = [r for r in test_results if r.get('status') == 'fail']
            if failed_tests:
                validation_results['test_passed'] = False
                validation_results['is_safe'] = False
                validation_results['issues'].append(f"Found {len(failed_tests)} failed tests")
                validation_results['recommendations'].append("Fix failing tests before proceeding")

            # Check for regressions
            has_regression, regressions = self.regression_detector.detect_regression(
                current_version_id, new_version_id
            )

            if has_regression:
                validation_results['regression_detected'] = True
                regression_summary = self.regression_detector.get_regression_summary(regressions)

                # Determine if rollback is needed
                if self.regression_detector.is_critical_regression(regressions):
                    validation_results['is_safe'] = False
                    validation_results['rollback_recommended'] = True
                    validation_results['issues'].append("Critical regressions detected")
                    validation_results['recommendations'].append("Immediate rollback recommended")
                elif regression_summary['severity_counts']['high'] > 0:
                    validation_results['is_safe'] = False
                    validation_results['issues'].append("High severity regressions detected")
                    validation_results['recommendations'].append("Review and fix regressions")
                else:
                    validation_results['issues'].append("Minor regressions detected")
                    validation_results['recommendations'].append("Monitor performance closely")

                validation_results['regression_details'] = regressions
                validation_results['regression_summary'] = regression_summary

            # Calculate safety score
            validation_results['safety_score'] = self._calculate_safety_score(
                validation_results, test_results, regressions if has_regression else {}
            )

            logger.info(f"Version safety validation completed: {validation_results['is_safe']}")
            return validation_results

        except Exception as e:
            logger.error(f"Error during safety validation: {e}")
            validation_results['is_safe'] = False
            validation_results['issues'].append(f"Validation error: {e}")
            return validation_results

    def execute_safe_evolution_step(
        self,
        current_version_id: str,
        new_version_data: Union[Dict[str, Any], Any],
        new_version_id: str,
        test_results: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Execute a single evolution step with full safety mechanisms.

        Args:
            current_version_id: ID of the current version
            new_version_data: Data for the new version
            new_version_id: ID of the new version
            test_results: Test results for the new version

        Returns:
            Execution results with safety information
        """
        execution_results = {
            'success': False,
            'version_accepted': False,
            'checkpoint_created': False,
            'rollback_performed': False,
            'safety_validation': {},
            'actions_taken': [],
        }

        try:
            # Step 1: Create checkpoint for new version
            if self.auto_checkpoint:
                checkpoint_path = self.create_safety_checkpoint(
                    new_version_id, new_version_data, test_results
                )
                execution_results['checkpoint_created'] = True
                execution_results['checkpoint_path'] = checkpoint_path
                execution_results['actions_taken'].append("Created safety checkpoint")

            # Step 2: Validate version safety
            safety_validation = self.validate_version_safety(
                current_version_id, new_version_id, test_results
            )
            execution_results['safety_validation'] = safety_validation

            # Step 3: Decide on acceptance or rollback
            if safety_validation['is_safe']:
                execution_results['version_accepted'] = True
                execution_results['success'] = True
                execution_results['actions_taken'].append("Version accepted - safety checks passed")
                logger.info(f"Version {new_version_id} accepted - safety checks passed")

            elif safety_validation['rollback_recommended'] and self.auto_rollback:
                # Perform automatic rollback
                rollback_success = self.rollback_manager.auto_rollback_on_failure(
                    new_version_id, test_results, safety_validation.get('regression_details')
                )
                execution_results['rollback_performed'] = rollback_success
                execution_results['actions_taken'].append(
                    "Automatic rollback performed" if rollback_success else "Rollback failed"
                )

                if rollback_success:
                    logger.warning(
                        f"Rolled back from version {new_version_id} due to safety issues"
                    )
                else:
                    logger.error(f"Failed to rollback from version {new_version_id}")

            else:
                execution_results['actions_taken'].append(
                    "Version rejected - manual intervention required"
                )
                logger.warning(f"Version {new_version_id} rejected - safety issues detected")

            return execution_results

        except Exception as e:
            logger.error(f"Error during safe evolution step: {e}")
            execution_results['error'] = str(e)
            return execution_results

    def get_safety_status(self) -> Dict[str, Any]:
        """Get comprehensive safety system status.

        Returns:
            Dictionary with safety system status
        """
        checkpoint_stats = self.checkpoint_manager.get_stats()
        rollback_stats = self.rollback_manager.get_rollback_stats()

        return {
            'safety_enabled': self.safety_checks_enabled,
            'auto_checkpoint': self.auto_checkpoint,
            'auto_rollback': self.auto_rollback,
            'checkpoint_manager': {
                'total_checkpoints': checkpoint_stats['total_checkpoints'],
                'total_size_mb': checkpoint_stats['total_size_mb'],
                'auto_cleanup_enabled': checkpoint_stats['auto_cleanup_enabled'],
            },
            'rollback_manager': {
                'total_rollbacks': rollback_stats['total_rollbacks'],
                'success_rate': rollback_stats['success_rate'],
                'auto_rollbacks': rollback_stats['auto_rollbacks'],
            },
            'regression_detector': {
                'threshold': self.regression_detector.regression_threshold,
                'metrics_tracked': len(self.regression_detector.metric_thresholds),
            },
        }

    def cleanup_old_safety_data(self, keep_checkpoints: int = 50) -> Dict[str, int]:
        """Clean up old safety data to free space.

        Args:
            keep_checkpoints: Number of checkpoints to keep

        Returns:
            Dictionary with cleanup statistics
        """
        cleanup_stats = {'checkpoints_deleted': 0, 'rollback_history_cleared': False}

        try:
            # Clean up old checkpoints
            deleted_checkpoints = self.checkpoint_manager.cleanup_old_checkpoints(keep_checkpoints)
            cleanup_stats['checkpoints_deleted'] = deleted_checkpoints

            # Optionally clear old rollback history (keep last 100 entries)
            rollback_history = self.rollback_manager.get_rollback_history()
            if len(rollback_history) > 100:
                # Keep only the most recent 100 entries
                recent_history = rollback_history[:100]
                self.rollback_manager.rollback_history = recent_history
                self.rollback_manager._save_rollback_history()
                cleanup_stats['rollback_history_cleared'] = True

            logger.info(f"Safety data cleanup completed: {cleanup_stats}")
            return cleanup_stats

        except Exception as e:
            logger.error(f"Error during safety data cleanup: {e}")
            cleanup_stats['error'] = str(e)
            return cleanup_stats

    def _calculate_safety_score(
        self,
        validation_results: Dict[str, Any],
        test_results: List[Dict[str, Any]],
        regressions: Dict[str, Any],
    ) -> float:
        """Calculate a safety score for the version.

        Args:
            validation_results: Validation results
            test_results: Test results
            regressions: Regression details

        Returns:
            Safety score between 0.0 and 1.0
        """
        score = 1.0

        # Deduct for test failures
        if test_results:
            total_tests = sum(r.get('tests_run', 0) for r in test_results)
            failed_tests = sum(r.get('tests_failed', 0) for r in test_results)
            if total_tests > 0:
                test_pass_rate = (total_tests - failed_tests) / total_tests
                score *= test_pass_rate

        # Deduct for regressions
        if regressions:
            regression_penalty = 0
            for regression_info in regressions.values():
                severity = regression_info.get('severity', 'low')
                if severity == 'critical':
                    regression_penalty += 0.4
                elif severity == 'high':
                    regression_penalty += 0.2
                elif severity == 'medium':
                    regression_penalty += 0.1
                else:
                    regression_penalty += 0.05

            score *= max(0.0, 1.0 - regression_penalty)

        return max(0.0, min(1.0, score))

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()

    def __str__(self) -> str:
        """String representation of the safety integration."""
        return (
            f"SafetyIntegration("
            f"auto_checkpoint={self.auto_checkpoint}, "
            f"auto_rollback={self.auto_rollback}, "
            f"safety_enabled={self.safety_checks_enabled})"
        )

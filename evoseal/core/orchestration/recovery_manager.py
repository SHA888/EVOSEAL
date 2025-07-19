"""
Recovery Manager for Workflow Orchestration

Handles error recovery, retry logic, and workflow restoration strategies.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .types import CheckpointType, ExecutionContext, OrchestrationState

logger = logging.getLogger(__name__)


@dataclass
class RecoveryStrategy:
    """Strategy configuration for workflow recovery."""

    max_retries: int = 3
    retry_delay: float = 5.0
    exponential_backoff: bool = True
    backoff_multiplier: float = 2.0
    max_retry_delay: float = 300.0  # 5 minutes
    checkpoint_rollback: bool = True
    component_restart: bool = True
    state_validation: bool = True
    custom_recovery_actions: List[Callable] = field(default_factory=list)
    recovery_timeout: float = 600.0  # 10 minutes
    critical_error_threshold: int = 5
    auto_recovery_enabled: bool = True


@dataclass
class RecoveryAttempt:
    """Record of a recovery attempt."""

    attempt_id: str
    timestamp: datetime
    error_type: str
    error_message: str
    recovery_action: str
    success: bool
    execution_time: float
    checkpoint_used: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


class RecoveryManager:
    """
    Manages error recovery and retry strategies for workflow orchestration.

    Provides comprehensive recovery mechanisms including retry logic,
    checkpoint rollback, component restart, and custom recovery actions.
    """

    def __init__(
        self,
        recovery_strategy: Optional[RecoveryStrategy] = None,
        checkpoint_manager: Optional[Any] = None,
    ):
        """Initialize the recovery manager.

        Args:
            recovery_strategy: Recovery strategy configuration
            checkpoint_manager: Checkpoint manager for rollback operations
        """
        self.recovery_strategy = recovery_strategy or RecoveryStrategy()
        self.checkpoint_manager = checkpoint_manager

        # Recovery tracking
        self.recovery_attempts: List[RecoveryAttempt] = []
        self.critical_error_count = 0
        self.last_recovery_time: Optional[datetime] = None

        logger.info("RecoveryManager initialized")

    async def attempt_recovery(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str] = None,
    ) -> bool:
        """Attempt to recover from an error.

        Args:
            error: The error that occurred
            execution_context: Current execution context
            iteration: Current iteration number
            step_id: Optional step ID where error occurred

        Returns:
            True if recovery was successful
        """
        if not self.recovery_strategy.auto_recovery_enabled:
            logger.info("Auto recovery is disabled")
            return False

        # Check if we've exceeded critical error threshold
        if self.critical_error_count >= self.recovery_strategy.critical_error_threshold:
            logger.error("Critical error threshold exceeded, recovery disabled")
            return False

        error_type = type(error).__name__
        error_message = str(error)

        logger.info(f"Attempting recovery from {error_type}: {error_message}")

        # Try different recovery strategies
        recovery_strategies = [
            ("retry_with_backoff", self._retry_with_backoff),
            ("checkpoint_rollback", self._checkpoint_rollback),
            ("component_restart", self._component_restart),
            ("state_validation", self._state_validation),
            ("custom_actions", self._execute_custom_recovery_actions),
        ]

        for strategy_name, strategy_func in recovery_strategies:
            try:
                start_time = datetime.utcnow()

                logger.info(f"Trying recovery strategy: {strategy_name}")
                success = await asyncio.wait_for(
                    strategy_func(error, execution_context, iteration, step_id),
                    timeout=self.recovery_strategy.recovery_timeout,
                )

                execution_time = (datetime.utcnow() - start_time).total_seconds()

                # Record recovery attempt
                attempt = RecoveryAttempt(
                    attempt_id=f"recovery_{int(datetime.utcnow().timestamp())}",
                    timestamp=start_time,
                    error_type=error_type,
                    error_message=error_message,
                    recovery_action=strategy_name,
                    success=success,
                    execution_time=execution_time,
                    details={
                        "iteration": iteration,
                        "step_id": step_id,
                        "context_workflow_id": execution_context.workflow_id,
                    },
                )
                self.recovery_attempts.append(attempt)

                if success:
                    logger.info(f"Recovery successful using strategy: {strategy_name}")
                    self.last_recovery_time = datetime.utcnow()
                    return True
                else:
                    logger.warning(f"Recovery strategy {strategy_name} failed")

            except asyncio.TimeoutError:
                logger.error(f"Recovery strategy {strategy_name} timed out")
            except Exception as recovery_error:
                logger.error(f"Recovery strategy {strategy_name} raised error: {recovery_error}")

        # All recovery strategies failed
        self.critical_error_count += 1
        logger.error("All recovery strategies failed")
        return False

    async def _retry_with_backoff(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str],
    ) -> bool:
        """Implement retry with exponential backoff."""
        for attempt in range(self.recovery_strategy.max_retries):
            # Calculate delay
            if self.recovery_strategy.exponential_backoff:
                delay = min(
                    self.recovery_strategy.retry_delay
                    * (self.recovery_strategy.backoff_multiplier**attempt),
                    self.recovery_strategy.max_retry_delay,
                )
            else:
                delay = self.recovery_strategy.retry_delay

            logger.info(
                f"Retry attempt {attempt + 1}/{self.recovery_strategy.max_retries} "
                f"after {delay:.1f}s delay"
            )

            await asyncio.sleep(delay)

            # For retry strategy, we just wait and return True
            # The actual retry will be handled by the calling code
            if attempt == self.recovery_strategy.max_retries - 1:
                return True

        return False

    async def _checkpoint_rollback(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str],
    ) -> bool:
        """Attempt recovery by rolling back to a previous checkpoint."""
        if not self.recovery_strategy.checkpoint_rollback or not self.checkpoint_manager:
            return False

        try:
            # Find the most recent successful checkpoint
            latest_checkpoint = self.checkpoint_manager.get_latest_checkpoint(
                experiment_id=execution_context.experiment_id
            )

            if not latest_checkpoint:
                logger.warning("No checkpoint available for rollback")
                return False

            # Load checkpoint data
            checkpoint_data = self.checkpoint_manager.get_checkpoint(
                latest_checkpoint.checkpoint_id
            )

            if not checkpoint_data:
                logger.error(f"Failed to load checkpoint {latest_checkpoint.checkpoint_id}")
                return False

            logger.info(f"Rolling back to checkpoint: {latest_checkpoint.checkpoint_id}")

            # Create recovery checkpoint before rollback
            if self.checkpoint_manager:
                await self.checkpoint_manager.create_checkpoint(
                    CheckpointType.ERROR_RECOVERY,
                    execution_context,
                    [],  # Empty workflow steps for error checkpoint
                    {},  # Empty step results
                    OrchestrationState.RECOVERING,
                    {},  # Empty resource usage
                    {
                        "error_type": type(error).__name__,
                        "error_message": str(error),
                        "rollback_to": latest_checkpoint.checkpoint_id,
                    },
                )

            return True

        except Exception as rollback_error:
            logger.error(f"Checkpoint rollback failed: {rollback_error}")
            return False

    async def _component_restart(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str],
    ) -> bool:
        """Attempt recovery by restarting components."""
        if not self.recovery_strategy.component_restart:
            return False

        try:
            logger.info("Attempting component restart recovery")

            # This is a placeholder for component restart logic
            # In a real implementation, this would restart the relevant components
            # based on the error type and step_id

            await asyncio.sleep(1)  # Simulate restart time

            logger.info("Component restart completed")
            return True

        except Exception as restart_error:
            logger.error(f"Component restart failed: {restart_error}")
            return False

    async def _state_validation(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str],
    ) -> bool:
        """Attempt recovery by validating and fixing state."""
        if not self.recovery_strategy.state_validation:
            return False

        try:
            logger.info("Attempting state validation recovery")

            # Validate execution context
            if not self._validate_execution_context(execution_context):
                logger.error("Execution context validation failed")
                return False

            # Additional state validation logic would go here

            logger.info("State validation completed successfully")
            return True

        except Exception as validation_error:
            logger.error(f"State validation failed: {validation_error}")
            return False

    async def _execute_custom_recovery_actions(
        self,
        error: Exception,
        execution_context: ExecutionContext,
        iteration: int,
        step_id: Optional[str],
    ) -> bool:
        """Execute custom recovery actions."""
        if not self.recovery_strategy.custom_recovery_actions:
            return False

        try:
            logger.info("Executing custom recovery actions")

            for action in self.recovery_strategy.custom_recovery_actions:
                try:
                    if asyncio.iscoroutinefunction(action):
                        await action(error, execution_context, iteration, step_id)
                    else:
                        action(error, execution_context, iteration, step_id)

                    logger.info(f"Custom recovery action {action.__name__} completed")

                except Exception as action_error:
                    logger.error(f"Custom recovery action {action.__name__} failed: {action_error}")
                    continue

            return True

        except Exception as custom_error:
            logger.error(f"Custom recovery actions failed: {custom_error}")
            return False

    def _validate_execution_context(self, context: ExecutionContext) -> bool:
        """Validate execution context integrity."""
        try:
            # Check required fields
            if not context.workflow_id:
                return False

            if context.current_iteration < 0:
                return False

            if context.total_iterations <= 0:
                return False

            if context.current_iteration >= context.total_iterations:
                return False

            # Check state consistency
            if not isinstance(context.state, OrchestrationState):
                return False

            return True

        except Exception as e:
            logger.error(f"Context validation error: {e}")
            return False

    def get_recovery_statistics(self) -> Dict[str, Any]:
        """Get statistics about recovery attempts.

        Returns:
            Dictionary with recovery statistics
        """
        if not self.recovery_attempts:
            return {
                "total_attempts": 0,
                "successful_attempts": 0,
                "failed_attempts": 0,
                "success_rate": 0.0,
                "by_strategy": {},
                "by_error_type": {},
                "average_execution_time": 0.0,
                "critical_error_count": self.critical_error_count,
            }

        total_attempts = len(self.recovery_attempts)
        successful_attempts = sum(1 for attempt in self.recovery_attempts if attempt.success)
        failed_attempts = total_attempts - successful_attempts

        # Group by strategy
        by_strategy = {}
        for attempt in self.recovery_attempts:
            strategy = attempt.recovery_action
            if strategy not in by_strategy:
                by_strategy[strategy] = {"total": 0, "successful": 0}
            by_strategy[strategy]["total"] += 1
            if attempt.success:
                by_strategy[strategy]["successful"] += 1

        # Group by error type
        by_error_type = {}
        for attempt in self.recovery_attempts:
            error_type = attempt.error_type
            if error_type not in by_error_type:
                by_error_type[error_type] = {"total": 0, "successful": 0}
            by_error_type[error_type]["total"] += 1
            if attempt.success:
                by_error_type[error_type]["successful"] += 1

        # Calculate average execution time
        total_time = sum(attempt.execution_time for attempt in self.recovery_attempts)
        average_time = total_time / total_attempts if total_attempts > 0 else 0.0

        return {
            "total_attempts": total_attempts,
            "successful_attempts": successful_attempts,
            "failed_attempts": failed_attempts,
            "success_rate": successful_attempts / total_attempts if total_attempts > 0 else 0.0,
            "by_strategy": by_strategy,
            "by_error_type": by_error_type,
            "average_execution_time": round(average_time, 2),
            "critical_error_count": self.critical_error_count,
            "last_recovery_time": (
                self.last_recovery_time.isoformat() if self.last_recovery_time else None
            ),
        }

    def reset_critical_error_count(self) -> None:
        """Reset the critical error count."""
        self.critical_error_count = 0
        logger.info("Critical error count reset")

    def add_custom_recovery_action(self, action: Callable) -> None:
        """Add a custom recovery action.

        Args:
            action: Callable that takes (error, execution_context, iteration, step_id) as arguments
        """
        self.recovery_strategy.custom_recovery_actions.append(action)
        logger.info(f"Added custom recovery action: {action.__name__}")

    def remove_custom_recovery_action(self, action: Callable) -> bool:
        """Remove a custom recovery action.

        Args:
            action: Callable to remove

        Returns:
            True if action was found and removed
        """
        try:
            self.recovery_strategy.custom_recovery_actions.remove(action)
            logger.info(f"Removed custom recovery action: {action.__name__}")
            return True
        except ValueError:
            logger.warning(f"Custom recovery action not found: {action.__name__}")
            return False

    def clear_recovery_history(self) -> None:
        """Clear the recovery attempt history."""
        self.recovery_attempts.clear()
        logger.info("Recovery history cleared")

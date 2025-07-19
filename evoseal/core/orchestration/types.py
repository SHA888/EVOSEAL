"""
Type definitions for workflow orchestration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class OrchestrationState(Enum):
    """States for workflow orchestration."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    CHECKPOINTING = "checkpointing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CheckpointType(Enum):
    """Types of checkpoints."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"
    RECOVERY = "recovery"
    MILESTONE = "milestone"
    ERROR_RECOVERY = "error_recovery"


class ExecutionStrategy(Enum):
    """Execution strategies for workflow orchestration."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    ADAPTIVE = "adaptive"
    PRIORITY_BASED = "priority_based"


@dataclass
class WorkflowStep:
    """Represents a single workflow step."""

    step_id: str
    name: str
    component: str
    operation: str
    dependencies: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)
    timeout: Optional[float] = None
    retry_count: int = 3
    retry_delay: float = 1.0
    critical: bool = True
    parallel_group: Optional[str] = None
    priority: int = 0


@dataclass
class ExecutionContext:
    """Context for workflow execution."""

    workflow_id: str
    experiment_id: Optional[str]
    start_time: datetime
    current_iteration: int
    current_stage: str
    total_iterations: int
    state: OrchestrationState
    checkpoint_interval: int
    last_checkpoint: Optional[datetime]
    resource_limits: Dict[str, Any] = field(default_factory=dict)
    custom_context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    """Result of a workflow step execution."""

    step_id: str
    name: str
    success: bool
    execution_time: float
    retry_count: int
    result: Optional[Any] = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    resource_usage: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IterationResult:
    """Result of a workflow iteration."""

    iteration: int
    start_time: datetime
    end_time: Optional[datetime]
    success: bool
    execution_time: float
    stages: Dict[str, StepResult]
    resource_usage: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    should_continue: bool = True


@dataclass
class WorkflowResult:
    """Complete workflow execution result."""

    workflow_id: str
    experiment_id: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    total_execution_time: float
    iterations: List[IterationResult]
    success_count: int
    failure_count: int
    checkpoints_created: int
    final_state: OrchestrationState
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

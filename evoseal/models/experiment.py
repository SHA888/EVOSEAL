"""Experiment tracking models for EVOSEAL.

This module defines models for tracking experiments, configurations,
results, and their relationships in the evolution pipeline.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import (
    IO,
    TYPE_CHECKING,
    Any,
    AnyStr,
    AsyncGenerator,
    AsyncIterable,
    AsyncIterator,
    Awaitable,
    BinaryIO,
    Callable,
    ChainMap,
    ClassVar,
    Coroutine,
    Counter,
    DefaultDict,
    Deque,
    Dict,
    Final,
    FrozenSet,
    Generic,
    Iterable,
    Iterator,
    List,
    Literal,
    Mapping,
    Match,
    MutableMapping,
    MutableSequence,
    MutableSet,
    Optional,
    Pattern,
    Protocol,
    Sequence,
    Set,
    TextIO,
    Tuple,
    Type,
    TypeAlias,
    TypeGuard,
    TypeVar,
    Union,
    cast,
    final,
    get_args,
    get_origin,
    get_type_hints,
    no_type_check,
    no_type_check_decorator,
    overload,
    runtime_checkable,
)
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_serializer,
    model_validator,
    root_validator,
    validator,
)


class ExperimentStatus(str, Enum):
    """Status of an experiment."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class ExperimentType(str, Enum):
    """Type of experiment."""

    EVOLUTION = "evolution"
    OPTIMIZATION = "optimization"
    COMPARISON = "comparison"
    ABLATION = "ablation"
    HYPERPARAMETER_TUNING = "hyperparameter_tuning"
    CUSTOM = "custom"


class MetricType(str, Enum):
    """Type of metric."""

    ACCURACY = "accuracy"
    LOSS = "loss"
    F1_SCORE = "f1_score"
    PRECISION = "precision"
    RECALL = "recall"
    AUC = "auc"
    RMSE = "rmse"
    MAE = "mae"
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CODE_QUALITY = "code_quality"
    CUSTOM = "custom"


class ExperimentConfig(BaseModel):
    """Configuration for an experiment."""

    model_config = ConfigDict(extra="forbid")

    experiment_type: ExperimentType = ExperimentType.EVOLUTION
    seed: Optional[int] = None
    max_iterations: int = 100
    population_size: int = 50
    dgm_config: Dict[str, Any] = Field(default_factory=dict)
    openevolve_config: Dict[str, Any] = Field(default_factory=dict)
    seal_config: Dict[str, Any] = Field(default_factory=dict)
    mutation_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    crossover_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    selection_pressure: float = Field(default=2.0, ge=1.0)
    fitness_function: str = "default"
    evaluation_timeout: int = 300
    environment: Dict[str, Any] = Field(default_factory=dict)
    resources: Dict[str, Any] = Field(default_factory=dict)
    custom_params: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("mutation_rate", "crossover_rate")
    @classmethod
    def validate_rates(cls, v: float) -> float:
        """Validate that rates are between 0 and 1."""
        if not 0 <= v <= 1:
            raise ValueError("Rate must be between 0 and 1")
        return round(v, 4)  # Round to avoid floating point precision issues

    @field_validator("selection_pressure")
    @classmethod
    def validate_selection_pressure(cls, v: float) -> float:
        """Validate that selection pressure is at least 1.0."""
        if v < 1.0:
            raise ValueError("Selection pressure must be at least 1.0")
        return v


class ExperimentMetric(BaseModel):
    """A metric recorded during an experiment."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: Union[float, int, str, bool]
    metric_type: MetricType = MetricType.CUSTOM
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    iteration: Optional[int] = None
    step: Optional[int] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)  # Convert to UTC if in different timezone


class ExperimentArtifact(BaseModel):
    """An artifact produced during an experiment."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    artifact_type: str
    file_path: Optional[str] = None
    content: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def ensure_timezone_aware(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware."""
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)  # Convert to UTC if in different timezone


class ExperimentResult(BaseModel):
    """Results of an experiment."""

    model_config = ConfigDict(extra="forbid")

    final_metrics: Dict[str, Union[float, int, str, bool]] = Field(default_factory=dict)
    best_individual: Optional[Dict[str, Any]] = None
    best_fitness: Optional[float] = None
    generations_completed: int = 0
    total_evaluations: int = 0
    convergence_iteration: Optional[int] = None
    execution_time: Optional[float] = Field(
        default=None, description="Execution time in seconds", json_schema_extra={"example": 123.45}
    )
    memory_peak: Optional[float] = Field(
        default=None, description="Peak memory usage in MB", json_schema_extra={"example": 1024.5}
    )
    cpu_usage: Optional[float] = Field(
        default=None,
        description="Average CPU usage as a percentage",
        ge=0.0,
        le=100.0,
        json_schema_extra={"example": 85.5},
    )
    code_quality_score: Optional[float] = Field(
        default=None,
        description="Code quality score (0-100)",
        ge=0.0,
        le=100.0,
        json_schema_extra={"example": 92.3},
    )
    test_coverage: Optional[float] = Field(
        default=None,
        description="Test coverage percentage (0-100)",
        ge=0.0,
        le=100.0,
        json_schema_extra={"example": 78.5},
    )
    summary: Dict[str, Any] = Field(
        default_factory=dict, description="Additional summary statistics and metrics"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error message if the experiment failed"
    )
    error_traceback: Optional[str] = Field(
        default=None, description="Full error traceback if the experiment failed"
    )


class Experiment(BaseModel):
    """A complete experiment record."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(
        default_factory=lambda: str(uuid4()), description="Unique identifier for the experiment"
    )
    name: str = Field(..., description="Name of the experiment")
    description: str = Field(default="", description="Description of the experiment")
    tags: List[str] = Field(
        default_factory=list, description="Tags for categorizing the experiment"
    )
    status: ExperimentStatus = Field(
        default=ExperimentStatus.CREATED, description="Current status of the experiment"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the experiment was created",
    )
    started_at: Optional[datetime] = Field(
        default=None, description="When the experiment was started"
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="When the experiment was completed"
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the experiment was last updated",
    )
    config: ExperimentConfig = Field(..., description="Configuration for the experiment")
    result: Optional[ExperimentResult] = Field(
        default=None, description="Results of the experiment"
    )
    metrics: List[ExperimentMetric] = Field(
        default_factory=list, description="Metrics recorded during the experiment"
    )
    artifacts: List[ExperimentArtifact] = Field(
        default_factory=list, description="Artifacts produced by the experiment"
    )
    git_commit: Optional[str] = Field(
        default=None, description="Git commit hash when the experiment was created"
    )
    git_branch: Optional[str] = Field(
        default=None, description="Git branch when the experiment was created"
    )
    git_repository: Optional[str] = Field(default=None, description="URL of the git repository")
    code_version: Optional[str] = Field(
        default=None, description="Version of the code used for the experiment"
    )
    parent_experiment_id: Optional[str] = Field(
        default=None, description="ID of the parent experiment if this is a continuation"
    )
    child_experiment_ids: List[str] = Field(
        default_factory=list, description="IDs of child experiments that continue from this one"
    )
    created_by: Optional[str] = Field(
        default=None, description="User or system that created the experiment"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata for the experiment"
    )

    @field_validator("created_at", "started_at", "completed_at", "updated_at", mode='before')
    @classmethod
    def ensure_timezone_aware(
        cls, v: Optional[datetime], info: FieldValidationInfo
    ) -> Optional[datetime]:
        """Ensure datetime fields are timezone-aware."""
        if v is None:
            return None
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)  # Convert to UTC if in different timezone

    @model_validator(mode='after')
    def validate_timing(self) -> 'Experiment':
        """Validate timing constraints."""
        if self.started_at and self.started_at < self.created_at:
            raise ValueError("started_at cannot be before created_at")
        if self.completed_at and self.started_at and self.completed_at < self.started_at:
            raise ValueError("completed_at cannot be before started_at")
        return self

    def add_metric(
        self,
        name: str,
        value: Union[float, int, str, bool],
        metric_type: MetricType = MetricType.CUSTOM,
        iteration: Optional[int] = None,
        step: Optional[int] = None,
        **metadata: Any,
    ) -> None:
        """Add a metric to the experiment."""
        metric = ExperimentMetric(
            name=name,
            value=value,
            metric_type=metric_type,
            iteration=iteration,
            step=step,
            metadata=metadata,
        )
        self.metrics.append(metric)
        self.updated_at = datetime.now(timezone.utc)

    def add_artifact(
        self,
        name: str,
        artifact_type: str,
        file_path: Optional[str] = None,
        content: Optional[str] = None,
        **metadata: Any,
    ) -> ExperimentArtifact:
        """Add an artifact to the experiment."""
        artifact = ExperimentArtifact(
            name=name,
            artifact_type=artifact_type,
            file_path=file_path,
            content=content,
            metadata=metadata,
        )
        self.artifacts.append(artifact)
        self.updated_at = datetime.now(timezone.utc)
        return artifact

    def start(self) -> None:
        """Mark the experiment as started."""
        if self.status != ExperimentStatus.CREATED:
            raise ValueError(f"Cannot start experiment in status {self.status}")
        self.status = ExperimentStatus.RUNNING
        self.started_at = datetime.now(timezone.utc)
        self.updated_at = self.started_at

    def complete(self, result: Optional[ExperimentResult] = None) -> None:
        """Mark the experiment as completed."""
        if self.status not in [ExperimentStatus.RUNNING, ExperimentStatus.PAUSED]:
            raise ValueError(f"Cannot complete experiment in status {self.status}")
        self.status = ExperimentStatus.COMPLETED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = self.completed_at
        if result:
            self.result = result

    def fail(self, error_message: str, error_traceback: Optional[str] = None) -> None:
        """Mark the experiment as failed."""
        self.status = ExperimentStatus.FAILED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = self.completed_at
        if not self.result:
            self.result = ExperimentResult()
        self.result.error_message = error_message
        self.result.error_traceback = error_traceback

    def pause(self) -> None:
        """Pause the experiment."""
        if self.status != ExperimentStatus.RUNNING:
            raise ValueError(f"Cannot pause experiment in status {self.status}")
        self.status = ExperimentStatus.PAUSED
        self.updated_at = datetime.now(timezone.utc)

    def resume(self) -> None:
        """Resume the experiment."""
        if self.status != ExperimentStatus.PAUSED:
            raise ValueError(f"Cannot resume experiment in status {self.status}")
        self.status = ExperimentStatus.RUNNING
        self.updated_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        """Cancel the experiment."""
        if self.status in [ExperimentStatus.COMPLETED, ExperimentStatus.FAILED]:
            raise ValueError(f"Cannot cancel experiment in status {self.status}")
        self.status = ExperimentStatus.CANCELLED
        self.completed_at = datetime.now(timezone.utc)
        self.updated_at = self.completed_at

    def get_metric_history(self, metric_name: str) -> List[ExperimentMetric]:
        """Get the history of a specific metric."""
        return [m for m in self.metrics if m.name == metric_name]

    def get_latest_metric(self, metric_name: str) -> Optional[ExperimentMetric]:
        """Get the latest value of a specific metric."""
        history = self.get_metric_history(metric_name)
        if not history:
            return None
        return max(history, key=lambda m: m.timestamp)

    def get_artifacts_by_type(self, artifact_type: str) -> List[ExperimentArtifact]:
        """Get all artifacts of a specific type."""
        return [a for a in self.artifacts if a.artifact_type == artifact_type]

    def duration(self) -> Optional[float]:
        """Get the duration of the experiment in seconds."""
        if not self.started_at:
            return None
        end_time = self.completed_at or datetime.now(timezone.utc)
        return (end_time - self.started_at).total_seconds()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return self.model_dump(mode="json")

    def to_json(self) -> str:
        """Convert to JSON string."""
        return self.model_dump_json()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Experiment:
        """Create from dictionary."""
        return cls.model_validate(data)

    @classmethod
    def from_json(cls, json_str: str) -> Experiment:
        """Create from JSON string."""
        return cls.model_validate_json(json_str)


def create_experiment(
    name: str,
    config: ExperimentConfig,
    description: str = "",
    tags: Optional[List[str]] = None,
    created_by: Optional[str] = None,
    **metadata: Any,
) -> Experiment:
    """Create a new experiment.

    Args:
        name: Name of the experiment
        config: Experiment configuration
        description: Optional description
        tags: Optional list of tags
        created_by: Optional creator identifier
        **metadata: Additional metadata

    Returns:
        New Experiment instance
    """
    return Experiment(
        name=name,
        description=description,
        config=config,
        tags=tags or [],
        created_by=created_by,
        metadata=metadata,
    )

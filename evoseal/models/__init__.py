"""EVOSEAL models package."""

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

"""Data models for EVOSEAL.

This package contains all the data models and schemas used throughout
the EVOSEAL system.
"""

from .code_archive import CodeArchive, CodeLanguage, CodeVisibility, create_code_archive
from .evaluation import EvaluationResult, TestCaseResult
from .experiment import (
    Experiment,
    ExperimentArtifact,
    ExperimentConfig,
    ExperimentMetric,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    MetricType,
    create_experiment,
)
from .system_config import SystemConfig


class Program(BaseModel):
    """Represents a program in the EVOSEAL system.

    Attributes:
        id: Unique identifier for the program
        code: The program's source code
        language: Programming language of the code
        metadata: Additional metadata about the program
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    code: str
    language: str = "python"
    metadata: dict[str, Any] = Field(default_factory=dict)

    def __str__(self) -> str:
        return f"Program(id={self.id}, language={self.language}, code_length={len(self.code)})"


__all__ = [
    # Core
    "Program",
    # Code Archive
    "CodeArchive",
    "CodeLanguage",
    "CodeVisibility",
    "create_code_archive",
    # Evaluation
    "EvaluationResult",
    "TestCaseResult",
    # Experiment
    "Experiment",
    "ExperimentConfig",
    "ExperimentResult",
    "ExperimentStatus",
    "ExperimentType",
    "ExperimentMetric",
    "ExperimentArtifact",
    "MetricType",
    "create_experiment",
    # System Config
    "SystemConfig",
]

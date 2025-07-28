"""
Data models for evolution tracking and analysis.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EvolutionStrategy(Enum):
    """Types of evolution strategies used by EVOSEAL."""

    GENETIC_ALGORITHM = "genetic_algorithm"
    HILL_CLIMBING = "hill_climbing"
    SIMULATED_ANNEALING = "simulated_annealing"
    RANDOM_SEARCH = "random_search"
    GRADIENT_BASED = "gradient_based"
    HYBRID = "hybrid"


class ImprovementType(Enum):
    """Types of code improvements detected."""

    PERFORMANCE = "performance"
    READABILITY = "readability"
    MAINTAINABILITY = "maintainability"
    CORRECTNESS = "correctness"
    EFFICIENCY = "efficiency"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    ERROR_HANDLING = "error_handling"


@dataclass
class CodeMetrics:
    """Metrics for evaluating code quality."""

    lines_of_code: int
    cyclomatic_complexity: float
    maintainability_index: float
    test_coverage: float
    execution_time: float
    memory_usage: float
    readability_score: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvolutionResult:
    """Represents the result of a single evolution cycle."""

    # Core data
    id: str
    timestamp: datetime
    original_code: str
    improved_code: str

    # Evolution metadata
    strategy: EvolutionStrategy
    generation: int
    iteration: int

    # Performance metrics
    fitness_score: float
    improvement_percentage: float
    original_metrics: CodeMetrics
    improved_metrics: CodeMetrics

    # Classification
    improvement_types: List[ImprovementType]
    success: bool

    # Context
    task_description: str
    provider_used: str
    model_version: str

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        # Convert enums to strings
        result["strategy"] = self.strategy.value
        result["improvement_types"] = [t.value for t in self.improvement_types]
        result["timestamp"] = self.timestamp.isoformat()
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvolutionResult":
        """Create from dictionary."""
        # Convert string enums back
        data["strategy"] = EvolutionStrategy(data["strategy"])
        data["improvement_types"] = [ImprovementType(t) for t in data["improvement_types"]]
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])

        # Convert metrics
        data["original_metrics"] = CodeMetrics(**data["original_metrics"])
        data["improved_metrics"] = CodeMetrics(**data["improved_metrics"])

        return cls(**data)

    def get_improvement_summary(self) -> str:
        """Get a human-readable summary of improvements."""
        improvements = ", ".join(
            [t.value.replace("_", " ").title() for t in self.improvement_types]
        )
        return f"Improved {improvements} by {self.improvement_percentage:.1f}% using {self.strategy.value.replace('_', ' ').title()}"


@dataclass
class PatternMatch:
    """Represents a detected pattern in evolution results."""

    pattern_id: str
    pattern_type: str
    frequency: int
    confidence: float
    examples: List[str]
    description: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class TrainingExample:
    """A training example for fine-tuning."""

    instruction: str
    input_code: str
    output_code: str
    context: str
    quality_score: float
    source_evolution_id: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_alpaca_format(self) -> Dict[str, str]:
        """Convert to Alpaca instruction format."""
        return {
            "instruction": self.instruction,
            "input": self.input_code,
            "output": self.output_code,
        }

    def to_chat_format(self) -> List[Dict[str, str]]:
        """Convert to chat format for training."""
        return [
            {
                "role": "system",
                "content": "You are an expert code improvement assistant. Analyze the given code and provide an improved version.",
            },
            {
                "role": "user",
                "content": f"{self.instruction}\n\n```python\n{self.input_code}\n```",
            },
            {
                "role": "assistant",
                "content": f"Here's the improved code:\n\n```python\n{self.output_code}\n```",
            },
        ]

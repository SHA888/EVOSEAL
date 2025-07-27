"""
Evolution data collection and analysis components for bidirectional evolution.

This module provides the infrastructure for collecting evolution patterns from EVOSEAL
and preparing them for fine-tuning Devstral, enabling mutual improvement between
the framework and the AI model.
"""

from .data_collector import EvolutionDataCollector, create_evolution_result
from .models import (
    CodeMetrics,
    EvolutionResult,
    EvolutionStrategy,
    ImprovementType,
    PatternMatch,
    TrainingExample,
)
from .pattern_analyzer import PatternAnalyzer
from .training_data_builder import TrainingDataBuilder

__all__ = [
    "EvolutionDataCollector",
    "EvolutionResult",
    "EvolutionStrategy",
    "ImprovementType",
    "CodeMetrics",
    "PatternMatch",
    "TrainingExample",
    "PatternAnalyzer",
    "TrainingDataBuilder",
    "create_evolution_result",
]

__version__ = "0.1.0"

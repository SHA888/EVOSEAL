"""
Weight-level fine-tuning infrastructure for EVOSEAL bidirectional evolution (GPU-only).

This module provides components for fine-tuning a local coding model (discovered
from Ollama) using evolution patterns collected from EVOSEAL, enabling
bidirectional improvement. On CPU-only hosts use :mod:`evoseal.prompt_evolution`.
"""

from .bidirectional_manager import BidirectionalEvolutionManager
from .model_fine_tuner import DevstralFineTuner, ModelFineTuner
from .model_validator import ModelValidator
from .training_manager import TrainingManager
from .version_manager import ModelVersionManager

__all__ = [
    "ModelFineTuner",
    "DevstralFineTuner",  # deprecated alias of ModelFineTuner
    "TrainingManager",
    "ModelValidator",
    "ModelVersionManager",
    "BidirectionalEvolutionManager",
]

__version__ = "0.1.0"

"""
Fine-tuning infrastructure for EVOSEAL bidirectional evolution.

This module provides components for fine-tuning Devstral models using
evolution patterns collected from EVOSEAL, enabling bidirectional improvement.
"""

from .bidirectional_manager import BidirectionalEvolutionManager
from .model_fine_tuner import DevstralFineTuner
from .model_validator import ModelValidator
from .training_manager import TrainingManager
from .version_manager import ModelVersionManager

__all__ = [
    "DevstralFineTuner",
    "TrainingManager",
    "ModelValidator",
    "ModelVersionManager",
    "BidirectionalEvolutionManager",
]

__version__ = "0.1.0"

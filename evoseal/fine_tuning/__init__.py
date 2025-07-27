"""
Fine-tuning infrastructure for EVOSEAL bidirectional evolution.

This module provides components for fine-tuning Devstral models using
evolution patterns collected from EVOSEAL, enabling bidirectional improvement.
"""

from .model_fine_tuner import DevstralFineTuner
from .training_manager import TrainingManager
from .model_validator import ModelValidator
from .version_manager import ModelVersionManager
from .bidirectional_manager import BidirectionalEvolutionManager

__all__ = [
    'DevstralFineTuner',
    'TrainingManager',
    'ModelValidator',
    'ModelVersionManager',
    'BidirectionalEvolutionManager'
]

__version__ = "0.1.0"

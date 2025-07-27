"""
Services module for EVOSEAL continuous evolution and monitoring.

This module provides production-ready services for running EVOSEAL's
bidirectional evolution system continuously.
"""

from .continuous_evolution_service import ContinuousEvolutionService

__all__ = ["ContinuousEvolutionService"]

__version__ = "0.1.0"

"""
SEAL (Self-Adapting Language Models) Integration

This package provides integration with SEAL (Self-Adapting Language Models),
including knowledge management, self-editing, and prompt processing.
"""

from evoseal.integration.seal.seal_interface import SEALInterface, SEALProvider
from evoseal.integration.seal.seal_system import SEALSystem

# Re-export key components
# Alias for backward compatibility
SEALConfig = SEALSystem.Config

__all__ = [
    'SEALInterface',
    'SEALProvider',
    'SEALSystem',
    'SEALConfig',
]

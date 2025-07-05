"""
SEAL (Self-Adapting Language Models) Integration

This package provides integration with SEAL (Self-Adapting Language Models),
including knowledge management, self-editing, and prompt processing.
"""

from evoseal.integration.seal.enhanced_seal_system import EnhancedSEALSystem, SEALConfig
from evoseal.integration.seal.seal_interface import SEALInterface, SEALProvider

# Re-export key components
# Maintain backward compatibility with old imports
SEALSystem = EnhancedSEALSystem

__all__ = [
    "SEALInterface",
    "SEALProvider",
    "EnhancedSEALSystem",
    "SEALSystem",  # For backward compatibility
    "SEALConfig",
]

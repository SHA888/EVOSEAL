"""
SelfEditor module for the SEAL system.

This module provides the SelfEditor class that enables the system to review and improve its own outputs.
"""

from evoseal.integration.seal.self_editor.self_editor import (
    SelfEditor,
    EditSuggestion,
    EditOperation,
    EditCriteria,
    EditHistory,
    EditStrategy,
    DefaultEditStrategy
)

__all__ = [
    "SelfEditor",
    "EditSuggestion",
    "EditOperation",
    "EditCriteria",
    "EditHistory",
    "EditStrategy",
    "DefaultEditStrategy"
]

"""
SelfEditor module for the SEAL system.

This module provides the SelfEditor class that enables the system to review and improve its own outputs.
"""

from .models import (
    EditSuggestion,
    EditOperation,
    EditCriteria,
    EditHistoryEntry,
    ContentState,
    EditResult
)

from .self_editor import (
    SelfEditor,
    EditStrategy,
    DefaultEditStrategy
)

from .strategies import (
    BaseEditStrategy,
    CodeStyleStrategy,
    KnowledgeAwareStrategy
)

__all__ = [
    # Core classes
    'SelfEditor',
    'EditStrategy',
    'DefaultEditStrategy',
    
    # Models
    'EditSuggestion',
    'EditOperation',
    'EditCriteria',
    'EditHistoryEntry',
    'ContentState',
    'EditResult',
    
    # Strategies
    'BaseEditStrategy',
    'CodeStyleStrategy',
    'KnowledgeAwareStrategy',
    "EditSuggestion",
    "EditOperation",
    "EditCriteria",
    "EditHistory",
    "EditStrategy",
    "DefaultEditStrategy",
    "KnowledgeAwareStrategy"
]

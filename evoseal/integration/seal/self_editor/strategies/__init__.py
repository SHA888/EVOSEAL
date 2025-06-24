"""
Edit strategies for the SelfEditor.

This package contains various editing strategies that can be used with the SelfEditor.
"""

from .knowledge_aware_strategy import KnowledgeAwareStrategy
from .base_strategy import BaseEditStrategy
from .code_style_strategy import CodeStyleStrategy
from .documentation_strategy import DocumentationStrategy, DocumentationConfig, DocstringStyle
from .security_analysis_strategy import SecurityAnalysisStrategy, SecurityConfig, SecurityIssueSeverity

__all__ = [
    'BaseEditStrategy',
    'CodeStyleStrategy',
    'DocumentationStrategy',
    'DocumentationConfig',
    'DocstringStyle',
    'KnowledgeAwareStrategy',
    'SecurityAnalysisStrategy',
    'SecurityConfig',
    'SecurityIssueSeverity'
]

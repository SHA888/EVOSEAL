"""
Prompt construction utilities for the SEAL system.

This module provides tools for constructing and formatting prompts with integrated
knowledge, examples, and context. It supports various prompt styles and templates
for different use cases.
"""

from .constructor import PromptConstructor, PromptStyle, PromptTemplate
from .default_templates import BASE_TEMPLATES, DOMAIN_TEMPLATES, SYSTEM_TEMPLATES, get_all_templates
from .formatters import format_context, format_examples, format_knowledge, format_prompt

# Initialize default templates
DEFAULT_TEMPLATES = get_all_templates()

__all__ = [
    # Core classes
    "PromptConstructor",
    "PromptStyle",
    "PromptTemplate",
    # Formatting functions
    "format_knowledge",
    "format_examples",
    "format_context",
    "format_prompt",
    # Template collections
    "DEFAULT_TEMPLATES",
    "BASE_TEMPLATES",
    "DOMAIN_TEMPLATES",
    "SYSTEM_TEMPLATES",
    "get_all_templates",
]

"""
Prompt template management for EVOSEAL.

This module provides functionality for loading and managing prompt templates
used throughout the EVOSEAL system.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

# Default templates that are built into the package
DEFAULT_TEMPLATES: dict[str, str] = {
    # Add default templates here if needed
}

# Backward compatibility templates
BACKWARD_COMPAT_TEMPLATES: dict[str, str] = {
    "diff_user": "diff_user template content",
    "diff_system": "diff_system template content",
}

# Template metadata
TEMPLATE_METADATA = {
    "diagnose_improvement_prompt": {
        "category": "evaluation",
        "version": "1",
        "description": "Template for diagnosing improvements",
    },
    "self_improvement_prompt_emptypatches": {
        "category": "self-improvement",
        "version": "1",
        "description": "Self-improvement template for empty patches",
    },
    "self_improvement_prompt_stochasticity": {
        "category": "self-improvement",
        "version": "1",
        "description": "Self-improvement template for handling stochasticity",
    },
    "diagnose_improvement_system_message": {
        "category": "evaluation",
        "version": "1",
        "description": "System message for improvement diagnosis",
    },
    "self_improvement_instructions": {
        "category": "self-improvement",
        "version": "1",
        "description": "Instructions for self-improvement",
    },
    "testrepo_test_command": {
        "category": "testing",
        "version": "1",
        "description": "Test command template",
    },
    "testrepo_test_description": {
        "category": "testing",
        "version": "1",
        "description": "Test description template",
    },
    "tooluse_prompt": {
        "category": "tools",
        "version": "1",
        "description": "Template for tool usage",
    },
}


class TemplateManager:
    """Manages templates for prompt generation.

    This class handles loading templates from files and providing access to them.
    Templates can be loaded from a directory or added programmatically.
    """

    def __init__(self, template_dir: str | None = None) -> None:
        """Initialize the TemplateManager.

        Args:
            template_dir: Optional directory path to load templates from
        """
        # Initialize with default OpenEvolve templates for backward compatibility
        self.templates: dict[str, str] = {
            "system_message": "You are an expert software developer tasked with iteratively improving a codebase.\nYour job is to analyze the current program and suggest improvements based on feedback from previous attempts.\nFocus on making targeted changes that will increase the program's performance metrics.\n",
            "evaluator_system_message": "You are an expert code reviewer.\nYour job is to analyze the provided code and evaluate it systematically.",
            "diff_user": "# Current Program Information\n- Current performance metrics: {metrics}\n- Areas identified for improvement: {improvement_areas}\n\n{artifacts}\n\n# Program Evolution History\n{evolution_history}\n\n# Current Program\n```{language}\n{current_program}\n```\n\n# Task\nSuggest improvements to the program that will lead to better performance on the specified metrics.\n\nYou MUST use the exact SEARCH/REPLACE diff format shown below to indicate changes:\n\n<<<<<<< SEARCH\n# Original code to find and replace (must match exactly)\n=======\n# New replacement code\n>>>>>>> REPLACE\n\nExample of valid diff format:\n<<<<<<< SEARCH\nfor i in range(m):\n    for j in range(p):\n        for k in range(n):\n            C[i, j] += A[i, k] * B[k, j]\n=======\n# Reorder loops for better memory access pattern\nfor i in range(m):\n    for k in range(n):\n        for j in range(p):\n            C[i, j] += A[i, k] * B[k, j]\n>>>>>>> REPLACE\n\nYou can suggest multiple changes. Each SEARCH section must exactly match code in the current program.\nBe thoughtful about your changes and explain your reasoning thoroughly.\n\nIMPORTANT: Do not rewrite the entire program - focus on targeted improvements.",
            "full_rewrite_user": "# Current Program Information\n- Current performance metrics: {metrics}\n- Areas identified for improvement: {improvement_areas}\n\n{artifacts}\n\n# Program Evolution History\n{evolution_history}\n\n# Current Program\n```{language}\n{current_program}\n```\n\n# Task\nRewrite the program to improve its performance on the specified metrics.\nProvide the complete new program code.\n\nIMPORTANT: Make sure your rewritten program maintains the same inputs and outputs\nas the original program, but with improved internal implementation.\n\n```{language}\n# Your rewritten program here\n```",
            "evolution_history": "## Previous Attempts\n\n{previous_attempts}\n\n## Top Performing Programs\n\n{top_programs}",
            "previous_attempt": "### Attempt {attempt_number}\n- Changes: {changes}\n- Performance: {performance}\n- Outcome: {outcome}",
            "top_program": "### Program {program_number} (Score: {score})\n```{language}\n{program_snippet}\n```\nKey features: {key_features}",
            "evaluation": 'Evaluate the following code on a scale of 0.0 to 1.0 for the following metrics:\n1. Readability: How easy is the code to read and understand?\n2. Maintainability: How easy would the code be to maintain and modify?\n3. Efficiency: How efficient is the code in terms of time and space complexity?\n\nFor each metric, provide a score between 0.0 and 1.0, where 1.0 is best.\n\nCode to evaluate:\n```python\n{current_program}\n```\n\nReturn your evaluation as a JSON object with the following format:\n{{\n    "readability": [score],\n    "maintainability": [score],\n    "efficiency": [score],\n    "reasoning": "[brief explanation of scores]"\n}}',
        }
        self.metadata = TEMPLATE_METADATA.copy()

        if template_dir and os.path.isdir(template_dir):
            self._load_templates_from_dir(template_dir)

    def _load_templates_from_dir(self, template_dir: str | os.PathLike[str]) -> None:
        """Load templates from a directory.

        Args:
            template_dir: Directory path containing template files
        """
        template_path = Path(template_dir)
        for file_path in template_path.glob("*.txt"):
            template_name = file_path.stem
            try:
                with open(file_path, encoding="utf-8") as f:
                    self.templates[template_name] = f.read()
            except OSError as e:
                print(f"Error loading template {file_path}: {e}")

    def get_template(self, template_name: str, version: int | None = None) -> str:
        """Get a template by name.

        Args:
            template_name: Name of the template to retrieve
            version: Optional version number (for backward compatibility)

        Returns:
            The template content as a string

        Raises:
            ValueError: If the template is not found
        """
        # Check for backward compatibility
        if template_name in BACKWARD_COMPAT_TEMPLATES:
            return BACKWARD_COMPAT_TEMPLATES[template_name]

        # Check if template exists
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        return self.templates[template_name]

    def list_templates(self) -> list[str]:
        """List all available template names.

        Returns:
            List of template names
        """
        return list(self.templates.keys())

    def get_metadata(self, template_name: str) -> dict[str, Any]:
        """Get metadata for a template.

        Args:
            template_name: Name of the template

        Returns:
            Dictionary containing template metadata

        Raises:
            ValueError: If the template is not found
        """
        if template_name not in self.templates and template_name not in BACKWARD_COMPAT_TEMPLATES:
            raise ValueError(f"Template '{template_name}' not found")

        metadata = TEMPLATE_METADATA.get(template_name, {})

        # For backward compatibility templates
        if template_name in BACKWARD_COMPAT_TEMPLATES and not metadata:
            metadata = {
                "name": template_name,
                "category": "legacy",
                "version": "1",
                "description": f"Backward compatibility template for {template_name}",
            }

        # Return default metadata if none found
        if not metadata:
            metadata = {"name": template_name, "category": "unknown", "version": "1"}

        return metadata

    def get_by_category(self, category: str) -> dict[str, str]:
        """Get all templates in a specific category.

        Args:
            category: Category name to filter by

        Returns:
            Dictionary mapping template names to template content for the given category
        """
        return {
            name: self.get_template(name)
            for name, meta in TEMPLATE_METADATA.items()
            if meta.get("category") == category and name in self.templates
        }

    def add_template(self, template_name: str, template: str) -> None:
        """Add or update a template.

        Args:
            template_name: Name of the template
            template: Template content
        """
        self.templates[template_name] = template

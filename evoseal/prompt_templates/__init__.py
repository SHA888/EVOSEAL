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
        self.templates: dict[str, str] = DEFAULT_TEMPLATES.copy()

        # Load templates from directory if provided
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
        if (
            template_name not in self.templates
            and template_name not in BACKWARD_COMPAT_TEMPLATES
        ):
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

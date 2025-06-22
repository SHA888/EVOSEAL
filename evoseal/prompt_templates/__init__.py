"""
Prompt template management for EVOSEAL.

This module provides functionality for loading and managing prompt templates
used throughout the EVOSEAL system.
"""

import os
from pathlib import Path
from typing import Dict, Optional, Any

# Default templates that are built into the package
DEFAULT_TEMPLATES = {
    # Add default templates here if needed
}

# Backward compatibility templates
BACKWARD_COMPAT_TEMPLATES = {
    'diff_user': 'diff_user template content',
    'diff_system': 'diff_system template content'
}

# Template metadata
TEMPLATE_METADATA = {
    'diagnose_improvement_prompt': {
        'category': 'evaluation',
        'version': '1',
        'description': 'Template for diagnosing improvements'
    },
    'self_improvement_prompt_emptypatches': {
        'category': 'self-improvement',
        'version': '1',
        'description': 'Self-improvement template for empty patches'
    },
    'self_improvement_prompt_stochasticity': {
        'category': 'self-improvement',
        'version': '1',
        'description': 'Self-improvement template for handling stochasticity'
    },
    'diagnose_improvement_system_message': {
        'category': 'evaluation',
        'version': '1',
        'description': 'System message for improvement diagnosis'
    },
    'self_improvement_instructions': {
        'category': 'self-improvement',
        'version': '1',
        'description': 'Instructions for self-improvement'
    },
    'testrepo_test_command': {
        'category': 'testing',
        'version': '1',
        'description': 'Test command template'
    },
    'testrepo_test_description': {
        'category': 'testing',
        'version': '1',
        'description': 'Test description template'
    },
    'tooluse_prompt': {
        'category': 'tools',
        'version': '1',
        'description': 'Template for tool usage'
    }
}


class TemplateManager:
    """Manages templates for prompt generation.
    
    This class handles loading templates from files and providing access to them.
    Templates can be loaded from a directory or added programmatically.
    """

    def __init__(self, template_dir: Optional[str] = None):
        """Initialize the TemplateManager.
        
        Args:
            template_dir: Optional directory path to load templates from
        """
        self.templates = DEFAULT_TEMPLATES.copy()

        # Load templates from directory if provided
        if template_dir and os.path.isdir(template_dir):
            self._load_templates_from_dir(template_dir)

    def _load_templates_from_dir(self, template_dir: str) -> None:
        """Load templates from a directory.
        
        Args:
            template_dir: Directory path containing template files
        """
        template_dir = Path(template_dir)
        for template_file in template_dir.glob("*.txt"):
            template_name = template_file.stem
            with open(template_file, 'r', encoding='utf-8') as f:
                self.templates[template_name] = f.read()
        
        # Add backward compatibility templates
        self.templates.update(BACKWARD_COMPAT_TEMPLATES)

    def get_template(self, template_name: str, version: Optional[int] = None) -> str:
        """Get a template by name.
        
        Args:
            template_name: Name of the template to retrieve
            version: Optional version number (for backward compatibility)
            
        Returns:
            The template content as a string
            
        Raises:
            ValueError: If the template is not found
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        return self.templates[template_name]
    
    def list_templates(self) -> list[str]:
        """List all available template names.
        
        Returns:
            List of template names
        """
        return list(self.templates.keys())
    
    def get_metadata(self, template_name: str) -> Dict[str, str]:
        """Get metadata for a template.
        
        Args:
            template_name: Name of the template
            
        Returns:
            Dictionary containing template metadata
            
        Raises:
            ValueError: If the template is not found
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")
        
        # Return stored metadata if available
        if template_name in TEMPLATE_METADATA:
            return {
                'name': template_name,
                **TEMPLATE_METADATA[template_name]
            }
        
        # For backward compatibility templates
        if template_name in BACKWARD_COMPAT_TEMPLATES:
            return {
                'name': template_name,
                'category': 'compat',
                'version': '1',
                'description': f'Backward compatibility template for {template_name}'
            }
            
        # Default metadata for other templates
        return {
            'name': template_name,
            'category': 'general',
            'version': '1',
            'description': ''
        }
    
    def get_by_category(self, category: str) -> Dict[str, str]:
        """Get all templates in a specific category.
        
        Args:
            category: Category name to filter by
            
        Returns:
            Dictionary mapping template names to template content for the given category
        """
        # This is a simple implementation - in a real system, you might want to
        # maintain a separate index of templates by category
        return {
            name: content for name, content in self.templates.items()
            if self.get_metadata(name).get("category") == category
        }
    
    def add_template(self, template_name: str, template: str) -> None:
        """Add or update a template.
        
        Args:
            template_name: Name of the template
            template: Template content
        """
        self.templates[template_name] = template

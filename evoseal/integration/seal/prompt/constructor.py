"""
Prompt construction and management.

This module provides functionality for constructing prompts with integrated
knowledge and examples, supporting different prompt styles and formats.
"""

import re
from typing import Any, Dict, List, Optional, Set, Union

from ..types import PromptStyle
from ..types import PromptTemplate as BasePromptTemplate


class PromptTemplate(BasePromptTemplate):
    """A template for generating prompts with variables.

    Extends the base PromptTemplate with additional functionality.
    """

    def __init__(
        self,
        name: str,
        template: str,
        description: str = "",
        style: Union[str, PromptStyle] = PromptStyle.INSTRUCTION,
        required_fields: Optional[Set[str]] = None,
        version: str = "1.0",
    ):
        """Initialize the prompt template with validation.

        Args:
            name: Unique identifier for the template
            template: The template string with {placeholders}
            description: Human-readable description of the template's purpose
            style: The style of the template (e.g., INSTRUCTION, CHAT)
            required_fields: Set of required template variables
            version: Optional version identifier
        """
        super().__init__(
            name=name,
            template=template,
            description=description,
            style=style,
            required_fields=required_fields or set(),
            version=version,
        )

        # Convert style string to enum if needed
        if isinstance(self.style, str):
            try:
                self.style = PromptStyle(self.style.lower())
            except ValueError:
                # If it's not a standard style, keep as is
                pass


class PromptConstructor:
    """Constructs prompts by combining templates with dynamic content."""

    def __init__(
        self,
        default_style: PromptStyle = PromptStyle.INSTRUCTION,
        templates: Optional[Dict[str, PromptTemplate]] = None,
    ):
        """Initialize the prompt constructor.

        Args:
            default_style: Default prompt style to use
            templates: Optional dictionary of named templates
        """
        self.default_style = default_style
        self.templates = templates or {}
        self._register_default_templates()

    def _register_default_templates(self):
        """Register default templates for common use cases."""
        default_templates = {
            "basic_instruction": PromptTemplate(
                name="basic_instruction",
                template=(
                    "You are a helpful AI assistant. Based on the following knowledge:\n"
                    "{knowledge}\n\n"
                    "Answer the following question: {question}"
                ),
                style=PromptStyle.INSTRUCTION,
                required_fields=["question"],
                description="Basic instruction-following prompt with knowledge",
            ),
            "chat": PromptTemplate(
                name="chat",
                template=(
                    "System: You are a helpful AI assistant.\n"
                    "{knowledge_section}"
                    "{chat_history}"
                    "User: {user_input}\n"
                    "Assistant:"
                ),
                style=PromptStyle.CHAT,
                required_fields=["user_input"],
                description="Chat-style prompt with conversation history",
            ),
            "chain_of_thought": PromptTemplate(
                name="chain_of_thought",
                template=(
                    "Question: {question}\n" "Knowledge:\n{knowledge}\n" "Let's think step by step."
                ),
                style=PromptStyle.CHAIN_OF_THOUGHT,
                required_fields=["question"],
                description="Chain-of-thought style prompt for reasoning tasks",
            ),
        }

        for name, template in default_templates.items():
            if name not in self.templates:
                self.templates[name] = template

    def create_prompt(self, template_name: str, **kwargs: Any) -> str:
        """Create a prompt using a named template.

        Args:
            template_name: Name of the template to use
            **kwargs: Values to fill in the template placeholders

        Returns:
            Formatted prompt string

        Raises:
            ValueError: If template_name is not found or required fields are missing
        """
        if template_name not in self.templates:
            raise ValueError(f"Template '{template_name}' not found")

        template = self.templates[template_name]
        return template.template.format(**kwargs)

    def format_with_style(
        self,
        content: str,
        style: Optional[Union[str, PromptStyle]] = None,
        **kwargs: Any,
    ) -> str:
        """Format content with a specific style.

        Args:
            content: The main content to format
            style: Style to apply (defaults to instance default)
            **kwargs: Additional style-specific parameters

        Returns:
            Formatted prompt string
        """
        style_enum = PromptStyle(style) if isinstance(style, str) else (style or self.default_style)

        if style_enum == PromptStyle.INSTRUCTION:
            return f"Instruction: {content}\n\nResponse:"
        elif style_enum == PromptStyle.CHAT:
            role = kwargs.get("role", "user")
            return f"{role.capitalize()}: {content}"
        elif style_enum == PromptStyle.COMPLETION:
            return content
        elif style_enum == PromptStyle.CHAIN_OF_THOUGHT:
            return f"Question: {content}\nLet's think step by step."
        else:
            return content

    def add_template(
        self,
        name_or_template: Union[str, PromptTemplate],
        template: Optional[str] = None,
        style: Optional[Union[str, PromptStyle]] = None,
        description: str = "",
        required_fields: Optional[Set[str]] = None,
    ) -> None:
        """Add a new template to the constructor.

        Args:
            name_or_template: Either the template name (str) or a PromptTemplate instance
            template: Template string with {placeholders} (if name_or_template is a string)
            style: Style of the template (e.g., "instruction", "chat") (if name_or_template is a string)
            description: Human-readable description of the template's purpose
            required_fields: Set of required template variables
        """
        if isinstance(name_or_template, PromptTemplate):
            # If a template object is provided, just store it
            self.templates[name_or_template.name] = name_or_template
            return

        # Otherwise, create a new template from parameters
        name = name_or_template
        if template is None or style is None:
            raise ValueError("Both template and style must be provided when name is a string")

        if not required_fields:
            required_fields = set()

        # Extract placeholders from template
        placeholders = set(re.findall(r"\{([^}]+)\}", template))

        # Add any placeholders that are required by the template
        required_fields.update(placeholders)

        # Create and store the template
        self.templates[name] = PromptTemplate(
            name=name,
            template=template,
            style=style,
            description=description,
            required_fields=required_fields,
        )

    def get_template(self, name: str) -> PromptTemplate:
        """Get a template by name.

        Args:
            name: Name of the template to retrieve

        Returns:
            The requested PromptTemplate

        Raises:
            ValueError: If template is not found
        """
        if name not in self.templates:
            raise ValueError(f"Template '{name}' not found")
        return self.templates[name]

    def list_templates(self) -> Dict[str, Dict[str, Any]]:
        """List all available templates with their metadata.

        Returns:
            Dictionary mapping template names to their metadata
        """
        return {
            name: {
                "style": template.style.value,
                "required_fields": template.required_fields,
                "description": template.description,
            }
            for name, template in self.templates.items()
        }

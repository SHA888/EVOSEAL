"""Default prompt templates for the SEAL system.

This module contains pre-defined prompt templates for common use cases in the SEAL system.
Templates are organized by style and purpose for easy reuse and maintenance.
"""

from typing import Dict, List

from ..types import PromptTemplate

# Base templates that can be extended or used directly
BASE_TEMPLATES: Dict[str, str] = {
    "instruction": (
        "You are a helpful AI assistant. Use the following information to answer the question.\n\n"
        "{knowledge}\n\n"
        "Question: {question}\n"
        "Answer:"
    ),
    "chat": (
        "The following is a conversation with an AI assistant. The assistant is helpful, creative, clever, and very friendly.\n\n"
        "Context:\n{knowledge}\n\n"
        "### User:\n{user_input}\n\n"
        "### Assistant:"
    ),
    "completion": (
        "Complete the following text using the provided context.\n\n"
        "Context:\n{knowledge}\n\n"
        "Text to complete: {user_input}"
    ),
    "chain_of_thought": (
        "Answer the following question using the provided knowledge. "
        "Explain your reasoning step by step.\n\n"
        "Knowledge:\n{knowledge}\n\n"
        "Question: {question}\n"
        "Let's think step by step:"
    ),
}

# Domain-specific templates
DOMAIN_TEMPLATES: Dict[str, str] = {
    "code_generation": (
        "You are an expert programming assistant. Generate code based on the following requirements.\n\n"
        "Context:\n{knowledge}\n\n"
        "Requirements:\n{user_input}\n\n"
        "Code:"
    ),
    "code_explanation": (
        "Explain the following code in detail. Describe what it does, how it works, and any important considerations.\n\n"
        "Additional context:\n{knowledge}\n\n"
        "Code to explain:\n{user_input}\n\n"
        "Explanation:"
    ),
    "documentation": (
        "Generate documentation for the following code. Include a description, parameters, return values, and examples.\n\n"
        "Code context:\n{knowledge}\n\n"
        "Code to document:\n{user_input}\n\n"
        "Documentation:"
    ),
}

# System message templates
SYSTEM_TEMPLATES: Dict[str, str] = {
    "default_system": (
        "You are a helpful AI assistant. Your responses should be accurate, concise, and helpful. "
        "Use the provided knowledge to inform your answers when available."
    ),
    "expert_system": (
        "You are an expert in your field with deep knowledge and experience. "
        "Provide detailed, accurate, and professional responses. "
        "Use the provided knowledge to support your answers when relevant."
    ),
    "friendly_system": (
        "You are a friendly and approachable AI assistant. "
        "Keep your responses warm, engaging, and easy to understand. "
        "Use the provided knowledge to enhance your answers when helpful."
    ),
}


def get_all_templates() -> Dict[str, PromptTemplate]:
    """Get all default templates as PromptTemplate objects.

    Returns:
        Dictionary mapping template names to PromptTemplate objects
    """
    all_templates = {}

    # Add base templates
    for name, template in BASE_TEMPLATES.items():
        # Determine required fields based on template type
        if name == "chat":
            required_fields = {"user_input"}
        elif name == "completion":
            required_fields = {"user_input"}
        else:
            required_fields = {"question"}

        # Add knowledge if the template uses it
        if "{knowledge}" in template:
            required_fields.add("knowledge")

        all_templates[f"base_{name}"] = PromptTemplate(
            name=f"base_{name}",
            template=template,
            description=f"Base {name.replace('_', ' ')} template",
            style=name.upper(),
            required_fields=required_fields,
        )

    # Add domain templates
    for name, template in DOMAIN_TEMPLATES.items():
        required_fields = {"user_input"}
        if "{knowledge}" in template:
            required_fields.add("knowledge")

        all_templates[name] = PromptTemplate(
            name=name,
            template=template,
            description=f"Template for {name.replace('_', ' ')}",
            style="INSTRUCTION",
            required_fields=required_fields,
        )

    # Add system templates
    for name, template in SYSTEM_TEMPLATES.items():
        all_templates[f"system_{name}"] = PromptTemplate(
            name=f"system_{name}",
            template=template,
            description=f"System message: {name.replace('_', ' ')}",
            style="SYSTEM",
            required_fields=set(),
        )

    return all_templates

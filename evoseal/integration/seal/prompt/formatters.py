"""
Prompt formatting utilities for the SEAL system.

This module provides functions for formatting different parts of prompts,
such as knowledge, examples, and context, in a consistent way.
"""

from typing import Any, Dict, List, Optional, Union


def format_knowledge(
    knowledge: Union[str, List[Dict[str, Any]], None],
    max_items: int = 5,
    max_length: int = 1000,
) -> str:
    """Format knowledge for inclusion in a prompt.

    Args:
        knowledge: Knowledge to format. Can be a string, list of dicts, or None.
        max_items: Maximum number of knowledge items to include
        max_length: Maximum total length of the formatted knowledge

    Returns:
        Formatted knowledge string
    """
    if not knowledge:
        return "No relevant knowledge available."

    if isinstance(knowledge, str):
        # Truncate if necessary
        return knowledge[:max_length] + ("..." if len(knowledge) > max_length else "")

    if not isinstance(knowledge, list):
        return str(knowledge)[:max_length] + ("..." if len(str(knowledge)) > max_length else "")

    # Handle list of knowledge items
    formatted = []
    total_length = 0

    for i, item in enumerate(knowledge[:max_items]):
        if total_length >= max_length:
            break

        if isinstance(item, dict):
            # Format dict items with their content
            content = item.get("content", "")
            source = item.get("source", "")
            score = item.get("score", "")

            item_str = f"- {content}"
            if source:
                item_str += f" (Source: {source})"
            if score is not None:
                item_str += f" [Relevance: {score:.2f}]"
        else:
            item_str = f"- {str(item)}"

        # Check if adding this item would exceed max_length
        if total_length + len(item_str) + 2 > max_length:  # +2 for newlines
            remaining = max_length - total_length
            if remaining > 3:  # Enough space for "..."
                formatted.append(item_str[: remaining - 3] + "...")
            break

        formatted.append(item_str)
        total_length += len(item_str) + 2  # +2 for newline

    if not formatted:
        return "No relevant knowledge available."

    return "\n".join(formatted)


def format_examples(examples: Union[str, List[Dict[str, str]], None], max_examples: int = 3) -> str:
    """Format examples for inclusion in a prompt.

    Args:
        examples: Examples to format. Can be a string, list of dicts, or None.
        max_examples: Maximum number of examples to include

    Returns:
        Formatted examples string
    """
    if not examples:
        return ""

    if isinstance(examples, str):
        return f"\n\nExamples:\n{examples}"

    if not isinstance(examples, list):
        return ""

    formatted = ["\n\nExamples:"]

    for i, example in enumerate(examples[:max_examples]):
        if not isinstance(example, dict):
            continue

        input_text = example.get("input", "")
        output_text = example.get("output", "")

        if input_text and output_text:
            formatted.append(f"Input: {input_text}")
            formatted.append(f"Output: {output_text}")
            formatted.append("")

    return "\n".join(formatted).strip()


def format_context(
    context: Optional[Dict[str, Any]] = None,
    include_keys: Optional[List[str]] = None,
    exclude_keys: Optional[List[str]] = None,
) -> str:
    """Format context dictionary into a string for the prompt.

    Args:
        context: Context dictionary to format
        include_keys: Optional list of keys to include (if None, include all)
        exclude_keys: Optional list of keys to exclude

    Returns:
        Formatted context string
    """
    if not context:
        return ""

    # Filter keys
    keys = set(context.keys())

    if include_keys is not None:
        keys = keys.intersection(include_keys)

    if exclude_keys is not None:
        keys = keys.difference(exclude_keys)

    if not keys:
        return ""

    # Format each key-value pair
    parts = []
    for key in sorted(keys):
        value = context[key]
        if value is not None:
            if isinstance(value, (list, dict)) and not value:
                continue  # Skip empty lists/dicts
            parts.append(f"{key}: {value}")

    if not parts:
        return ""

    return "\n".join(["\nContext:", "\n".join(parts)])


def format_prompt(
    template: str,
    knowledge: Union[str, List[Dict[str, Any]], None] = None,
    examples: Union[str, List[Dict[str, str]], None] = None,
    context: Optional[Dict[str, Any]] = None,
    **kwargs: Any,
) -> str:
    """Format a complete prompt with knowledge, examples, and context.

    Args:
        template: Template string with {placeholders}
        knowledge: Knowledge to include in the prompt
        examples: Examples to include in the prompt
        context: Additional context to include
        **kwargs: Additional template variables

    Returns:
        Formatted prompt string with placeholders preserved for missing variables
    """
    # Create a copy of kwargs to avoid modifying the original
    format_kwargs = dict(kwargs)

    # Format knowledge if provided and expected in template
    if "{knowledge}" in template:
        format_kwargs["knowledge"] = format_knowledge(knowledge) if knowledge is not None else ""

    # Format examples if expected in template
    if "{examples}" in template:
        format_kwargs["examples"] = format_examples(examples) if examples is not None else ""

    # Add context if expected in template
    if context and "{context}" in template:
        context_str = format_context(context)
        format_kwargs["context"] = context_str if context_str else ""

    # Use a custom formatter that preserves missing placeholders
    class DefaultFormatter(dict):
        def __missing__(self, key):
            return f"{{{key}}}"

    # Format the template with all variables
    return template.format_map(DefaultFormatter(**format_kwargs))

"""Tests for prompt construction functionality."""

from unittest.mock import MagicMock, patch

import pytest

from evoseal.integration.seal.prompt import (
    PromptConstructor,
    PromptStyle,
    format_context,
    format_examples,
    format_knowledge,
    format_prompt,
)


class TestPromptConstructor:
    """Tests for the PromptConstructor class."""

    def test_initialization(self):
        """Test that the constructor initializes with defaults."""
        constructor = PromptConstructor()
        assert constructor.default_style == PromptStyle.INSTRUCTION
        assert len(constructor.templates) > 0  # Should have default templates

    def test_add_template(self):
        """Test adding a new template."""
        constructor = PromptConstructor()
        template_name = "test_template"
        template = "This is a {test} template."

        # Add a new template
        constructor.add_template(
            template_name,
            template=template,
            style=PromptStyle.INSTRUCTION,
            required_fields={"test"},
            description="A test template",
        )

        # Verify template was added
        assert template_name in constructor.templates
        assert constructor.templates[template_name].template == template
        assert "test" in constructor.templates[template_name].required_fields

    def test_create_prompt(self):
        """Test creating a prompt from a template."""
        constructor = PromptConstructor()

        # Create a prompt using the basic_instruction template
        result = constructor.create_prompt(
            "basic_instruction",
            question="What is the capital of France?",
            knowledge="Paris is the capital of France.",
        )

        assert "What is the capital of France?" in result
        assert "Paris is the capital of France" in result

    def test_format_with_style(self):
        """Test formatting content with different styles."""
        constructor = PromptConstructor()

        # Test instruction style
        result = constructor.format_with_style("Do something", PromptStyle.INSTRUCTION)
        assert result.startswith("Instruction: ")

        # Test chat style
        result = constructor.format_with_style("Hello", PromptStyle.CHAT, role="user")
        assert result == "User: Hello"

        # Test chain of thought
        result = constructor.format_with_style("Solve this", PromptStyle.CHAIN_OF_THOUGHT)
        assert "Let's think step by step" in result


class TestFormatKnowledge:
    """Tests for the format_knowledge function."""

    def test_format_knowledge_none(self):
        """Test formatting None knowledge."""
        assert "No relevant knowledge" in format_knowledge(None)

    def test_format_knowledge_string(self):
        """Test formatting string knowledge."""
        knowledge = "This is some knowledge."
        assert format_knowledge(knowledge) == knowledge

    def test_format_knowledge_list(self):
        """Test formatting knowledge as a list of dicts."""
        knowledge = [
            {"content": "Fact 1", "source": "source1", "score": 0.9},
            {"content": "Fact 2", "source": "source2", "score": 0.8},
        ]
        result = format_knowledge(knowledge)
        assert "Fact 1" in result
        assert "source1" in result
        assert "0.90" in result  # Check score formatting

    def test_format_knowledge_max_length(self):
        """Test that knowledge is truncated to max_length."""
        knowledge = "a" * 1000
        result = format_knowledge(knowledge, max_length=100)
        assert len(result) <= 103  # Account for "..."
        assert result.endswith("...")


class TestFormatExamples:
    """Tests for the format_examples function."""

    def test_format_examples_none(self):
        """Test formatting None examples."""
        assert format_examples(None) == ""

    def test_format_examples_string(self):
        """Test formatting examples as a string."""
        examples = "Example 1\nExample 2"
        result = format_examples(examples)
        assert "Examples:" in result
        assert "Example 1" in result

    def test_format_examples_list(self):
        """Test formatting examples as a list of dicts."""
        examples = [
            {"input": "Input 1", "output": "Output 1"},
            {"input": "Input 2", "output": "Output 2"},
        ]
        result = format_examples(examples)
        assert "Input: Input 1" in result
        assert "Output: Output 2" in result

    def test_format_examples_max_examples(self):
        """Test that only max_examples are included."""
        examples = [{"input": f"Input {i}", "output": f"Output {i}"} for i in range(5)]
        result = format_examples(examples, max_examples=2)
        assert "Input: Input 0" in result
        assert "Input: Input 1" in result
        assert "Input: Input 2" not in result


class TestFormatContext:
    """Tests for the format_context function."""

    def test_format_context_none(self):
        """Test formatting None context."""
        assert format_context(None) == ""

    def test_format_context_basic(self):
        """Test formatting a basic context dictionary."""
        context = {"key1": "value1", "key2": 42, "key3": None}
        result = format_context(context)
        assert "key1: value1" in result
        assert "key2: 42" in result
        assert "key3" not in result  # None values should be skipped

    def test_format_context_include_exclude(self):
        """Test include_keys and exclude_keys parameters."""
        context = {"key1": "value1", "key2": "value2", "key3": "value3"}

        # Test include_keys
        result = format_context(context, include_keys=["key1", "key2"])
        assert "key1" in result
        assert "key2" in result
        assert "key3" not in result

        # Test exclude_keys
        result = format_context(context, exclude_keys=["key3"])
        assert "key1" in result
        assert "key2" in result
        assert "key3" not in result


class TestFormatPrompt:
    """Tests for the format_prompt function."""

    def test_format_prompt_basic(self):
        """Test basic prompt formatting."""
        template = "Question: {question}\nAnswer:"
        result = format_prompt(template, question="What is the answer?")
        assert "Question: What is the answer?" in result

    def test_format_prompt_with_knowledge(self):
        """Test prompt formatting with knowledge."""
        template = "Context: {knowledge}\nQuestion: {question}\nAnswer:"
        result = format_prompt(
            template, question="What is the capital?", knowledge="Paris is the capital of France."
        )
        assert "Paris is the capital" in result
        assert "What is the capital?" in result

    def test_format_prompt_with_examples(self):
        """Test prompt formatting with examples."""
        template = "Examples:{examples}\n\nQuestion: {question}\nAnswer:"
        examples = [
            {"input": "2+2", "output": "4"},
            {"input": "3*3", "output": "9"},
        ]
        result = format_prompt(template, question="4*4", examples=examples)
        assert "Input: 2+2" in result
        assert "Output: 4" in result
        assert "4*4" in result

    def test_format_prompt_missing_vars(self):
        """Test that missing variables don't cause errors."""
        template = "This {missing} should not cause an error"
        result = format_prompt(template, question="test")
        assert "This {missing} should not cause an error" == result


if __name__ == "__main__":
    pytest.main([__file__])

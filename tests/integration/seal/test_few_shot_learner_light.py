"""Lightweight tests for FewShotLearner to avoid WSL crashes."""

import os
import sys
from pathlib import Path
from unittest.mock import ANY, MagicMock, patch

import pytest

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

# Import with mock to prevent actual model loading
with (
    patch("transformers.AutoModelForCausalLM.from_pretrained"),
    patch("transformers.AutoTokenizer.from_pretrained"),
):
    from evoseal.integration.seal.few_shot.few_shot_learner import (
        FewShotExample,
        FewShotLearner,
    )

# Simple test data
TEST_EXAMPLES = [
    FewShotExample(
        input_data="What is the capital of France?",
        output_data="The capital of France is Paris.",
        metadata={"source": "test"},
    )
]


def test_initialization():
    """Test that FewShotLearner initializes correctly."""
    with (
        patch("transformers.AutoModelForCausalLM.from_pretrained") as mock_model,
        patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer,
    ):

        # Setup mocks
        mock_tokenizer.return_value.pad_token = "[PAD]"
        mock_tokenizer.return_value.eos_token = "</s>"
        mock_tokenizer.return_value.pad_token_id = 0
        mock_model.return_value = MagicMock()

        # Test initialization with default model
        learner = FewShotLearner()
        assert learner is not None
        assert len(learner.examples) == 0


def test_add_and_clear_examples():
    """Test adding and clearing examples."""
    with (
        patch("transformers.AutoModelForCausalLM.from_pretrained") as mock_model,
        patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer,
    ):

        # Setup mocks
        mock_tokenizer.return_value.pad_token = "[PAD]"
        mock_tokenizer.return_value.eos_token = "</s>"
        mock_tokenizer.return_value.pad_token_id = 0
        mock_model.return_value = MagicMock()

        learner = FewShotLearner()

        # Add example
        learner.add_example(TEST_EXAMPLES[0])
        assert len(learner.examples) == 1
        assert learner.examples[0].input_data == "What is the capital of France?"

        # Clear examples
        learner.clear_examples()
        assert len(learner.examples) == 0


def test_format_prompt():
    """Test prompt formatting without actual model calls."""
    with (
        patch("transformers.AutoModelForCausalLM.from_pretrained") as mock_model,
        patch("transformers.AutoTokenizer.from_pretrained") as mock_tokenizer,
    ):

        # Setup mocks
        mock_tokenizer.return_value.pad_token = "[PAD]"
        mock_tokenizer.return_value.eos_token = "</s>"
        mock_tokenizer.return_value.pad_token_id = 0
        mock_model.return_value = MagicMock()

        learner = FewShotLearner()
        learner.add_example(TEST_EXAMPLES[0])

        # Test format prompt
        prompt = learner.format_prompt("What is the capital of Spain?")
        assert isinstance(prompt, str)
        assert "What is the capital of France?" in prompt
        assert "What is the capital of Spain?" in prompt


if __name__ == "__main__":
    # Run tests directly for better control
    print("🚀 Running lightweight tests...")
    test_initialization()
    test_format_prompt()
    print("✅ All lightweight tests passed!")

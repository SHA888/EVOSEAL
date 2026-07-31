"""Tests for ModelFineTuner.

Covers the format-mismatch gap (tokenization) and security defaults
(trust_remote_code must be False to prevent arbitrary code execution
from untrusted model repos).
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest
from datasets import Dataset

from evoseal.fine_tuning.model_fine_tuner import ModelFineTuner


@pytest.fixture()
def fine_tuner():
    ft = ModelFineTuner.__new__(ModelFineTuner)
    ft.tokenizer = MagicMock(
        side_effect=lambda texts, **kwargs: {"input_ids": [[1, 2, 3] for _ in texts]}
    )
    return ft


class TestTokenizeIfNeeded:
    def test_skips_already_tokenized_dataset(self, fine_tuner):
        ds = Dataset.from_list([{"input_ids": [1, 2, 3]}])

        result = fine_tuner._tokenize_if_needed(ds, max_length=512)

        assert result is ds
        fine_tuner.tokenizer.assert_not_called()

    def test_tokenizes_alpaca_format_dataset(self, fine_tuner):
        ds = Dataset.from_list(
            [
                {
                    "instruction": "Fix the bug",
                    "input": "def f(): pass",
                    "output": "def f(): return 1",
                }
            ]
        )

        result = fine_tuner._tokenize_if_needed(ds, max_length=512)

        assert "input_ids" in result.column_names
        assert "instruction" not in result.column_names
        assert "text" not in result.column_names
        fine_tuner.tokenizer.assert_called_once()

    def test_passes_max_length_through_to_tokenizer(self, fine_tuner):
        ds = Dataset.from_list([{"instruction": "i", "input": "", "output": "o"}])

        fine_tuner._tokenize_if_needed(ds, max_length=128)

        _, kwargs = fine_tuner.tokenizer.call_args
        assert kwargs["max_length"] == 128


class TestTrustRemoteCodeDefault:
    """Verify trust_remote_code defaults to False in initialize_model.

    trust_remote_code=True allows a HuggingFace repo to execute arbitrary
    Python code on load — a remote-code-execution vector when combined
    with the _resolve_hf_base_model() fallback that uses model_name
    verbatim as an HF repo id for unknown families.
    """

    def test_source_uses_trust_remote_code_false(self):
        """Inspect initialize_model source to confirm trust_remote_code=False."""
        source = inspect.getsource(ModelFineTuner.initialize_model)
        # Must NOT contain trust_remote_code=True (after the fix)
        assert "trust_remote_code=True" not in source, (
            "initialize_model still contains trust_remote_code=True"
        )
        # Must contain trust_remote_code=False
        assert "trust_remote_code=False" in source, (
            "initialize_model does not set trust_remote_code=False"
        )
        # No nosec B615 suppressions — the security flag is now safe
        assert "nosec B615" not in source, (
            "initialize_model still has nosec B615 suppression comments"
        )

    @pytest.mark.asyncio
    async def test_initialize_returns_false_without_transformers(self, tmp_path):
        """When TRANSFORMERS_AVAILABLE is False, initialize_model returns False."""
        tuner = ModelFineTuner.__new__(ModelFineTuner)
        tuner.model_name = "test-model"
        tuner.base_model_path = None
        tuner.output_dir = tmp_path
        tuner.use_lora = True
        tuner.use_qlora = False
        tuner.tokenizer = None
        tuner.model = None
        tuner.peft_model = None
        tuner.is_initialized = False
        tuner.current_training = None

        result = await tuner.initialize_model()

        assert result is False
        assert tuner.is_initialized is False

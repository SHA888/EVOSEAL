"""Tests for ModelFineTuner.

Covers the format-mismatch gap (tokenization) and security defaults
(trust_remote_code must be False to prevent arbitrary code execution
from untrusted model repos).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

    @pytest.mark.asyncio
    async def test_from_pretrained_calls_use_trust_remote_code_false(self, tmp_path):
        """Both from_pretrained calls receive trust_remote_code=False.

        Mocks the HF loading calls and asserts the kwarg on each,
        consistent with the style of test_passes_max_length_through_to_tokenizer.
        """
        import evoseal.fine_tuning.model_fine_tuner as mod

        tuner = ModelFineTuner.__new__(ModelFineTuner)
        tuner.model_name = "deepseek-coder"
        tuner.base_model_path = "deepseek-ai/deepseek-coder-6.7b-instruct"
        tuner.output_dir = tmp_path
        tuner.use_lora = True
        tuner.use_qlora = False
        tuner.tokenizer = None
        tuner.model = None
        tuner.peft_model = None
        tuner.is_initialized = False
        tuner.current_training = None

        mock_tokenizer = MagicMock()
        mock_tokenizer.pad_token = None
        mock_tokenizer.eos_token = "</s>"
        mock_model = MagicMock()
        mock_model.config = MagicMock()

        # AutoTokenizer / AutoModelForCausalLM aren't in the module namespace
        # because peft isn't installed (the try/except bailed early). Inject
        # mock classes so the function can reference them, then patch
        # from_pretrained on each.
        mock_tok_cls = MagicMock()
        mock_tok_cls.from_pretrained.return_value = mock_tokenizer
        mock_mdl_cls = MagicMock()
        mock_mdl_cls.from_pretrained.return_value = mock_model

        with (
            patch.object(mod, "TRANSFORMERS_AVAILABLE", True),
            patch.object(mod, "AutoTokenizer", mock_tok_cls, create=True),
            patch.object(mod, "AutoModelForCausalLM", mock_mdl_cls, create=True),
            patch("torch.cuda.is_available", return_value=False),
        ):
            result = await tuner.initialize_model()

        assert result is True

        # Tokenizer call must pass trust_remote_code=False
        _, tok_kwargs = mock_tok_cls.from_pretrained.call_args
        assert tok_kwargs["trust_remote_code"] is False, (
            "AutoTokenizer.from_pretrained called with trust_remote_code!=False"
        )

        # Model call must pass trust_remote_code=False
        _, mdl_kwargs = mock_mdl_cls.from_pretrained.call_args
        assert mdl_kwargs["trust_remote_code"] is False, (
            "AutoModelForCausalLM.from_pretrained called with trust_remote_code!=False"
        )

    @pytest.mark.asyncio
    async def test_initialize_returns_false_without_transformers(self, monkeypatch, tmp_path):
        """When TRANSFORMERS_AVAILABLE is False, initialize_model returns False."""
        import evoseal.fine_tuning.model_fine_tuner as mod

        monkeypatch.setattr(mod, "TRANSFORMERS_AVAILABLE", False)

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

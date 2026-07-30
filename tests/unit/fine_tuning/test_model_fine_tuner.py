"""Tests for ModelFineTuner._tokenize_if_needed.

Covers the format-mismatch gap: TrainingDataBuilder's HuggingFace export
writes raw instruction/input/output columns, but Trainer + DataCollatorFor-
LanguageModeling require pre-tokenized input_ids. fine_tune_model() must
tokenize on load when the dataset isn't already tokenized, and leave an
already-tokenized dataset untouched.
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


class TestInitializeModelGpuGuard:
    """Regression tests for the _check_gpu_availability early-exit path."""

    @pytest.fixture()
    def fine_tuner(self):
        ft = ModelFineTuner.__new__(ModelFineTuner)
        ft.model_name = "test-model"
        ft.is_initialized = False
        ft.model = None
        ft.tokenizer = None
        return ft

    @pytest.mark.asyncio
    async def test_returns_false_when_gpu_unavailable(self, fine_tuner):
        import evoseal.fine_tuning.model_fine_tuner as mod

        with (
            patch.object(mod, "TRANSFORMERS_AVAILABLE", True),
            patch.object(ModelFineTuner, "_check_gpu_availability", return_value=False),
        ):
            result = await fine_tuner.initialize_model()

        assert result is False
        assert fine_tuner.is_initialized is False

    @pytest.mark.asyncio
    async def test_does_not_load_model_when_gpu_unavailable(self, fine_tuner):
        import evoseal.fine_tuning.model_fine_tuner as mod

        with (
            patch.object(mod, "TRANSFORMERS_AVAILABLE", True),
            patch.object(ModelFineTuner, "_check_gpu_availability", return_value=False),
            patch.object(mod, "AutoTokenizer", create=True) as mock_tok,
            patch.object(mod, "AutoModelForCausalLM", create=True) as mock_model,
        ):
            await fine_tuner.initialize_model()

        mock_tok.from_pretrained.assert_not_called()
        mock_model.from_pretrained.assert_not_called()

    def test_gpu_check_returns_false_on_runtime_error(self, fine_tuner):
        """_check_gpu_availability catches non-ImportError exceptions (e.g. driver
        failures) and returns False instead of letting them propagate."""
        torch = pytest.importorskip("torch")

        import evoseal.fine_tuning.model_fine_tuner as mod

        with (
            patch.object(mod, "TRANSFORMERS_AVAILABLE", True),
            patch.object(torch.cuda, "is_available", side_effect=RuntimeError("CUDA driver error")),
        ):
            result = fine_tuner._check_gpu_availability()

        assert result is False

"""Tests for ModelFineTuner._tokenize_if_needed.

Covers the format-mismatch gap: TrainingDataBuilder's HuggingFace export
writes raw instruction/input/output columns, but Trainer + DataCollatorFor-
LanguageModeling require pre-tokenized input_ids. fine_tune_model() must
tokenize on load when the dataset isn't already tokenized, and leave an
already-tokenized dataset untouched.
"""

from __future__ import annotations

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

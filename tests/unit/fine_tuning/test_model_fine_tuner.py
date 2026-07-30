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

from evoseal.fine_tuning.model_fine_tuner import (
    ModelFineTuner,
    _is_valid_example,
    _validate_training_examples,
)


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

    def test_raises_on_all_invalid_examples(self, fine_tuner):
        ds = Dataset.from_list(
            [
                {"instruction": "", "output": "o"},
                {"instruction": "i", "output": ""},
                {"not_instruction": "x", "not_output": "y"},
            ]
        )

        with pytest.raises(ValueError, match="no valid training examples"):
            fine_tuner._tokenize_if_needed(ds, max_length=512)

    def test_filters_mixed_valid_and_invalid(self, fine_tuner):
        ds = Dataset.from_list(
            [
                {"instruction": "good", "input": "", "output": "result"},
                {"instruction": "", "output": "bad"},
                {"instruction": "also good", "input": "", "output": "out"},
            ]
        )

        result = fine_tuner._tokenize_if_needed(ds, max_length=512)

        assert "input_ids" in result.column_names
        assert len(result) == 2
        fine_tuner.tokenizer.assert_called_once()

    @pytest.mark.parametrize("bad_input", [[1, 2], 42])
    def test_filters_non_string_input(self, fine_tuner, bad_input):
        """Examples with non-string input (e.g. list, int) must be rejected."""
        # Each type needs its own Dataset because HF/Arrow can't mix column types.
        ds = Dataset.from_list([{"instruction": "ok", "input": bad_input, "output": "out"}])

        with pytest.raises(ValueError, match="no valid training examples"):
            fine_tuner._tokenize_if_needed(ds, max_length=512)

    def test_accepts_string_input(self, fine_tuner):
        """Valid string input (including empty string) should be accepted."""
        ds = Dataset.from_list(
            [
                {"instruction": "a", "input": "", "output": "b"},
                {"instruction": "c", "input": "context", "output": "d"},
            ]
        )

        result = fine_tuner._tokenize_if_needed(ds, max_length=512)
        assert len(result) == 2

    def test_accepts_mixed_input_presence(self, fine_tuner):
        """Rows where Arrow backfills missing ``input`` with None must survive."""
        ds = Dataset.from_list(
            [
                {"instruction": "a", "input": "ctx", "output": "b"},
                {"instruction": "c", "output": "d"},  # no input key
            ]
        )
        # Arrow schema unification: row 1's "input" is now None
        assert ds[1]["input"] is None

        result = fine_tuner._tokenize_if_needed(ds, max_length=512)
        assert len(result) == 2


class TestIsValidExample:
    """Tests for the shared _is_valid_example predicate."""

    def test_valid_with_input(self):
        assert _is_valid_example({"instruction": "i", "input": "ctx", "output": "o"})

    def test_valid_without_input(self):
        assert _is_valid_example({"instruction": "i", "output": "o"})

    def test_valid_empty_string_input(self):
        assert _is_valid_example({"instruction": "i", "input": "", "output": "o"})

    def test_normalizes_none_input(self):
        """None input (Arrow backfill for missing keys) should be accepted."""
        assert _is_valid_example({"instruction": "i", "input": None, "output": "o"})

    def test_invalid_list_input(self):
        assert not _is_valid_example({"instruction": "i", "input": [1], "output": "o"})

    def test_invalid_int_input(self):
        assert not _is_valid_example({"instruction": "i", "input": 42, "output": "o"})

    def test_invalid_missing_instruction(self):
        assert not _is_valid_example({"output": "o"})

    def test_invalid_empty_instruction(self):
        assert not _is_valid_example({"instruction": "  ", "output": "o"})

    def test_invalid_not_a_dict(self):
        assert not _is_valid_example("not a dict")


class TestValidateTrainingExamples:
    """Tests for _validate_training_examples with input validation."""

    def test_accepts_none_input(self):
        """None input (Arrow backfill for missing keys) should be accepted."""
        examples = [{"instruction": "i", "input": None, "output": "o"}]
        assert len(_validate_training_examples(examples)) == 1

    def test_accepts_empty_string_input(self):
        examples = [{"instruction": "i", "input": "", "output": "o"}]
        assert len(_validate_training_examples(examples)) == 1

    def test_rejects_non_string_input(self):
        examples = [{"instruction": "i", "input": 123, "output": "o"}]
        assert _validate_training_examples(examples) == []

    def test_mixed_valid_and_invalid_input(self):
        examples = [
            {"instruction": "a", "input": "valid", "output": "b"},
            {"instruction": "c", "input": None, "output": "d"},
            {"instruction": "e", "output": "f"},  # no input key — valid
        ]
        valid = _validate_training_examples(examples)
        assert len(valid) == 3

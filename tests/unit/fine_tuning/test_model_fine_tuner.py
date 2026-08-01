"""Tests for ModelFineTuner.

Covers the format-mismatch gap (tokenization) and security defaults
(trust_remote_code must be False to prevent arbitrary code execution
from untrusted model repos).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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
            patch.object(ModelFineTuner, "_check_gpu_availability", return_value=True),
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

    @pytest.mark.asyncio
    async def test_initialize_returns_false_when_model_needs_trust_remote_code(
        self, tmp_path, caplog
    ):
        """When a model requires trust_remote_code=True but gets False, initialize_model
        catches the resulting exception, logs it, and returns False.

        This exercises the failure path that the reviewer flagged: a model that
        used to load with trust_remote_code=True now hard-fails because custom
        code execution is blocked.
        """
        import logging

        import evoseal.fine_tuning.model_fine_tuner as mod

        tuner = ModelFineTuner.__new__(ModelFineTuner)
        tuner.model_name = "custom-model"
        tuner.base_model_path = "some-org/custom-model-needs-trust"
        tuner.output_dir = tmp_path
        tuner.use_lora = True
        tuner.use_qlora = False
        tuner.tokenizer = None
        tuner.model = None
        tuner.peft_model = None
        tuner.is_initialized = False
        tuner.current_training = None

        mock_tok_cls = MagicMock()
        # Simulate the failure: a model that ships custom code raises when
        # trust_remote_code=False.  OSError is what transformers actually raises
        # when the auto-map can't resolve the architecture without custom code.
        mock_tok_cls.from_pretrained.side_effect = OSError(
            "does not appear to have a file named configuration_auto.py. "
            "Checkout 'https://huggingface.co/some-org/custom-model-needs-trust'"
        )
        mock_mdl_cls = MagicMock()

        with (
            patch.object(mod, "TRANSFORMERS_AVAILABLE", True),
            patch.object(ModelFineTuner, "_check_gpu_availability", return_value=True),
            patch.object(mod, "AutoTokenizer", mock_tok_cls, create=True),
            patch.object(mod, "AutoModelForCausalLM", mock_mdl_cls, create=True),
            caplog.at_level(logging.ERROR, logger=mod.logger.name),
        ):
            result = await tuner.initialize_model()

        # Must surface the failure, not silently succeed
        assert result is False
        assert tuner.is_initialized is False

        # Model load should never have been attempted (tokenizer failed first)
        mock_mdl_cls.from_pretrained.assert_not_called()

        # Error must be logged so operators can diagnose the root cause
        assert "Error initializing model" in caplog.text


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

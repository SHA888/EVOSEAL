"""Tests for ModelValidator — verifies model_path is forwarded to the provider."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from evoseal.fine_tuning.model_validator import ModelValidator


@pytest.fixture()
def validator():
    return ModelValidator(baseline_model="baseline:latest", min_quality_threshold=0.5)


def _make_provider_mock(model: str) -> AsyncMock:
    """Return a mock OllamaProvider whose submit_prompt always succeeds."""
    mock = AsyncMock()
    mock.model = model
    mock.submit_prompt = AsyncMock(
        return_value="def factorial(n): return 1 if n < 2 else n * factorial(n-1)"
    )
    return mock


class TestResolveModelForValidation:
    """Unit tests for the _resolve_model_for_validation helper."""

    def test_returns_model_path_when_provided(self, validator):
        assert validator._resolve_model_for_validation("custom:7b") == "custom:7b"

    def test_returns_baseline_when_none(self, validator):
        assert validator._resolve_model_for_validation(None) == "baseline:latest"

    def test_raises_on_empty_string(self, validator):
        # Empty string is not the same as None — it's likely an upstream bug.
        with pytest.raises(ValueError, match="empty string"):
            validator._resolve_model_for_validation("")


@pytest.mark.asyncio()
async def test_validate_model_uses_model_path(validator):
    """When model_path is given, every test suite must use it — not the baseline."""
    captured_models: list[str] = []

    def _capture(model: str, **kwargs):
        captured_models.append(model)
        return _make_provider_mock(model)

    with patch("evoseal.fine_tuning.model_validator.OllamaProvider", side_effect=_capture):
        results = await validator.validate_model(model_path="finetuned:v1")

    # All 5 test suites should have used the fine-tuned model.
    assert len(captured_models) == 5
    assert all(m == "finetuned:v1" for m in captured_models), (
        f"Expected all calls with 'finetuned:v1', got {captured_models}"
    )
    assert results["model_path"] == "finetuned:v1"


@pytest.mark.asyncio()
async def test_validate_model_uses_baseline_when_no_path(validator):
    """When model_path is None, all test suites fall back to baseline."""
    captured_models: list[str] = []

    def _capture(model: str, **kwargs):
        captured_models.append(model)
        return _make_provider_mock(model)

    with patch("evoseal.fine_tuning.model_validator.OllamaProvider", side_effect=_capture):
        results = await validator.validate_model(model_path=None)

    assert len(captured_models) == 5
    assert all(m == "baseline:latest" for m in captured_models)
    assert results["model_path"] is None


@pytest.mark.asyncio()
async def test_validate_model_directory_path_is_forwarded(validator):
    """A filesystem directory path is forwarded as-is (Ollama will error — that's item 4's job)."""
    dir_path = "/tmp/models/versions/v1/model"
    captured_models: list[str] = []

    def _capture(model: str, **kwargs):
        captured_models.append(model)
        # Simulate Ollama failing on a non-existent model tag.
        mock = _make_provider_mock(model)
        mock.submit_prompt = AsyncMock(side_effect=Exception("model not found"))
        return mock

    with patch("evoseal.fine_tuning.model_validator.OllamaProvider", side_effect=_capture):
        results = await validator.validate_model(model_path=dir_path)

    # The directory path should still be forwarded (not silently replaced).
    assert all(m == dir_path for m in captured_models)
    # Validation should not pass — the dir path isn't a real Ollama model.
    assert results["passed"] is False
    # The safety suite defaults to 1.0 on error and performance gets 0.5
    # (0s avg time → time_score=1.0, 0 quality → 0.0).  Other suites give 0.0.
    # The important thing is the dir_path was forwarded, not the exact score.

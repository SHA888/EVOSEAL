"""Tests for TrainingDataBuilder.save_training_data huggingface format."""

from __future__ import annotations

from pathlib import Path

import pytest

datasets = pytest.importorskip(
    "datasets", reason="'datasets' package required for huggingface format tests"
)
Dataset = datasets.Dataset
load_from_disk = datasets.load_from_disk

from evoseal.evolution.models import TrainingExample
from evoseal.evolution.training_data_builder import TrainingDataBuilder


def _make_example(idx: int = 0) -> TrainingExample:
    return TrainingExample(
        instruction=f"Improve code {idx}",
        input_code=f"def f{idx}(x): return x",
        output_code=f"def f{idx}(x: int) -> int:\n    return x",
        context="unit test",
        quality_score=0.9,
        source_evolution_id=f"evo-{idx}",
    )


@pytest.fixture()
def populated_builder() -> TrainingDataBuilder:
    builder = TrainingDataBuilder()
    builder.training_examples = [_make_example(i) for i in range(10)]
    return builder


@pytest.mark.unit
def test_save_huggingface_creates_loadable_datasets(tmp_path, populated_builder):
    """The saved huggingface directories must be loadable via load_from_disk."""
    saved = populated_builder.save_training_data(tmp_path, format_type="huggingface")

    assert "train_hf" in saved
    assert "val_hf" in saved

    # Verify both splits load correctly
    train_ds = load_from_disk(str(saved["train_hf"]))
    val_ds = load_from_disk(str(saved["val_hf"]))

    assert isinstance(train_ds, Dataset)
    assert isinstance(val_ds, Dataset)
    assert len(train_ds) + len(val_ds) == 10


@pytest.mark.unit
def test_save_huggingface_has_alpaca_columns(tmp_path, populated_builder):
    """Loaded HF dataset should have instruction/input/output columns."""
    saved = populated_builder.save_training_data(tmp_path, format_type="huggingface")
    train_ds = load_from_disk(str(saved["train_hf"]))

    assert "instruction" in train_ds.column_names
    assert "input" in train_ds.column_names
    assert "output" in train_ds.column_names


@pytest.mark.unit
def test_save_huggingface_metadata(tmp_path, populated_builder):
    """Metadata file should record huggingface format type."""
    populated_builder.save_training_data(tmp_path, format_type="huggingface")

    import json

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["format_type"] == "huggingface"
    assert metadata["total_examples"] == 10


@pytest.mark.unit
def test_save_huggingface_single_example(tmp_path):
    """A single example (split_idx would be 0) must not crash or produce empty train."""
    builder = TrainingDataBuilder()
    builder.training_examples = [_make_example(0)]

    saved = builder.save_training_data(tmp_path, format_type="huggingface")

    # Train split must exist and be loadable
    assert "train_hf" in saved
    train_ds = load_from_disk(str(saved["train_hf"]))
    assert len(train_ds) == 1
    assert "instruction" in train_ds.column_names

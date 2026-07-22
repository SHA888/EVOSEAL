"""Regression tests for path traversal in checkpoint handling.

These tests verify that attacker-controlled identifiers (version_id,
checkpoint_name, file paths in changes dicts) cannot escape their
intended base directory via directory traversal sequences.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.checkpoint_manager import CheckpointManager, _validate_path_within_base
from evoseal.core.version_tracker import VersionTracker, _validate_checkpoint_id

# ---------------------------------------------------------------------------
# _validate_path_within_base helper
# ---------------------------------------------------------------------------


class TestValidatePathWithinBase:
    """Tests for the _validate_path_within_base helper."""

    def test_accepts_simple_name(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        base.mkdir()
        result = _validate_path_within_base(base, "simple_name", "test")
        assert result == (base / "simple_name").resolve()

    def test_rejects_dotdot(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(ValueError, match="would escape base directory"):
            _validate_path_within_base(base, "../etc/passwd", "test")

    def test_rejects_absolute_path(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(ValueError, match="would escape base directory"):
            _validate_path_within_base(base, "/etc/passwd", "test")

    def test_rejects_nested_dotdot(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        base.mkdir()
        with pytest.raises(ValueError, match="would escape base directory"):
            _validate_path_within_base(base, "sub/../../escape", "test")

    def test_accepts_subdirectory(self, tmp_path: Path) -> None:
        base = tmp_path / "base"
        base.mkdir()
        result = _validate_path_within_base(base, "sub/dir/file", "test")
        assert result == (base / "sub/dir/file").resolve()


# ---------------------------------------------------------------------------
# CheckpointManager — version_id traversal
# ---------------------------------------------------------------------------


class TestCheckpointManagerPathTraversal:
    """Verify CheckpointManager rejects path-traversal in version_id and file paths."""

    def _make_manager(self, tmp_path: Path) -> CheckpointManager:
        return CheckpointManager({"checkpoint_directory": str(tmp_path / "checkpoints")})

    # --- create_checkpoint ---

    def test_create_checkpoint_rejects_dotdot_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.create_checkpoint("../../etc/cron.d/evil", {"changes": {}})

    def test_create_checkpoint_rejects_absolute_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.create_checkpoint("/etc/passwd", {"changes": {}})

    def test_create_checkpoint_rejects_escaped_changes_path(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.create_checkpoint(
                "valid_id",
                {"changes": {"../../etc/cron.d/evil": "payload"}},
            )

    def test_create_checkpoint_accepts_valid_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        path = mgr.create_checkpoint("v1.0.0", {"changes": {"safe/file.py": "x = 1"}})
        assert Path(path).exists()

    # --- restore_checkpoint ---

    def test_restore_checkpoint_rejects_dotdot_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.restore_checkpoint("../../etc/passwd", tmp_path / "target")

    def test_restore_checkpoint_rejects_absolute_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.restore_checkpoint("/etc/passwd", tmp_path / "target")

    # --- get_checkpoint_path ---

    def test_get_checkpoint_path_rejects_dotdot_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.get_checkpoint_path("../../etc/passwd")

    def test_get_checkpoint_path_rejects_absolute_version_id(self, tmp_path: Path) -> None:
        mgr = self._make_manager(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            mgr.get_checkpoint_path("/etc/passwd")


# ---------------------------------------------------------------------------
# VersionTracker — checkpoint_name traversal
# ---------------------------------------------------------------------------


class TestVersionTrackerPathTraversal:
    """Verify VersionTracker rejects path-traversal in checkpoint_name."""

    def _make_tracker(self, tmp_path: Path) -> VersionTracker:
        """Create a VersionTracker with a mock experiment database."""
        tracker = VersionTracker(work_dir=tmp_path / "work")
        # Mock the experiment database so we don't need a real experiment
        tracker.experiment_db = MagicMock()
        mock_experiment = MagicMock()
        mock_experiment.to_json.return_value = "{}"
        mock_experiment.status.value = "completed"
        mock_experiment.git_commit = "abc123"
        mock_experiment.git_branch = "main"
        mock_experiment.artifacts = []
        tracker.experiment_db.get_experiment.return_value = mock_experiment
        return tracker

    def test_create_checkpoint_rejects_dotdot_name(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            tracker.create_checkpoint("exp1", checkpoint_name="../../escape")

    def test_create_checkpoint_rejects_absolute_name(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            tracker.create_checkpoint("exp1", checkpoint_name="/etc/passwd")

    def test_create_checkpoint_accepts_valid_name(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        cp_id = tracker.create_checkpoint("exp1", checkpoint_name="my_checkpoint")
        assert "my_checkpoint" in cp_id

    def test_restore_checkpoint_rejects_dotdot_id(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            tracker.restore_checkpoint("../../etc/passwd")

    def test_restore_checkpoint_rejects_absolute_id(self, tmp_path: Path) -> None:
        tracker = self._make_tracker(tmp_path)
        with pytest.raises(ValueError, match="would escape base directory"):
            tracker.restore_checkpoint("/etc/passwd")

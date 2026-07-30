"""Tests for checkpoint save and restore cycle.

Verifies that saving a checkpoint and restoring it produces consistent
state — covering the round-trip through create → restore → verify.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from evoseal.core.checkpoint_manager import CheckpointError, CheckpointManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def checkpoint_dir(tmp_path: Path) -> Path:
    return tmp_path / "checkpoints"


@pytest.fixture
def target_dir(tmp_path: Path) -> Path:
    return tmp_path / "restore_target"


@pytest.fixture
def manager(checkpoint_dir: Path) -> CheckpointManager:
    return CheckpointManager(config={"checkpoint_directory": str(checkpoint_dir)})


def _sample_version(version_id: str = "v1") -> dict:
    """Return a minimal but valid version dict for checkpoint creation."""
    return {
        "id": version_id,
        "name": f"version-{version_id}",
        "description": "test version",
        "changes": {
            "src/main.py": "print('hello')\n",
            "src/utils.py": "def helper():\n    return 42\n",
        },
        "config": {"learning_rate": 0.001, "epochs": 3},
        "metrics": [{"name": "fitness", "value": 0.85, "timestamp": "2026-01-01T00:00:00Z"}],
        "result": {"best_fitness": 0.85, "generations_completed": 5},
        "timestamp": "2026-01-01T00:00:00Z",
    }


# ---------------------------------------------------------------------------
# Basic round-trip
# ---------------------------------------------------------------------------


class TestCheckpointSaveRestore:
    """Core save/restore round-trip tests."""

    def test_create_and_restore_basic(self, manager: CheckpointManager, target_dir: Path) -> None:
        """Saving then restoring a checkpoint reproduces all files."""
        version = _sample_version("v1")
        cp_path = manager.create_checkpoint("v1", version, capture_system_state=False)

        assert Path(cp_path).exists()

        result = manager.restore_checkpoint("v1", target_dir, verify_integrity=True)

        assert result["success"] is True
        assert result["version_id"] == "v1"
        assert (target_dir / "src" / "main.py").read_text() == "print('hello')\n"
        assert (target_dir / "src" / "utils.py").read_text() == "def helper():\n    return 42\n"

    def test_metadata_preserved_after_restore(
        self, manager: CheckpointManager, target_dir: Path
    ) -> None:
        """Metadata (config, metrics, result) survives the round-trip."""
        version = _sample_version("v2")
        manager.create_checkpoint("v2", version, capture_system_state=False)

        result = manager.restore_checkpoint("v2", target_dir, verify_integrity=True)
        metadata = result["metadata"]

        assert metadata["version_id"] == "v2"
        assert metadata["config_snapshot"]["learning_rate"] == 0.001
        assert metadata["metrics_count"] == 1
        assert metadata["has_results"] is True

    def test_integrity_hash_matches_after_save(self, manager: CheckpointManager) -> None:
        """Integrity verification passes immediately after creation."""
        version = _sample_version("v3")
        manager.create_checkpoint("v3", version, capture_system_state=False)

        assert manager.verify_checkpoint_integrity("v3") is True

    def test_integrity_hash_fails_when_file_tampered(self, manager: CheckpointManager) -> None:
        """Integrity verification fails when a file is modified after checkpoint."""
        version = _sample_version("v4")
        manager.create_checkpoint("v4", version, capture_system_state=False)

        # Tamper with a file inside the checkpoint
        cp_path = Path(manager.get_checkpoint_path("v4"))
        tampered = cp_path / "src" / "main.py"
        tampered.write_text("EVIL CODE\n")

        assert manager.verify_checkpoint_integrity("v4") is False

    def test_restore_nonexistent_raises(self, manager: CheckpointManager, target_dir: Path) -> None:
        """Restoring a version that was never checkpointed raises CheckpointError."""
        with pytest.raises(CheckpointError):
            manager.restore_checkpoint("does_not_exist", target_dir)

    def test_multiple_checkpoints_restore_correct_one(
        self, manager: CheckpointManager, tmp_path: Path
    ) -> None:
        """With multiple checkpoints, each restores its own data."""
        manager.create_checkpoint("a", _sample_version("a"), capture_system_state=False)
        manager.create_checkpoint(
            "b",
            {
                **_sample_version("b"),
                "changes": {"file_b.txt": "content-b\n"},
            },
            capture_system_state=False,
        )

        target_a = tmp_path / "target_a"
        target_b = tmp_path / "target_b"
        manager.restore_checkpoint("a", target_a, verify_integrity=False)
        manager.restore_checkpoint("b", target_b, verify_integrity=False)

        assert (target_a / "src" / "main.py").exists()
        assert not (target_a / "file_b.txt").exists()
        assert (target_b / "file_b.txt").read_text() == "content-b\n"

    def test_list_checkpoints_after_create(self, manager: CheckpointManager) -> None:
        """list_checkpoints returns metadata for all created checkpoints."""
        for vid in ("x", "y"):
            manager.create_checkpoint(vid, _sample_version(vid), capture_system_state=False)

        listed = manager.list_checkpoints()
        ids = {cp["version_id"] for cp in listed}
        assert ids == {"x", "y"}

    def test_delete_checkpoint(self, manager: CheckpointManager) -> None:
        """Deleting a checkpoint removes it from disk and registry."""
        checkpoint_path = Path(
            manager.create_checkpoint("del", _sample_version("del"), capture_system_state=False)
        )
        assert manager.delete_checkpoint("del") is True
        assert manager.get_checkpoint_path("del") is None
        assert not checkpoint_path.exists()

    def test_restore_clears_target_except_protected(
        self, manager: CheckpointManager, target_dir: Path
    ) -> None:
        """Restore clears the target directory but leaves .git/ alone."""
        target_dir.mkdir(parents=True)
        (target_dir / "stale.txt").write_text("old\n")
        git_dir = target_dir / ".git"
        git_dir.mkdir()
        (git_dir / "HEAD").write_text("ref: refs/heads/main\n")

        manager.create_checkpoint("c", _sample_version("c"), capture_system_state=False)
        result = manager.restore_checkpoint("c", target_dir, verify_integrity=False)

        assert result["success"] is True
        assert not (target_dir / "stale.txt").exists()
        assert (target_dir / ".git" / "HEAD").exists()

    def test_checkpoint_size_reported(self, manager: CheckpointManager) -> None:
        """get_checkpoint_size returns a positive number for a saved checkpoint."""
        manager.create_checkpoint("sz", _sample_version("sz"), capture_system_state=False)
        size = manager.get_checkpoint_size("sz")
        assert size is not None
        assert size > 0

    def test_restore_with_system_state(self, manager: CheckpointManager, target_dir: Path) -> None:
        """Restoring with capture_system_state=True returns system_state in result."""
        manager.create_checkpoint("ss", _sample_version("ss"), capture_system_state=True)
        result = manager.restore_checkpoint("ss", target_dir, verify_integrity=True)

        assert result["system_state"] is not None
        assert "system_info" in result["system_state"]
        assert "capture_timestamp" in result["system_state"]

    def test_interrupt_and_restore_consistency(
        self, manager: CheckpointManager, target_dir: Path
    ) -> None:
        """Simulate mid-evolution interruption: checkpoint, mutate, restore."""
        original = _sample_version("interrupt")
        manager.create_checkpoint("interrupt", original, capture_system_state=False)

        # Simulate a partial evolution that corrupts the workspace
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "src" / "main.py").parent.mkdir(parents=True, exist_ok=True)
        (target_dir / "src" / "main.py").write_text("BROKEN PARTIAL EDIT\n")
        (target_dir / "junk.txt").write_text("should be removed on restore\n")

        # Restore — should recover original state
        result = manager.restore_checkpoint("interrupt", target_dir, verify_integrity=True)
        assert result["success"] is True
        assert (target_dir / "src" / "main.py").read_text() == "print('hello')\n"
        assert not (target_dir / "junk.txt").exists()

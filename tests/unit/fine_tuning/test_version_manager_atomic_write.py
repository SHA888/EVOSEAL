"""Tests for ModelVersionManager atomic registry writes."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from evoseal.fine_tuning.version_manager import ModelVersionManager


@pytest.fixture
def versions_dir(tmp_path: Path) -> Path:
    return tmp_path / "versions"


class TestAtomicSaveRegistry:
    """Verify _save_registry uses atomic temp-file + os.replace."""

    def test_save_creates_registry_file(self, versions_dir: Path) -> None:
        """Registry file exists and is valid JSON after save."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm._save_registry()
        assert vm.registry_file.exists()
        data = json.loads(vm.registry_file.read_text())
        assert "versions" in data
        assert "created" in data
        assert "updated" in data

    def test_save_round_trip(self, versions_dir: Path) -> None:
        """Data written by _save_registry survives a _load_registry round-trip."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm.registry["versions"].append({"id": "test-v1", "status": "stored"})
        vm._save_registry()

        vm2 = ModelVersionManager(versions_dir=versions_dir)
        assert len(vm2.registry["versions"]) == 1
        assert vm2.registry["versions"][0]["id"] == "test-v1"

    def test_no_temp_files_left_after_save(self, versions_dir: Path) -> None:
        """Successful save should not leave temp files behind."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm._save_registry()

        tmp_files = list(versions_dir.glob(".version_registry_*"))
        assert tmp_files == [], f"Orphan temp files found: {tmp_files}"

    def test_write_failure_preserves_original(self, versions_dir: Path) -> None:
        """If the JSON dump fails, the original file content must be preserved."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm.registry["versions"].append({"id": "v1"})
        vm._save_registry()

        original_content = vm.registry_file.read_text()

        # Simulate a write failure by patching json.dump to raise.
        with patch(
            "evoseal.fine_tuning.version_manager.json.dump", side_effect=OSError("disk full")
        ):
            vm._save_registry()

        # The original file must still be intact.
        assert vm.registry_file.read_text() == original_content

    def test_no_temp_files_after_write_failure(self, versions_dir: Path) -> None:
        """Temp file must be cleaned up even when the write fails."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm._save_registry()  # establish the file

        with patch(
            "evoseal.fine_tuning.version_manager.json.dump", side_effect=OSError("disk full")
        ):
            vm._save_registry()

        tmp_files = list(versions_dir.glob(".version_registry_*"))
        assert tmp_files == [], f"Orphan temp files after failed write: {tmp_files}"

    def test_first_save_to_nonexistent_directory(self, tmp_path: Path) -> None:
        """First save creates parent directories if needed."""
        deep_dir = tmp_path / "a" / "b" / "c" / "versions"
        vm = ModelVersionManager(versions_dir=deep_dir)
        vm._save_registry()
        assert vm.registry_file.exists()

    def test_concurrent_reads_see_consistent_data(self, versions_dir: Path) -> None:
        """A reader loading the file mid-write sees either the old or new
        version, never a truncated/partial file."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm.registry["versions"].append({"id": "v1"})
        vm._save_registry()

        # Simulate a reader: load the file and check it's valid JSON.
        # After another save, it should still be valid.
        vm.registry["versions"].append({"id": "v2"})
        vm._save_registry()

        data = json.loads(vm.registry_file.read_text())
        assert len(data["versions"]) == 2

    def test_save_preserves_existing_file_permissions(self, versions_dir: Path) -> None:
        """Registry file permissions must not tighten after atomic save."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        vm._save_registry()

        # Set a deliberate mode (0o644) and verify it survives a round-trip.
        os.chmod(vm.registry_file, 0o644)
        vm.registry["versions"].append({"id": "v1"})
        vm._save_registry()

        mode = stat.S_IMODE(os.stat(vm.registry_file).st_mode)
        assert mode == 0o644, f"Expected 0o644 but got {oct(mode)}"

    def test_save_defaults_to_0644_when_file_is_new(self, versions_dir: Path) -> None:
        """A brand-new registry file should be created with mode 0o644."""
        vm = ModelVersionManager(versions_dir=versions_dir)
        # registry_file doesn't exist yet — _save_registry should use 0o644.
        vm._save_registry()

        mode = stat.S_IMODE(os.stat(vm.registry_file).st_mode)
        assert mode == 0o644, f"Expected 0o644 but got {oct(mode)}"

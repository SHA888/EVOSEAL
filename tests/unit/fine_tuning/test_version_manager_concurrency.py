"""Tests for asyncio.Lock-based concurrency protection in ModelVersionManager."""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from evoseal.fine_tuning.version_manager import ModelVersionManager


@pytest.fixture
def versions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "versions"
    d.mkdir()
    return d


def _make_training_results(idx: int) -> dict:
    return {
        "model_name": f"test-model-{idx}",
        "train_loss": 0.5 - idx * 0.01,
        "training_examples_count": 100 + idx,
    }


class TestConcurrentLocking:
    """Verify that concurrent async calls do not corrupt the registry."""

    @pytest.mark.asyncio
    async def test_concurrent_register_versions_all_persisted(self, versions_dir: Path) -> None:
        """Multiple concurrent register_version calls must all appear in the registry."""
        mgr = ModelVersionManager(versions_dir=versions_dir)

        # Patch deploy to avoid calling ollama
        with patch.object(mgr, "_deploy_to_ollama", return_value=None):
            tasks = [mgr.register_version(_make_training_results(i)) for i in range(5)]
            results = await asyncio.gather(*tasks)

        # All 5 should succeed
        assert all("error" not in r for r in results)
        assert len(mgr.registry["versions"]) == 5

        # Reload from disk and verify persistence
        mgr2 = ModelVersionManager(versions_dir=versions_dir)
        assert len(mgr2.registry["versions"]) == 5

    @pytest.mark.asyncio
    async def test_concurrent_register_and_deploy_no_corruption(self, versions_dir: Path) -> None:
        """Interleaved register + deploy must not lose updates or produce inconsistent state."""
        mgr = ModelVersionManager(versions_dir=versions_dir)

        # First register a version so deploy_version has something to work with
        with patch.object(mgr, "_deploy_to_ollama", return_value=None):
            first = await mgr.register_version(_make_training_results(0))
        first_id = first["version_id"]

        # Now register more versions concurrently with deploying the first.
        # Deploy will fail (no model_path) — that's fine; the test verifies
        # the registry stays consistent, not that deploy succeeds.
        with patch.object(mgr, "_deploy_to_ollama", return_value=None):
            tasks = [
                mgr.deploy_version(first_id),
                *[mgr.register_version(_make_training_results(i + 1)) for i in range(4)],
            ]
            results = await asyncio.gather(*tasks)

        # Total versions: 1 (first) + 4 (concurrent) = 5
        assert len(mgr.registry["versions"]) == 5
        # deploy_version returned an error (no model files) — that's expected
        assert "error" in results[0]
        # All 4 register calls should succeed
        assert all("error" not in r for r in results[1:])

    @pytest.mark.asyncio
    async def test_lock_is_per_instance(self, versions_dir: Path) -> None:
        """Two different ModelVersionManager instances have independent locks."""
        dir_a = versions_dir / "a"
        dir_b = versions_dir / "b"
        dir_a.mkdir()
        dir_b.mkdir()

        mgr_a = ModelVersionManager(versions_dir=dir_a)
        mgr_b = ModelVersionManager(versions_dir=dir_b)

        # They should be able to run concurrently (different locks)
        with (
            patch.object(mgr_a, "_deploy_to_ollama", return_value=None),
            patch.object(mgr_b, "_deploy_to_ollama", return_value=None),
        ):
            results = await asyncio.gather(
                mgr_a.register_version(_make_training_results(0)),
                mgr_b.register_version(_make_training_results(1)),
            )

        assert all("error" not in r for r in results)
        assert len(mgr_a.registry["versions"]) == 1
        assert len(mgr_b.registry["versions"]) == 1

    @pytest.mark.asyncio
    async def test_register_then_deploy_serialised(self, versions_dir: Path) -> None:
        """register_version with deploy=True calls deploy under the same lock
        without deadlocking (the impl pattern avoids reentrant lock)."""
        mgr = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(mgr, "_deploy_to_ollama", return_value=None):
            result = await mgr.register_version(_make_training_results(0), deploy=True)

        assert "error" not in result
        assert len(mgr.registry["versions"]) == 1
        # Should have been deployed (or at least attempted)
        assert result.get("deployment_status") in ("deployed", "failed", "current")

    @pytest.mark.asyncio
    async def test_deploy_nonexistent_version_while_registering(self, versions_dir: Path) -> None:
        """A failed deploy (version not found) alongside a register must not corrupt state."""
        mgr = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(mgr, "_deploy_to_ollama", return_value=None):
            tasks = [
                mgr.deploy_version("nonexistent-id"),
                mgr.register_version(_make_training_results(0)),
            ]
            results = await asyncio.gather(*tasks)

        # deploy should fail, register should succeed
        assert "error" in results[0]
        assert "error" not in results[1]
        assert len(mgr.registry["versions"]) == 1

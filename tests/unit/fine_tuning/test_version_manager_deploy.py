"""Tests for ModelVersionManager deployment functionality."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from evoseal.fine_tuning.version_manager import ModelVersionManager


@pytest.fixture
def versions_dir(tmp_path: Path) -> Path:
    return tmp_path / "versions"


@pytest.fixture
def model_dir(tmp_path: Path) -> Path:
    """Create a fake model directory with safetensors-style files."""
    d = tmp_path / "trained_model"
    d.mkdir()
    (d / "config.json").write_text('{"model_type": "test"}')
    (d / "model.safetensors").write_text("fake-weights")
    return d


@pytest.fixture
def gguf_model_dir(tmp_path: Path) -> Path:
    """Create a fake model directory with a GGUF file."""
    d = tmp_path / "gguf_model"
    d.mkdir()
    (d / "model-q4_K_M.gguf").write_text("fake-gguf")
    return d


class TestCreateModelfile:
    """Tests for _create_modelfile static method."""

    def test_gguf_file_detected(self, gguf_model_dir: Path) -> None:
        content = ModelVersionManager._create_modelfile(str(gguf_model_dir))
        assert "FROM" in content
        assert "model-q4_K_M.gguf" in content

    def test_huggingface_directory_fallback(self, model_dir: Path) -> None:
        content = ModelVersionManager._create_modelfile(str(model_dir))
        assert "FROM" in content
        assert str(model_dir) in content

    def test_empty_directory_falls_back_to_dir(self, tmp_path: Path) -> None:
        empty = tmp_path / "empty_model"
        empty.mkdir()
        content = ModelVersionManager._create_modelfile(str(empty))
        assert "FROM" in content
        assert str(empty) in content


class TestDeployToOllama:
    """Tests for _deploy_to_ollama static method."""

    def test_success(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = ModelVersionManager._deploy_to_ollama(
                "test-model", modelfile, "http://localhost:11434"
            )
        assert result is None

    def test_ollama_not_found(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = ModelVersionManager._deploy_to_ollama(
                "test-model", modelfile, "http://localhost:11434"
            )
        assert "not found" in result

    def test_nonzero_exit(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "model not found"
            result = ModelVersionManager._deploy_to_ollama(
                "test-model", modelfile, "http://localhost:11434"
            )
        assert "model not found" in result


class TestDeployVersion:
    """Tests for the deploy_version method."""

    @pytest.mark.asyncio
    async def test_version_not_found(self, versions_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        result = await vm.deploy_version("nonexistent")
        assert "error" in result
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_no_model_path(self, versions_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        # Register a version without model files
        reg = await vm.register_version(
            training_results={"success": True, "fallback_mode": True},
            validation_results={"passed": True},
        )
        vid = reg["version_id"]
        # Clear model_path to simulate missing files
        version_info = vm.get_version_info(vid)
        version_info.pop("model_path", None)
        vm._save_registry()

        result = await vm.deploy_version(vid)
        assert "error" in result
        assert "not found" in result["error"].lower() or "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_deploy_success(self, versions_dir: Path, model_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        reg = await vm.register_version(
            training_results={
                "success": True,
                "model_save_path": str(model_dir),
                "fallback_mode": True,
            },
            validation_results={"passed": True},
        )
        vid = reg["version_id"]

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            result = await vm.deploy_version(vid, ollama_model_name="test-deployed")

        assert "ollama_model" in result
        assert result["ollama_model"] == "test-deployed"

        # Verify registry updated
        vi = vm.get_version_info(vid)
        assert vi["deployment_status"] == "deployed"
        assert vi["ollama_model_name"] == "test-deployed"

    @pytest.mark.asyncio
    async def test_deploy_failure_updates_registry(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        reg = await vm.register_version(
            training_results={
                "success": True,
                "model_save_path": str(model_dir),
                "fallback_mode": True,
            },
            validation_results={"passed": True},
        )
        vid = reg["version_id"]

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value="some error"):
            result = await vm.deploy_version(vid)

        assert "error" in result
        vi = vm.get_version_info(vid)
        assert vi["deployment_status"] == "failed"
        assert vi["deployment_error"] == "some error"


class TestRegisterVersionWithDeploy:
    """Tests for register_version with the deploy flag."""

    @pytest.mark.asyncio
    async def test_register_with_deploy(self, versions_dir: Path, model_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            reg = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="auto-deployed",
            )

        assert reg["deployment_status"] == "deployed"
        assert reg["ollama_model_name"] == "auto-deployed"

    @pytest.mark.asyncio
    async def test_register_deploy_failure_still_registers(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value="deploy error"):
            reg = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
            )

        # Version should still be registered even if deploy fails
        assert "version_id" in reg
        assert reg.get("deployment_error") == "deploy error"

    @pytest.mark.asyncio
    async def test_register_without_deploy_no_deployment(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)

        reg = await vm.register_version(
            training_results={
                "success": True,
                "model_save_path": str(model_dir),
                "fallback_mode": True,
            },
            validation_results={"passed": True},
        )

        # Default: no deployment
        assert reg.get("deployment_status") != "deployed"


class TestDeploymentStats:
    """Test that deployment_distribution is included in statistics."""

    @pytest.mark.asyncio
    async def test_stats_include_deployment(self, versions_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        await vm.register_version(
            training_results={"success": True, "fallback_mode": True},
        )
        stats = vm.get_version_statistics()
        assert "deployment_distribution" in stats
        assert isinstance(stats["deployment_distribution"], dict)

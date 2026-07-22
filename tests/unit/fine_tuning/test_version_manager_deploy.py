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

    def test_multiple_gguf_picks_largest(self, tmp_path: Path) -> None:
        """When multiple GGUF files exist, the largest is selected."""
        d = tmp_path / "multi_gguf"
        d.mkdir()
        small = d / "model-Q4_K_M.gguf"
        small.write_bytes(b"x" * 100)
        large = d / "model-Q8_0.gguf"
        large.write_bytes(b"y" * 500)
        content = ModelVersionManager._create_modelfile(str(d))
        assert "model-Q8_0.gguf" in content

    def test_adapter_directory_detected(self, tmp_path: Path) -> None:
        """LoRA/PEFT adapter dirs produce FROM <base> + ADAPTER <path>."""
        import json

        d = tmp_path / "adapter_model"
        d.mkdir()
        (d / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "llama3:8b"}))
        content = ModelVersionManager._create_modelfile(str(d))
        assert "FROM llama3:8b" in content
        assert f"ADAPTER {d}" in content


class TestDeployToOllama:
    """Tests for _deploy_to_ollama static method."""

    def test_success(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            result = ModelVersionManager._deploy_to_ollama("test-model", modelfile)
        assert result is None

    def test_ollama_not_found(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = ModelVersionManager._deploy_to_ollama("test-model", modelfile)
        assert "not found" in result

    def test_nonzero_exit(self, tmp_path: Path) -> None:
        modelfile = tmp_path / "Modelfile"
        modelfile.write_text("FROM /some/model\n")
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stderr = "model not found"
            result = ModelVersionManager._deploy_to_ollama("test-model", modelfile)
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
        assert "not found" in result["error"].lower()

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
        assert reg["deployment_status"] == "failed"

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


class TestPathValidation:
    """Tests for _validate_model_path and path-safe Modelfile generation."""

    def test_path_with_spaces_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "my model"
        d.mkdir()
        (d / "model.gguf").write_bytes(b"x" * 10)
        with pytest.raises(ValueError, match="whitespace"):
            ModelVersionManager._create_modelfile(str(d))

    def test_gguf_path_with_spaces_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "ok_dir"
        d.mkdir()
        (d / "my model.gguf").write_bytes(b"x" * 10)
        with pytest.raises(ValueError, match="whitespace"):
            ModelVersionManager._create_modelfile(str(d))

    def test_clean_path_succeeds(self, tmp_path: Path) -> None:
        d = tmp_path / "clean_model"
        d.mkdir()
        (d / "model.gguf").write_bytes(b"x" * 10)
        content = ModelVersionManager._create_modelfile(str(d))
        assert "FROM" in content

    @pytest.mark.asyncio
    async def test_deploy_with_spaces_returns_error(
        self, versions_dir: Path, tmp_path: Path
    ) -> None:
        """deploy_version rejects model paths containing whitespace."""
        d = tmp_path / "ok_model"
        d.mkdir()
        (d / "config.json").write_text("{}")
        (d / "model.safetensors").write_text("fake")
        vm = ModelVersionManager(versions_dir=versions_dir)
        reg = await vm.register_version(
            training_results={
                "success": True,
                "model_save_path": str(d),
                "fallback_mode": True,
            },
            validation_results={"passed": True},
        )
        vid = reg["version_id"]
        # Overwrite the stored model_path with one containing spaces to
        # simulate a space-containing path reaching deploy_version.
        vi = vm.get_version_info(vid)
        spaced_dir = tmp_path / "my model"
        spaced_dir.mkdir()
        (spaced_dir / "config.json").write_text("{}")
        (spaced_dir / "model.safetensors").write_text("fake")
        vi["model_path"] = str(spaced_dir)
        vm._save_registry()

        result = await vm.deploy_version(vid)
        assert "error" in result
        assert "whitespace" in result["error"]


class TestModelNameSanitization:
    """Tests for Ollama model name sanitization in deploy_version."""

    @pytest.mark.asyncio
    async def test_uppercase_name_lowered(self, versions_dir: Path, model_dir: Path) -> None:
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
            result = await vm.deploy_version(vid, ollama_model_name="My-Model")
        assert result["ollama_model"] == "my-model"

    @pytest.mark.asyncio
    async def test_spaces_in_name_replaced(self, versions_dir: Path, model_dir: Path) -> None:
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
            result = await vm.deploy_version(vid, ollama_model_name="my model v1")
        assert result["ollama_model"] == "my-model-v1"
        assert " " not in result["ollama_model"]

    @pytest.mark.asyncio
    async def test_special_chars_replaced(self, versions_dir: Path, model_dir: Path) -> None:
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
            result = await vm.deploy_version(vid, ollama_model_name="model@v1#test")
        sanitized = result["ollama_model"]
        assert "@" not in sanitized
        assert "#" not in sanitized


class TestSupersedeAfterDeploy:
    """Regression: supersede marking must happen after successful deployment."""

    @pytest.mark.asyncio
    async def test_failed_deploy_does_not_supersede_old(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        """If ollama create fails, the previously-deployed version must not
        be marked superseded."""
        vm = ModelVersionManager(versions_dir=versions_dir)

        # Deploy v1 successfully under name "my-model".
        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            reg1 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v1_id = reg1["version_id"]
        v1_info = vm.get_version_info(v1_id)
        assert v1_info["deployment_status"] == "deployed"

        # Attempt v2 deploy under the same name, but ollama create fails.
        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value="boom"):
            reg2 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v2_id = reg2["version_id"]

        # v1 must still be "deployed", NOT "superseded".
        v1_info = vm.get_version_info(v1_id)
        assert v1_info["deployment_status"] == "deployed"
        # v2 should be "failed".
        v2_info = vm.get_version_info(v2_id)
        assert v2_info["deployment_status"] == "failed"

    @pytest.mark.asyncio
    async def test_successful_deploy_supersedes_old(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        """When a new version deploys successfully under the same name,
        the old version should be marked superseded."""
        vm = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            reg1 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v1_id = reg1["version_id"]

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            reg2 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v2_id = reg2["version_id"]

        v1_info = vm.get_version_info(v1_id)
        assert v1_info["deployment_status"] == "superseded"
        v2_info = vm.get_version_info(v2_id)
        assert v2_info["deployment_status"] == "deployed"

    @pytest.mark.asyncio
    async def test_modelfile_failure_does_not_supersede_old(
        self, versions_dir: Path, model_dir: Path
    ) -> None:
        """If _create_modelfile raises, the previously-deployed version must
        not be marked superseded."""
        vm = ModelVersionManager(versions_dir=versions_dir)

        with patch.object(ModelVersionManager, "_deploy_to_ollama", return_value=None):
            reg1 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v1_id = reg1["version_id"]

        # Make _create_modelfile fail for v2.
        with patch.object(
            ModelVersionManager,
            "_create_modelfile",
            side_effect=ValueError("bad path"),
        ):
            reg2 = await vm.register_version(
                training_results={
                    "success": True,
                    "model_save_path": str(model_dir),
                    "fallback_mode": True,
                },
                validation_results={"passed": True},
                deploy=True,
                ollama_model_name="my-model",
            )
        v2_id = reg2["version_id"]

        v1_info = vm.get_version_info(v1_id)
        assert v1_info["deployment_status"] == "deployed"
        v2_info = vm.get_version_info(v2_id)
        assert v2_info["deployment_status"] == "failed"


class TestAdapterBaseModelValidation:
    """Regression: base_model from adapter_config must be validated."""

    def test_adapter_base_model_with_spaces_raises(self, tmp_path: Path) -> None:
        d = tmp_path / "adapter_model"
        d.mkdir()
        (d / "adapter_config.json").write_text(
            json.dumps({"base_model_name_or_path": "my base model"})
        )
        with pytest.raises(ValueError, match="whitespace"):
            ModelVersionManager._create_modelfile(str(d))

    def test_adapter_base_model_without_spaces_succeeds(self, tmp_path: Path) -> None:
        d = tmp_path / "adapter_model"
        d.mkdir()
        (d / "adapter_config.json").write_text(json.dumps({"base_model_name_or_path": "llama3:8b"}))
        content = ModelVersionManager._create_modelfile(str(d))
        assert "FROM llama3:8b" in content
        assert f"ADAPTER {d}" in content


class TestNoModelPathPersistError:
    """Regression: deploy-requested-but-no-model_path must persist to registry."""

    @pytest.mark.asyncio
    async def test_error_persisted_to_disk(self, versions_dir: Path) -> None:
        vm = ModelVersionManager(versions_dir=versions_dir)
        reg = await vm.register_version(
            training_results={"success": True, "fallback_mode": True},
            deploy=True,
        )
        vid = reg["version_id"]

        # Re-load from disk to verify persistence.
        vm2 = ModelVersionManager(versions_dir=versions_dir)
        vi = vm2.get_version_info(vid)
        assert vi["deployment_error"] == "deploy requested but no model_path available"
        assert vi["deployment_status"] == "failed"


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

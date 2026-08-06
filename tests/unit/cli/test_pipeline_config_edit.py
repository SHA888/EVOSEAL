"""Tests for pipeline config --edit implementation."""

from __future__ import annotations

import json
import os
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import evoseal.cli.commands.pipeline as pipeline_mod
from evoseal.cli.commands.pipeline import PipelineConfig, app

runner = CliRunner()


@pytest.fixture(autouse=True)
def isolate_config(tmp_path):
    """Point the module-level pipeline_config and PIPELINE_CONFIG_FILE at a temp dir."""
    config_file = str(tmp_path / "pipeline_config.json")
    fake_cfg = PipelineConfig(config_file)
    with (
        patch.object(pipeline_mod, "pipeline_config", fake_cfg),
        patch.object(pipeline_mod, "PIPELINE_CONFIG_FILE", config_file),
    ):
        yield config_file


class TestConfigEdit:
    """Tests for the config --edit command."""

    def test_edit_no_editor_set(self, isolate_config):
        """When $EDITOR and $VISUAL are unset, command exits with error."""
        env = {"PATH": os.environ.get("PATH", "")}
        with patch.dict(os.environ, env, clear=True):
            result = runner.invoke(app, ["config", "--edit"])
            assert result.exit_code == 1
            assert "No editor found" in result.output

    def test_edit_creates_default_config_if_missing(self, isolate_config, tmp_path):
        """config --edit should create a default config file if none exists."""
        editor_script = str(tmp_path / "editor.sh")
        with open(editor_script, "w") as f:
            f.write("#!/bin/sh\n# no-op editor\n")
        os.chmod(editor_script, 0o755)

        with patch.dict(os.environ, {"EDITOR": editor_script}):
            result = runner.invoke(app, ["config", "--edit"])
            assert result.exit_code == 0, result.output
            assert os.path.exists(isolate_config)
            with open(isolate_config) as f:
                data = json.load(f)
            assert "iterations" in data

    def test_edit_rejects_invalid_json(self, isolate_config, tmp_path):
        """If the user saves invalid JSON, the command should revert."""
        cfg = pipeline_mod.pipeline_config
        original = {"iterations": 7, "custom": True}
        cfg.save_config(original)

        editor_script = str(tmp_path / "bad_editor.sh")
        with open(editor_script, "w") as f:
            f.write('#!/bin/sh\necho "not json" > "$1"\n')
        os.chmod(editor_script, 0o755)

        with patch.dict(os.environ, {"EDITOR": editor_script}):
            result = runner.invoke(app, ["config", "--edit"])
            assert "not valid JSON" in result.output

        # Verify the file was restored to the previous valid config
        with open(isolate_config) as f:
            restored = json.load(f)
        assert restored == original

    def test_edit_accepts_valid_json(self, isolate_config, tmp_path):
        """If the user saves valid JSON, the command should accept it."""
        cfg = pipeline_mod.pipeline_config
        cfg.save_config(cfg.get_default_config())

        editor_script = str(tmp_path / "good_editor.sh")
        with open(editor_script, "w") as f:
            f.write('#!/bin/sh\necho \'{"iterations": 42}\' > "$1"\n')
        os.chmod(editor_script, 0o755)

        with patch.dict(os.environ, {"EDITOR": editor_script}):
            result = runner.invoke(app, ["config", "--edit"])
            assert "updated successfully" in result.output

        with open(isolate_config) as f:
            data = json.load(f)
        assert data["iterations"] == 42

    def test_edit_bad_editor_binary(self, isolate_config):
        """If the editor binary doesn't exist, command exits with error."""
        cfg = pipeline_mod.pipeline_config
        cfg.save_config(cfg.get_default_config())

        with patch.dict(os.environ, {"EDITOR": "/nonexistent/binary"}):
            result = runner.invoke(app, ["config", "--edit"])
            assert result.exit_code == 1
            assert "not found" in result.output.lower()

    def test_edit_editor_with_arguments(self, isolate_config, tmp_path):
        """EDITOR values with arguments (e.g. 'code --wait') should work."""
        cfg = pipeline_mod.pipeline_config
        cfg.save_config(cfg.get_default_config())

        # A script that prints argv to prove arguments were split correctly
        editor_script = str(tmp_path / "editor_with_args.sh")
        with open(editor_script, "w") as f:
            f.write(
                "#!/bin/sh\n"
                "# Expect: <script> --some-flag <config-file>\n"
                'echo \'{"iterations": 99}\' > "$2"\n'
            )
        os.chmod(editor_script, 0o755)

        # Simulate EDITOR="script --some-flag"
        with patch.dict(os.environ, {"EDITOR": f"{editor_script} --some-flag"}):
            result = runner.invoke(app, ["config", "--edit"])
            assert result.exit_code == 0, result.output
            assert "updated successfully" in result.output

        with open(isolate_config) as f:
            data = json.load(f)
        assert data["iterations"] == 99

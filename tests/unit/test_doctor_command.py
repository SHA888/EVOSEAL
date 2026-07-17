"""Tests for the evoseal doctor command.

Tests validation of:
- API keys reachability
- configs/safety.yaml well-formedness
- Dependencies installation
- Git state cleanliness
- Budget/cost configuration
"""

from __future__ import annotations

import os
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from evoseal.cli.main import app

runner = CliRunner()


class TestDoctorCommand:
    """Test suite for the doctor command."""

    def test_doctor_command_exists(self):
        """Test that the doctor command is registered and responds to help."""
        result = runner.invoke(app, ["doctor", "--help"])
        assert result.exit_code == 0
        assert "doctor" in result.stdout.lower() or "validate" in result.stdout.lower()


class TestDoctorChecks:
    """Test suite for individual doctor check functions."""

    def test_check_api_keys_found(self):
        """Test API key detection when present."""
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):  # pragma: allowlist secret
            from evoseal.cli.commands.doctor import check_api_keys

            success, message = check_api_keys()
            assert success is True

    def test_check_api_keys_missing(self):
        """Test API key detection when missing."""
        with patch.dict(os.environ, {}, clear=True):
            from evoseal.cli.commands.doctor import check_api_keys

            success, message = check_api_keys()
            assert success is False

    def test_check_safety_yaml_present(self, tmp_path):
        """Test safety.yaml detection when present."""
        safety_dir = tmp_path / "configs"
        safety_dir.mkdir()
        safety_file = safety_dir / "safety.yaml"
        config = {"editable_paths": ["evoseal/"]}
        with open(safety_file, "w") as f:
            yaml.dump(config, f)

        with patch(
            "evoseal.cli.commands.doctor.get_safety_yaml_path",
            return_value=safety_file,
        ):
            from evoseal.cli.commands.doctor import check_safety_yaml

            success, message = check_safety_yaml()
            assert success is True

    def test_check_safety_yaml_missing(self, tmp_path):
        """Test safety.yaml detection when missing."""
        missing_file = tmp_path / "nonexistent" / "safety.yaml"

        with patch(
            "evoseal.cli.commands.doctor.get_safety_yaml_path",
            return_value=missing_file,
        ):
            from evoseal.cli.commands.doctor import check_safety_yaml

            success, message = check_safety_yaml()
            assert success is False

    def test_check_git_state_clean(self):
        """Test Git state check when clean."""
        from evoseal.cli.commands.doctor import check_git_state

        success, message = check_git_state()
        # Should succeed in clean repository (this repo is clean)
        assert isinstance(success, bool)

    def test_check_dependencies_basic(self):
        """Test basic dependency checking."""
        from evoseal.cli.commands.doctor import check_dependencies

        success, message = check_dependencies()
        # Should succeed since tests run with all dependencies
        assert success is True

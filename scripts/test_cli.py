#!/usr/bin/env python3
"""
Comprehensive test suite for the EVOSEAL CLI.

This script tests the functionality of the EVOSEAL CLI commands,
including edge cases and error conditions.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Import all packages first
import pytest
import yaml
from typer.testing import CliRunner

try:
    # Add the project root to the Python path after imports
    project_root = Path(__file__).parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    # Import local modules after path manipulation
    from evoseal import __version__
    from evoseal.cli.main import app
except Exception as e:
    error_msg = f"Error importing modules: {e}"
    print(error_msg, file=sys.stderr)
    sys.exit(1)

# Initialize the CLI test runner
runner = CliRunner()

# Test data
TEST_CONFIG = {
    "seal": {"model": "gpt-4", "temperature": 0.7, "max_tokens": 2048},
    "evolve": {
        "population_size": 100,
        "max_iterations": 1000,
        "checkpoint_interval": 10,
    },
}


def run_cli(
    command: list[str],
    input_text: str | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, str]:
    """Run a CLI command and return the exit code and combined output (stdout + stderr).

    Args:
        command: List of command-line arguments
        input_text: Optional input to send to the command
        cwd: Working directory for the command
        env: Environment variables to use

    Returns:
        Tuple of (exit_code, combined_output)
    """
    try:
        # Set up the command
        full_cmd = [sys.executable, "-m", "evoseal.cli.main"] + command

        # Prepare environment
        process_env = os.environ.copy()
        if env:
            process_env.update(env)

        # Ensure UTF-8 encoding
        process_env["PYTHONIOENCODING"] = "utf-8"

        # Print the command being run for debugging
        print(f"Running command: {' '.join(full_cmd)}")

        # Run the command
        result = subprocess.run(
            full_cmd,
            capture_output=True,
            text=True,
            input=input_text,
            cwd=cwd or Path(__file__).parent.parent,
            env=process_env,
            check=False,
        )

        # Combine stdout and stderr for the output
        combined_output = []
        if result.stdout:
            print(f"Command stdout:\n{result.stdout}")
            combined_output.append(result.stdout)
        if result.stderr:
            print(f"Command stderr:\n{result.stderr}")
            combined_output.append(result.stderr)

        return result.returncode, "\n".join(combined_output).strip()

    except Exception as e:
        error_msg = f"Error running command: {e}"
        print(error_msg, file=sys.stderr)
        return 1, error_msg


def test_cli_help() -> None:
    """Test that the CLI help command works."""
    exit_code, output = run_cli(["--help"])
    assert exit_code == 0
    assert "EVOSEAL: Evolutionary Self-Improving AI Agent" in output
    assert "COMMANDS" in output.upper()  # Case-insensitive check
    assert "init" in output
    assert "config" in output


def test_cli_version() -> None:
    """Test that the version command works."""
    # Test the version command using the version subcommand
    exit_code, output = run_cli(["--version"])

    # Check that the command succeeded
    assert exit_code == 0, f"Version command failed with output: {output}"

    # Check that the output contains the version string
    from evoseal import __version__

    assert (
        f"EVOSEAL v{__version__}" in output
    ), f"Version string not found in output: {output}".lower()

    # The exit code should be 0 for success
    # Note: The test runner might handle exit codes differently, so we'll log this
    if exit_code != 0:
        print(f"Warning: Version command returned non-zero exit code: {exit_code}")
        print(f"Output: {output}")


class TestInitCommand:
    """Test suite for the init command."""

    def test_init_creates_project_structure(self, tmp_path: Path) -> None:
        """Test that init creates the expected project structure."""
        # Create a temporary directory for the test
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()

        # Run the init command
        exit_code, output = run_cli(["init", "project", str(project_dir)])

        # Check that the command succeeded
        assert exit_code == 0, f"Init command failed with output: {output}"

        # Check that the expected directories and files were created
        expected_dirs = [
            "src",
            "data/raw",
            "data/processed",
            "notebooks",
            "tests",
            "docs",
        ]

        expected_files = [
            "README.md",
            "requirements.txt",
            "setup.py",
            ".gitignore",
            ".evoseal/config.yaml",
        ]

        for dir_path in expected_dirs:
            assert (project_dir / dir_path).is_dir(), f"Expected directory {dir_path} not found"

        for file_path in expected_files:
            assert (project_dir / file_path).is_file(), f"Expected file {file_path} not found"

        # Check that the output contains success message
        assert (
            "Successfully initialized EVOSEAL project" in output
        ), f"Success message not found in output: {output}"

    def test_init_in_non_empty_dir_fails(self, tmp_path: Path) -> None:
        """Test that init fails in non-empty directory without --force."""
        # Create a non-empty directory
        project_dir = tmp_path / "test_project"
        project_dir.mkdir()
        (project_dir / "existing_file.txt").write_text("test")

        # Run the init command
        exit_code, output = run_cli(["init", "project", str(project_dir)])

        # Check that the command failed
        assert exit_code != 0, "Expected init to fail in non-empty directory"

        # Check that the output contains an error message
        assert "is not empty" in output, f"Expected error about non-empty directory, got: {output}"

        # The error message should be in the output (either stdout or stderr)
        # Since we're capturing both in run_cli, we can just check the output
        assert "not empty" in output.lower(), f"Expected 'not empty' in output, got: {output}"

    def test_init_with_force_in_non_empty_dir(self, tmp_path: Path) -> None:
        """Test that init works with --force in non-empty directory."""
        (tmp_path / "existing_file.txt").write_text("test")

        exit_code, _ = run_cli(["init", "project", str(tmp_path), "--force"])
        assert exit_code == 0
        assert (tmp_path / ".evoseal").exists()


class TestConfigCommands:
    """Test suite for config commands."""

    @pytest.fixture(autouse=True)
    def setup(self, tmp_path: Path) -> None:
        """Set up a test project."""
        self.project_dir = tmp_path / "test_project"
        run_cli(["init", "project", str(self.project_dir)])
        os.chdir(self.project_dir)

    def test_config_set_get(self) -> None:
        """Test setting and getting config values."""
        # Set a config value
        exit_code, _ = run_cli(
            ["config", "set", "seal.model", "gpt-4"],
            input_text="y\n",  # Confirm overwrite
        )
        assert exit_code == 0

        # Get the config value using 'show' command
        exit_code, output = run_cli(["config", "show", "seal.model"])
        assert exit_code == 0, f"Command failed with output: {output}"
        assert "gpt-4" in output, f"Expected 'gpt-4' in output, got: {output}"

    def test_config_list(self) -> None:
        """Test listing all config values."""
        # First, set a config value to ensure there's something to list
        run_cli(["config", "set", "seal.model", "gpt-4"])

        # Now list all config values
        exit_code, output = run_cli(["config", "show"])
        assert exit_code == 0, f"Command failed with output: {output}"
        # Check for the expected YAML structure in the output
        assert "seal:" in output, f"Expected 'seal:' in output, got: {output}"
        assert "model: gpt-4" in output, f"Expected 'model: gpt-4' in output, got: {output}"

    def test_config_set_nonexistent_key(self) -> None:
        """Test setting a non-existent key."""
        # Set a new config value
        exit_code, output = run_cli(["config", "set", "nonexistent.key", "value"], input_text="y\n")
        assert exit_code == 0, f"Command failed with output: {output}"
        assert "Set nonexistent.key = value" in output, f"Unexpected output: {output}"

        # Verify the value was set
        exit_code, output = run_cli(["config", "show", "nonexistent.key"])
        assert exit_code == 0, f"Failed to get config value: {output}"
        assert "value" in output, f"Expected 'value' in output, got: {output}"

    def test_config_unset(self) -> None:
        """Test unsetting a config value."""
        # First set a value
        run_cli(["config", "set", "test.key", "value"], input_text="y\n")

        # Then unset it
        exit_code, output = run_cli(["config", "unset", "test.key"])
        assert exit_code == 0, f"Command failed with output: {output}"
        assert "Unset test.key" in output, f"Expected 'Unset test.key' in output, got: {output}"

        # Verify it's gone
        exit_code, output = run_cli(["config", "show", "test.key"])
        assert (
            exit_code != 0
        ), f"Expected command to fail after unsetting the key, but it succeeded with output: {output}"
        assert "not found" in output.lower(), f"Expected 'not found' in output, got: {output}"


class TestComponentCommands:
    """Test suite for component commands."""

    def test_seal_command_help(self) -> None:
        """Test that the SEAL command has help text."""
        exit_code, output = run_cli(["seal", "--help"])
        assert exit_code == 0, f"Command failed with output: {output}"
        assert (
            "seal model operations".lower() in output.lower()
        ), f"Expected 'seal model operations' in output, got: {output}"

    @pytest.mark.skip(reason="OpenEvolve command not yet implemented")
    def test_openevolve_command_help(self) -> None:
        """Test that the openevolve command has help text."""
        exit_code, output = run_cli(["openevolve", "--help"])
        assert exit_code == 0, f"Command failed with output: {output}"
        assert "openevolve" in output.lower(), f"Expected 'openevolve' in output, got: {output}"

    @pytest.mark.skip(reason="DGM command not yet implemented")
    def test_dgm_command_help(self) -> None:
        """Test that the DGM command has help text."""
        pass

    @pytest.mark.parametrize("subcmd", ["start", "stop", "status"])
    def test_service_commands(self, subcmd: str) -> None:
        """Test service management commands."""
        exit_code, output = run_cli([subcmd, "--help"])
        assert exit_code == 0, f"Command failed with output: {output}"
        assert subcmd in output.lower(), f"Expected '{subcmd}' in output, got: {output}"


class TestErrorConditions:
    """Test error conditions and edge cases."""

    def test_nonexistent_command(self) -> None:
        """Test handling of non-existent commands."""
        exit_code, output = run_cli(["nonexistent-command"])
        assert exit_code != 0, "Expected command to fail with non-existent command"
        assert (
            "no such command" in output.lower()
        ), f"Expected 'no such command' in output, got: {output}"

    def test_missing_required_arguments(self) -> None:
        """Test handling of missing required arguments."""
        exit_code, output = run_cli(["config", "set"])
        assert exit_code != 0, "Expected command to fail with missing arguments"
        assert (
            "missing argument" in output.lower()
        ), f"Expected 'missing argument' in output, got: {output}"

    def test_invalid_config_key(self) -> None:
        """Test handling of invalid config keys."""
        exit_code, output = run_cli(["config", "show", "invalid..key"])
        assert (
            exit_code != 0
        ), f"Expected command to fail with invalid key, but it succeeded with output: {output}"
        assert "invalid" in output.lower(), f"Expected 'invalid' in output, got: {output}"


if __name__ == "__main__":
    # Run the tests with increased verbosity
    pytest.main(["-v", "--tb=short", __file__])

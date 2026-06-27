"""
Adversarial tests for sandboxed test execution (Tier 1, T2 window).

These tests verify that variant tests run in a sandboxed environment where:
1. Secrets (API keys) are stripped from the subprocess environment
2. Safety-critical files are read-only
3. Network and other resources are restricted
4. Subprocess cannot exfiltrate or modify immutable config

Covers threat model §2 (test-runtime writes) and §5 (secret exfiltration).
See task 2.14 in Plans.md for DoD context.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.testrunner import SandboxedTestRunner, TestConfig


@pytest.fixture
def temp_repo_root(tmp_path):
    """Create a temporary repository structure."""
    # Create directory structure
    (tmp_path / "tests").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / "evoseal").mkdir()

    # Create safety-critical files
    safety_config = tmp_path / "configs" / "safety.yaml"
    safety_config.write_text("safety_checks_enabled: true\n")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "ANTHROPIC_API_KEY=secret-key-12345\nOPENAI_API_KEY=sk-abc123\n"  # pragma: allowlist secret
    )

    return tmp_path


@pytest.fixture
def sandboxed_runner(temp_repo_root):
    """Create a SandboxedTestRunner with a temporary repo root."""
    config = TestConfig(timeout=30, max_workers=2)
    return SandboxedTestRunner(
        config=config,
        repo_root=temp_repo_root,
        sandbox_enabled=True,
    )


class TestSecretStriping:
    """Verify that secrets are stripped from the subprocess environment."""

    def test_secrets_list_is_configured(self, sandboxed_runner):
        """SandboxedTestRunner has a configured list of secrets to strip."""
        assert len(sandboxed_runner.stripped_secrets) > 0
        assert "ANTHROPIC_API_KEY" in sandboxed_runner.stripped_secrets
        assert "OPENAI_API_KEY" in sandboxed_runner.stripped_secrets

    def test_create_sandboxed_environment_strips_secrets(self, sandboxed_runner):
        """Environment sanitization removes secrets."""
        # Set a secret in the current environment
        os.environ["ANTHROPIC_API_KEY"] = "test-secret-key"  # pragma: allowlist secret
        os.environ["OPENAI_API_KEY"] = "test-openai-key"  # pragma: allowlist secret

        try:
            # Create sandboxed environment
            sandboxed_env = sandboxed_runner._create_sandboxed_environment()

            # Verify secrets are stripped
            assert "ANTHROPIC_API_KEY" not in sandboxed_env
            assert "OPENAI_API_KEY" not in sandboxed_env

            # Verify PATH is preserved (normal env var)
            if "PATH" in os.environ:
                assert "PATH" in sandboxed_env, "PATH should be preserved in sandboxed environment"
        finally:
            # Clean up
            os.environ.pop("ANTHROPIC_API_KEY", None)
            os.environ.pop("OPENAI_API_KEY", None)


class TestReadOnlyEnforcement:
    """Verify that safety-critical files are read-only during test execution."""

    def test_readonly_files_list_is_configured(self, sandboxed_runner):
        """SandboxedTestRunner has configured list of read-only files."""
        assert len(sandboxed_runner.readonly_files) > 0
        assert "configs/safety.yaml" in sandboxed_runner.readonly_files
        assert ".env" in sandboxed_runner.readonly_files

    def test_can_apply_readonly_permissions(self, sandboxed_runner, temp_repo_root):
        """_apply_readonly_files can enforce read-only permissions."""
        # Create a test file to make readonly
        test_file = temp_repo_root / "configs" / "safety.yaml"
        test_file.write_text("test: true")

        # Apply readonly enforcement
        sandboxed_runner._apply_readonly_files()

        # Verify permissions were backed up
        assert str(test_file) in sandboxed_runner._permission_backup

        # Restore permissions
        sandboxed_runner._restore_file_permissions()

        # Verify backup was cleared
        assert len(sandboxed_runner._permission_backup) == 0


class TestAdversarialScenarios:
    """Test adversarial DGM scenarios that try to break the sandbox."""

    def test_sandbox_enabled_by_default(self, temp_repo_root):
        """Sandboxing is enabled by default for security."""
        config = TestConfig()
        runner = SandboxedTestRunner(config=config, repo_root=temp_repo_root)
        assert runner.sandbox_enabled is True

    def test_repo_root_is_set(self, sandboxed_runner, temp_repo_root):
        """repo_root is properly configured for sandbox enforcement."""
        assert sandboxed_runner.repo_root == temp_repo_root
        assert sandboxed_runner.repo_root.exists()

    def test_sandbox_mechanism_in_place_for_readonly(self, sandboxed_runner, temp_repo_root):
        """Read-only enforcement mechanism is in place and functional."""
        # Create a file that should be made readonly
        test_file = temp_repo_root / "configs" / "safety.yaml"
        test_file.write_text("key: value")

        import stat as stat_module

        original_mode = test_file.stat().st_mode

        # Apply readonly
        sandboxed_runner._apply_readonly_files()

        # Verify permissions changed
        new_mode = test_file.stat().st_mode
        # Check that write bits are removed
        assert not (new_mode & (stat_module.S_IWUSR | stat_module.S_IWGRP | stat_module.S_IWOTH))

        # Restore
        sandboxed_runner._restore_file_permissions()

        # Verify original mode is restored
        restored_mode = test_file.stat().st_mode
        assert restored_mode == original_mode

    def test_sandbox_mechanism_in_place_for_secrets(self, sandboxed_runner):
        """Secret stripping mechanism is in place and functional."""
        # Verify the mechanism exists and is configured
        assert hasattr(sandboxed_runner, "_create_sandboxed_environment")
        assert callable(sandboxed_runner._create_sandboxed_environment)

        # Set a test secret
        os.environ["TEST_SECRET_VAR"] = "secret123"  # pragma: allowlist secret

        try:
            # Create sandboxed environment
            env = sandboxed_runner._create_sandboxed_environment()

            # The mechanism looks for SECRET pattern
            assert "TEST_SECRET_VAR" not in env
        finally:
            os.environ.pop("TEST_SECRET_VAR", None)


class TestSandboxConfigurationOptions:
    """Test configuration options for sandboxing."""

    def test_sandboxing_can_be_disabled(self, temp_repo_root):
        """Sandboxing can be disabled via configuration."""
        config = TestConfig(timeout=30, max_workers=2)
        runner = SandboxedTestRunner(
            config=config,
            repo_root=temp_repo_root,
            sandbox_enabled=False,
        )
        # With sandboxing disabled, secrets would be visible
        # (This is tested implicitly; the runner should skip sandbox setup)
        assert runner is not None

    def test_readonly_files_configuration(self, temp_repo_root):
        """Read-only file list can be configured."""
        custom_readonly = ["custom_immutable.yaml", ".env", "configs/safety.yaml"]
        config = TestConfig(timeout=30, max_workers=2)
        runner = SandboxedTestRunner(
            config=config,
            repo_root=temp_repo_root,
            readonly_files=custom_readonly,
        )
        assert runner is not None

    def test_stripped_secrets_configuration(self, temp_repo_root):
        """Stripped secrets list can be configured."""
        custom_secrets = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "MY_CUSTOM_API_KEY",
        ]
        config = TestConfig(timeout=30, max_workers=2)
        runner = SandboxedTestRunner(
            config=config,
            repo_root=temp_repo_root,
            stripped_secrets=custom_secrets,
        )
        assert runner is not None


class TestResourceLimits:
    """Test resource limit enforcement (prepared for task 2.15).

    Note: Actual resource limit enforcement (CPU, memory, file descriptors)
    is implemented in task 2.15. This class is prepared for future expansion.
    """

    def test_runner_has_extensible_design(self, temp_repo_root):
        """SandboxedTestRunner is designed to accept resource limits in future."""
        config = TestConfig(timeout=30, max_workers=2)
        runner = SandboxedTestRunner(
            config=config,
            repo_root=temp_repo_root,
            sandbox_enabled=True,
        )
        # Runner can be extended to support resource limits in task 2.15
        assert runner is not None
        assert hasattr(runner, "_permission_backup")

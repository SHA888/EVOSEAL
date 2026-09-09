"""Tests for SandboxedTestRunner Tier 2 container sandbox integration (T2-5).

Verifies that ``SandboxedTestRunner`` routes test execution through
``ContainerSandbox`` when Docker is available and falls back to Tier 1
(subprocess + preexec_fn) when it is not.

All Docker SDK calls are mocked — no real Docker daemon is needed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.testrunner import SandboxedTestRunner, TestConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def repo_root(tmp_path: Path) -> Path:
    """Create a minimal fake repo root with a safety config."""
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs" / "safety.yaml").write_text("safe: true\n")
    (tmp_path / ".env").write_text("SECRET=1\n")
    return tmp_path


@pytest.fixture()
def test_config() -> TestConfig:
    return TestConfig(timeout=30)


# ---------------------------------------------------------------------------
# Container sandbox initialisation
# ---------------------------------------------------------------------------


class TestContainerSandboxInit:
    """Test that the container sandbox is initialised (or not) correctly."""

    def test_auto_init_when_docker_available(self, repo_root: Path) -> None:
        """Container sandbox is created automatically when docker package exists."""
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker,
        ):
            mock_docker.from_env.return_value = MagicMock()
            runner = SandboxedTestRunner(repo_root=str(repo_root))
            assert runner.container_sandbox_active is True

    def test_skip_when_explicitly_disabled(self, repo_root: Path) -> None:
        """``use_container_sandbox=False`` disables Tier 2 even if Docker exists."""
        runner = SandboxedTestRunner(repo_root=str(repo_root), use_container_sandbox=False)
        assert runner.container_sandbox_active is False

    def test_skip_when_docker_unavailable(self, repo_root: Path) -> None:
        """Falls back to Tier 1 when the docker package is not installed."""
        with patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", False):
            # Re-import to pick up the patched flag — but the class already
            # checked at __init__ time, so we test via the import path.
            runner = SandboxedTestRunner(repo_root=str(repo_root))
            # If DOCKER_AVAILABLE is False, ContainerSandbox.__init__ raises
            # RuntimeError — the runner should catch it and fall back.
            # However, the import itself succeeds (stub classes exist), so
            # we test the explicit path instead.
            assert runner.container_sandbox_active is False

    def test_raises_when_explicitly_enabled_but_docker_missing(self, repo_root: Path) -> None:
        """``use_container_sandbox=True`` propagates the error when Docker is missing."""
        with patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="docker"):
                SandboxedTestRunner(repo_root=str(repo_root), use_container_sandbox=True)

    def test_defaults_to_no_container_sandbox_when_import_fails(self, repo_root: Path) -> None:
        """Gracefully falls back when ``container_sandbox`` module is missing."""
        with patch.dict("sys.modules", {"evoseal.core.container_sandbox": None}):
            runner = SandboxedTestRunner(repo_root=str(repo_root))
            assert runner.container_sandbox_active is False


# ---------------------------------------------------------------------------
# Tier 2 execution path
# ---------------------------------------------------------------------------


class TestContainerExecution:
    """Test that _execute_test_command routes through ContainerSandbox."""

    @pytest.fixture()
    def runner_with_container(self, repo_root: Path) -> SandboxedTestRunner:
        """Runner with a mocked ContainerSandbox."""
        mock_sandbox = MagicMock()
        runner = SandboxedTestRunner(repo_root=str(repo_root), use_container_sandbox=False)
        # Inject the mock sandbox directly
        runner._container_sandbox = mock_sandbox
        return runner

    def test_routes_through_container_sandbox(
        self, runner_with_container: SandboxedTestRunner, test_config: TestConfig
    ) -> None:
        """When container sandbox is active, _execute_in_container is called."""
        from evoseal.core.container_sandbox import ContainerTestResult

        mock_result = ContainerTestResult(
            exit_code=0, stdout="all passed", stderr="", duration_seconds=1.5
        )
        runner_with_container._container_sandbox.run_variant_test.return_value = mock_result

        cmd = ["pytest", "tests/", "-q"]
        result = runner_with_container._execute_test_command(cmd, test_config)

        assert isinstance(result, subprocess.CompletedProcess)
        assert result.returncode == 0
        assert result.stdout == "all passed"
        assert result.stderr == ""

        # Verify the sandbox was called with the right args
        call_kwargs = runner_with_container._container_sandbox.run_variant_test.call_args
        assert call_kwargs.kwargs["command"] == cmd
        assert call_kwargs.kwargs["working_dir"] == "/workspace"
        assert "PYTHONPATH" in call_kwargs.kwargs["test_specific_env"]

    def test_mounts_repo_root_readonly(
        self, runner_with_container: SandboxedTestRunner, test_config: TestConfig
    ) -> None:
        """The repo root is mounted read-only at /workspace."""
        from evoseal.core.container_sandbox import ContainerTestResult

        runner_with_container._container_sandbox.run_variant_test.return_value = (
            ContainerTestResult(exit_code=0, stdout="", stderr="")
        )

        runner_with_container._execute_test_command(["pytest", "tests/", "-q"], test_config)

        call_kwargs = runner_with_container._container_sandbox.run_variant_test.call_args
        mounts = call_kwargs.kwargs["mounts"]
        repo_str = str(runner_with_container.repo_root)
        assert repo_str in mounts
        assert mounts[repo_str]["bind"] == "/workspace"
        assert mounts[repo_str]["mode"] == "ro"

    def test_propagates_nonzero_exit_code(
        self, runner_with_container: SandboxedTestRunner, test_config: TestConfig
    ) -> None:
        """Non-zero exit code from the container is preserved."""
        from evoseal.core.container_sandbox import ContainerTestResult

        runner_with_container._container_sandbox.run_variant_test.return_value = (
            ContainerTestResult(exit_code=1, stdout="FAIL", stderr="err")
        )

        result = runner_with_container._execute_test_command(
            ["pytest", "tests/", "-q"], test_config
        )
        assert result.returncode == 1
        assert result.stdout == "FAIL"
        assert result.stderr == "err"

    def test_falls_back_to_tier1_when_no_container_sandbox(
        self, repo_root: Path, test_config: TestConfig
    ) -> None:
        """When _container_sandbox is None, Tier 1 subprocess path is used."""
        runner = SandboxedTestRunner(repo_root=str(repo_root), use_container_sandbox=False)
        assert runner._container_sandbox is None

        with patch("evoseal.core.testrunner.subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=[], returncode=0, stdout="ok", stderr=""
            )
            result = runner._execute_test_command(["pytest", "tests/", "-q"], test_config)

        assert result.returncode == 0
        mock_run.assert_called_once()

    def test_container_timeout_result(
        self, runner_with_container: SandboxedTestRunner, test_config: TestConfig
    ) -> None:
        """Timed-out container results are passed through."""
        from evoseal.core.container_sandbox import ContainerTestResult

        runner_with_container._container_sandbox.run_variant_test.return_value = (
            ContainerTestResult(
                exit_code=-1,
                stdout="partial",
                stderr="",
                timed_out=True,
                error="timeout",
            )
        )

        result = runner_with_container._execute_test_command(
            ["pytest", "tests/", "-q"], test_config
        )
        assert result.returncode == -1

    def test_test_specific_env_passed(
        self, runner_with_container: SandboxedTestRunner, test_config: TestConfig
    ) -> None:
        """PYTHONPATH is set in the container environment."""
        from evoseal.core.container_sandbox import ContainerTestResult

        runner_with_container._container_sandbox.run_variant_test.return_value = (
            ContainerTestResult(exit_code=0, stdout="", stderr="")
        )

        runner_with_container._execute_test_command(["pytest", "tests/", "-q"], test_config)

        call_kwargs = runner_with_container._container_sandbox.run_variant_test.call_args
        env = call_kwargs.kwargs["test_specific_env"]
        assert "PYTHONPATH" in env
        assert env["PYTHONPATH"] == "/workspace"


# ---------------------------------------------------------------------------
# Integration: run_tests with container sandbox
# ---------------------------------------------------------------------------


class TestRunTestsContainerIntegration:
    """Test that run_tests works end-to-end with a mocked container sandbox."""

    def test_run_tests_uses_container_when_active(self, repo_root: Path) -> None:
        """Full run_tests flow delegates to container sandbox."""
        from evoseal.core.container_sandbox import ContainerTestResult

        mock_sandbox = MagicMock()
        mock_sandbox.run_variant_test.return_value = ContainerTestResult(
            exit_code=0,
            stdout="1 passed",
            stderr="",
            duration_seconds=0.5,
        )

        runner = SandboxedTestRunner(repo_root=str(repo_root), use_container_sandbox=False)
        runner._container_sandbox = mock_sandbox

        with (
            patch.object(runner, "_apply_readonly_files"),
            patch.object(runner, "_restore_file_permissions"),
        ):
            results = runner.run_tests(str(repo_root), test_types=["unit"])

        assert len(results) >= 1
        # The container sandbox was called at least once
        assert mock_sandbox.run_variant_test.called

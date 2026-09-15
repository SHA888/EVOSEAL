"""Unit tests for ContainerSandbox (Tier 2, T2-2).

Tests the container-based sandbox for variant test execution.
All Docker SDK calls are mocked — no Docker daemon required.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.core.container_sandbox import (
    DOCKER_AVAILABLE,
    ContainerSandbox,
    ContainerTestResult,
    _is_secret_file,
    _nano_cpus,
    _validate_command,
    _validate_image,
    _validate_mount_source,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_container(
    exit_code: int = 0,
    logs: bytes = b"test output",
    short_id: str = "abc123",
) -> MagicMock:
    """Build a mock Docker container."""
    container = MagicMock()
    container.short_id = short_id
    container.wait.return_value = {"StatusCode": exit_code}
    container.logs.return_value = logs
    return container


def _make_mock_client(container: MagicMock | None = None) -> MagicMock:
    """Build a mock Docker client."""
    client = MagicMock()
    if container is not None:
        client.containers.run.return_value = container
    return client


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


class TestValidateImage:
    """Test _validate_image input validation."""

    def test_valid_image_evoseal_local(self):
        _validate_image("evoseal:local")

    def test_valid_image_with_registry(self):
        _validate_image("ghcr.io/owner/repo:tag")

    def test_valid_image_bare_name(self):
        _validate_image("ubuntu")

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_image("")

    def test_rejects_none(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_image(None)  # type: ignore[arg-type]

    def test_rejects_shell_metacharacters(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_image("evoseal:local; rm -rf /")

    def test_rejects_protocol_prefix(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_image("https://evil.com/image:tag")

    def test_rejects_path_traversal(self):
        with pytest.raises(ValueError, match="disallowed"):
            _validate_image("../../../etc/passwd")


class TestValidateCommand:
    """Test _validate_command input validation."""

    def test_valid_pytest_command(self):
        result = _validate_command(["pytest", "tests/", "-q"])
        assert result == ["pytest", "tests/", "-q"]

    def test_valid_python_m_pytest(self):
        result = _validate_command(["python", "-m", "pytest", "tests/"])
        assert result == ["python", "-m", "pytest", "tests/"]

    def test_valid_string_command(self):
        result = _validate_command("pytest tests/ -q")
        assert result == ["pytest", "tests/", "-q"]

    def test_rejects_empty_command(self):
        with pytest.raises(ValueError, match="non-empty"):
            _validate_command([])

    def test_rejects_disallowed_command(self):
        with pytest.raises(ValueError, match="does not start with"):
            _validate_command(["curl", "http://evil.com"])

    def test_rejects_shell_injection_semicolon(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            _validate_command(["pytest; rm -rf /"])

    def test_rejects_shell_injection_pipe(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            _validate_command(["pytest", "|", "curl", "http://evil.com"])

    def test_rejects_shell_injection_dollar(self):
        with pytest.raises(ValueError, match="shell metacharacters"):
            _validate_command(["pytest", "$(whoami)"])


class TestValidateMountSource:
    """Test _validate_mount_source path validation."""

    def test_valid_path_no_root_constraint(self):
        result = _validate_mount_source("/some/path")
        assert result == Path("/some/path").resolve()

    def test_valid_path_within_allowed_root(self, tmp_path):
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        result = _validate_mount_source(str(subdir), allowed_root=tmp_path)
        assert result == subdir.resolve()

    def test_rejects_path_outside_allowed_root(self, tmp_path):
        outside = Path("/tmp/outside_workspace")
        with pytest.raises(ValueError, match="escapes allowed root"):
            _validate_mount_source(str(outside), allowed_root=tmp_path)


class TestNanoCpus:
    """Test CPU limit conversion."""

    def test_one_cpu(self):
        assert _nano_cpus("1.0") == 1_000_000_000

    def test_half_cpu(self):
        assert _nano_cpus("0.5") == 500_000_000

    def test_two_cpus(self):
        assert _nano_cpus("2.0") == 2_000_000_000


# ---------------------------------------------------------------------------
# ContainerSandbox class
# ---------------------------------------------------------------------------


class TestContainerSandboxInit:
    """Test ContainerSandbox construction."""

    def test_default_values(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            assert sandbox.image == "evoseal:local"
            assert sandbox.cpu_limit == "1.0"
            assert sandbox.memory_limit == "512m"
            assert sandbox.pids_limit == 256
            assert sandbox.timeout_seconds == 300
            assert sandbox.read_only_root is True

    def test_custom_values(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox(
                image="python:3.11-slim",
                cpu_limit="0.5",
                memory_limit="256m",
                pids_limit=128,
                timeout_seconds=60,
                read_only_root=False,
            )
            assert sandbox.image == "python:3.11-slim"
            assert sandbox.cpu_limit == "0.5"
            assert sandbox.memory_limit == "256m"
            assert sandbox.pids_limit == 128
            assert sandbox.timeout_seconds == 60
            assert sandbox.read_only_root is False

    def test_raises_if_docker_not_available(self):
        with patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", False):
            with pytest.raises(RuntimeError, match="docker.*Python package is required"):
                ContainerSandbox()

    def test_rejects_invalid_image(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            with pytest.raises(ValueError, match="disallowed"):
                ContainerSandbox(image="evil; image")


class TestContainerSandboxFromConfig:
    """Test ContainerSandbox.from_config classmethod."""

    def test_from_config_defaults(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox.from_config({})
            assert sandbox.image == "evoseal:local"
            assert sandbox.cpu_limit == "1.0"

    def test_from_config_custom(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox.from_config(
                {
                    "image": "python:3.11",
                    "cpu_limit": "2.0",
                    "memory_limit": "1g",
                    "pids_limit": 512,
                    "timeout_seconds": 600,
                }
            )
            assert sandbox.image == "python:3.11"
            assert sandbox.cpu_limit == "2.0"
            assert sandbox.memory_limit == "1g"
            assert sandbox.pids_limit == 512
            assert sandbox.timeout_seconds == 600


class TestRunVariantTest:
    """Test ContainerSandbox.run_variant_test execution flow."""

    def test_successful_execution(self, tmp_path):
        mock_container = _make_mock_container(exit_code=0, logs=b"all tests passed")
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            result = sandbox.run_variant_test(
                command=["pytest", "tests/", "-q"],
            )

        assert result.exit_code == 0
        assert "all tests passed" in result.stdout
        assert result.timed_out is False
        assert result.error is None
        assert result.container_id == "abc123"
        assert result.duration_seconds >= 0

        # Container should be created with correct parameters
        mock_client.containers.run.assert_called_once()
        call_kwargs = mock_client.containers.run.call_args
        assert call_kwargs.kwargs.get("network_disabled") is True
        assert call_kwargs.kwargs.get("detach") is True
        assert call_kwargs.kwargs.get("read_only") is True

        # Container should be cleaned up
        mock_container.remove.assert_called_once_with(force=True)

    def test_failed_test_execution(self, tmp_path):
        mock_container = _make_mock_container(exit_code=1, logs=b"FAILED test_foo")
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            result = sandbox.run_variant_test(command=["pytest", "tests/", "-q"])

        assert result.exit_code == 1
        assert "FAILED" in result.stdout

    def test_timeout_triggers_kill(self, tmp_path):
        from evoseal.core.container_sandbox import APIError as RealAPIError

        mock_container = _make_mock_container()
        mock_container.wait.side_effect = Exception("timeout")
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker_mod,
        ):
            mock_docker_mod.APIError = RealAPIError
            sandbox = ContainerSandbox(timeout_seconds=5)
            sandbox._client = mock_client

            result = sandbox.run_variant_test(command=["pytest", "tests/", "-q"])

        assert result.timed_out is True
        assert result.exit_code == -1
        mock_container.kill.assert_called_once()

    def test_no_host_secrets_passed(self, tmp_path):
        """T2-3: verify that no host environment variables are forwarded."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            sandbox.run_variant_test(
                command=["pytest", "tests/"],
                test_specific_env={"MY_TEST_VAR": "value"},
            )

        call_kwargs = mock_client.containers.run.call_args.kwargs
        # Only test_specific_env should be passed — not os.environ
        assert call_kwargs["environment"] == {"MY_TEST_VAR": "value"}

    def test_no_env_at_all_by_default(self, tmp_path):
        """T2-3: with no test_specific_env, environment should be empty dict."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            sandbox.run_variant_test(command=["pytest", "tests/"])

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["environment"] == {}

    def test_resource_limits_applied(self, tmp_path):
        """T2-4: verify CPU, memory, and PID limits are passed."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox(
                cpu_limit="0.5",
                memory_limit="256m",
                pids_limit=128,
            )
            sandbox._client = mock_client

            sandbox.run_variant_test(command=["pytest", "tests/"])

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["nano_cpus"] == 500_000_000
        assert call_kwargs["mem_limit"] == "256m"
        assert call_kwargs["pids_limit"] == 128

    def test_mount_validation_within_allowed_root(self, tmp_path):
        """Mount sources inside allowed_mount_root are accepted."""
        subdir = tmp_path / "workspace"
        subdir.mkdir()

        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker_mod,
        ):
            mock_docker_mod.types = MagicMock()
            mock_docker_mod.types.Mount = MagicMock()
            sandbox = ContainerSandbox(allowed_mount_root=str(tmp_path))
            sandbox._client = mock_client

            sandbox.run_variant_test(
                command=["pytest", "tests/"],
                mounts={str(subdir): {"bind": "/app", "mode": "ro"}},
            )

        mock_client.containers.run.assert_called_once()

    def test_mount_validation_rejects_outside_root(self, tmp_path):
        """Mount sources outside allowed_mount_root are rejected."""
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox(allowed_mount_root=str(tmp_path))
            sandbox._client = _make_mock_client()

            with pytest.raises(ValueError, match="escapes allowed root"):
                sandbox.run_variant_test(
                    command=["pytest", "tests/"],
                    mounts={"/etc/passwd": {"bind": "/app", "mode": "ro"}},
                )

    def test_read_only_root_with_tmpfs(self, tmp_path):
        """When read_only_root=True, tmpfs is configured for /tmp."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox(read_only_root=True, tmpfs_size="200m")
            sandbox._client = mock_client

            sandbox.run_variant_test(command=["pytest", "tests/"])

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["read_only"] is True
        assert call_kwargs["tmpfs"] == {"/tmp": "size=200m"}

    def test_read_only_root_disabled(self, tmp_path):
        """When read_only_root=False, no tmpfs is configured."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox(read_only_root=False)
            sandbox._client = mock_client

            sandbox.run_variant_test(command=["pytest", "tests/"])

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["read_only"] is False
        assert call_kwargs["tmpfs"] is None

    def test_cleanup_on_api_error(self, tmp_path):
        """Container is removed even when API errors occur."""
        from evoseal.core.container_sandbox import APIError as RealAPIError

        mock_container = _make_mock_container()
        mock_container.wait.side_effect = RealAPIError("connection lost")
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker_mod,
        ):
            mock_docker_mod.APIError = RealAPIError
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            result = sandbox.run_variant_test(command=["pytest", "tests/"])

        # Should return error result, not raise
        assert result.error is not None
        # Container should still be cleaned up
        mock_container.remove.assert_called_once_with(force=True)

    def test_cleanup_on_container_error(self, tmp_path):
        """Container is removed when ContainerError occurs."""
        from evoseal.core.container_sandbox import (
            APIError as RealAPIError,
        )
        from evoseal.core.container_sandbox import (
            ContainerError as RealContainerError,
        )
        from evoseal.core.container_sandbox import (
            ImageNotFound as RealImageNotFound,
        )

        mock_client = MagicMock()
        mock_client.containers.run.side_effect = RealContainerError(
            container=_make_mock_container(),
            exit_status=1,
            command="pytest",
            stderr=b"error",
            image="evoseal:local",
        )

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker_mod,
        ):
            mock_docker_mod.ContainerError = RealContainerError
            mock_docker_mod.ImageNotFound = RealImageNotFound
            mock_docker_mod.APIError = RealAPIError
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            result = sandbox.run_variant_test(command=["pytest", "tests/"])

        assert result.exit_code == 1


class TestContainerSandboxClose:
    """Test client lifecycle management."""

    def test_close_closes_client(self):
        mock_client = MagicMock()

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client
            sandbox.close()

        mock_client.close.assert_called_once()
        assert sandbox._client is None

    def test_close_noop_when_no_client(self):
        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            # Should not raise
            sandbox.close()


class TestIsSecretFile:
    """T2-3: test _is_secret_file pattern detection."""

    def test_dotenv(self):
        assert _is_secret_file(Path("/workspace/.env")) is True

    def test_dotenv_local(self):
        assert _is_secret_file(Path("/workspace/.env.local")) is True

    def test_dotenv_production(self):
        assert _is_secret_file(Path("/project/.env.production")) is True

    def test_dotenv_dev(self):
        assert _is_secret_file(Path("/project/.env.dev")) is True

    def test_key_suffix(self):
        assert _is_secret_file(Path("/certs/server.key")) is True

    def test_pem_suffix(self):
        assert _is_secret_file(Path("/certs/ca.pem")) is True

    def test_p12_suffix(self):
        assert _is_secret_file(Path("/certs/client.p12")) is True

    def test_ssh_key(self):
        assert _is_secret_file(Path("/home/user/.ssh/id_rsa")) is True

    def test_ssh_ed25519(self):
        assert _is_secret_file(Path("/home/user/.ssh/id_ed25519")) is True

    def test_netrc(self):
        assert _is_secret_file(Path("/home/user/.netrc")) is True

    def test_shadow(self):
        assert _is_secret_file(Path("/etc/shadow")) is True

    def test_service_account(self):
        assert _is_secret_file(Path("/config/service-account.json")) is True

    def test_regular_file_not_secret(self):
        assert _is_secret_file(Path("/workspace/app.py")) is False

    def test_regular_test_file_not_secret(self):
        assert _is_secret_file(Path("/workspace/tests/test_foo.py")) is False

    def test_regular_yaml_not_secret(self):
        assert _is_secret_file(Path("/workspace/config.yaml")) is False

    def test_directory_not_secret(self):
        assert _is_secret_file(Path("/workspace/.ssh")) is False

    def test_case_insensitive(self):
        assert _is_secret_file(Path("/workspace/ID_RSA")) is True
        assert _is_secret_file(Path("/workspace/Server.KEY")) is True

    def test_pypirc(self):
        assert _is_secret_file(Path("/home/user/.pypirc")) is True

    def test_npmrc(self):
        assert _is_secret_file(Path("/home/user/.npmrc")) is True


class TestValidateMountSourceSecretRejection:
    """T2-3: test that _validate_mount_source rejects secret files."""

    def test_rejects_dotenv(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/workspace/.env")

    def test_rejects_dotenv_with_root(self, tmp_path):
        """Secret file inside allowed_root is still rejected."""
        env_file = tmp_path / ".env"
        env_file.write_text("NOT_SECRET=value")  # pragma: allowlist secret
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source(str(env_file), allowed_root=tmp_path)

    def test_rejects_key_file(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/certs/server.key")

    def test_rejects_pem_file(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/certs/ca.pem")

    def test_rejects_ssh_key(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/home/user/.ssh/id_rsa")

    def test_accepts_regular_file(self, tmp_path):
        regular = tmp_path / "app.py"
        regular.write_text("print('hello')")
        result = _validate_mount_source(str(regular), allowed_root=tmp_path)
        assert result == regular.resolve()

    def test_reject_secrets_can_be_disabled(self):
        """Caller can explicitly opt out of secret rejection."""
        result = _validate_mount_source("/workspace/.env", reject_secrets=False)
        assert result == Path("/workspace/.env").resolve()

    def test_rejects_dotenv_local(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/workspace/.env.local")

    def test_rejects_dotenv_production(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/workspace/.env.production")

    def test_rejects_service_account(self):
        with pytest.raises(ValueError, match="secret/credential file"):
            _validate_mount_source("/config/service-account.json")


class TestContainerSandboxNoHostSecrets:
    """T2-3: end-to-end no-host-secrets guarantee tests."""

    def test_dotenv_mount_rejected(self, tmp_path):
        """Mounting a .env file into the container is rejected."""
        env_file = tmp_path / ".env"
        env_file.write_text("API_KEY=not-a-real-key")  # pragma: allowlist secret

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = _make_mock_client()

            with pytest.raises(ValueError, match="secret/credential file"):
                sandbox.run_variant_test(
                    command=["pytest", "tests/"],
                    mounts={str(env_file): {"bind": "/app/.env", "mode": "ro"}},
                )

    def test_key_file_mount_rejected(self, tmp_path):
        """Mounting a .key file into the container is rejected."""
        key_file = tmp_path / "server.key"
        key_file.write_text("not-a-real-key")

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = _make_mock_client()

            with pytest.raises(ValueError, match="secret/credential file"):
                sandbox.run_variant_test(
                    command=["pytest", "tests/"],
                    mounts={str(key_file): {"bind": "/app/key.pem", "mode": "ro"}},
                )

    def test_ssh_key_mount_rejected(self, tmp_path):
        """Mounting an SSH private key into the container is rejected."""
        ssh_dir = tmp_path / ".ssh"
        ssh_dir.mkdir()
        key_file = ssh_dir / "id_rsa"
        key_file.write_text("not-a-real-key")

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = _make_mock_client()

            with pytest.raises(ValueError, match="secret/credential file"):
                sandbox.run_variant_test(
                    command=["pytest", "tests/"],
                    mounts={str(key_file): {"bind": "/root/.ssh/id_rsa", "mode": "ro"}},
                )

    def test_regular_mount_accepted(self, tmp_path):
        """Non-secret files can still be mounted."""
        app_dir = tmp_path / "app"
        app_dir.mkdir()
        (app_dir / "test_foo.py").write_text("def test_pass(): pass")

        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker") as mock_docker_mod,
        ):
            mock_docker_mod.types = MagicMock()
            mock_docker_mod.types.Mount = MagicMock()
            sandbox = ContainerSandbox(allowed_mount_root=str(tmp_path))
            sandbox._client = mock_client

            result = sandbox.run_variant_test(
                command=["pytest", "tests/"],
                mounts={str(app_dir): {"bind": "/app", "mode": "ro"}},
            )

        assert result.exit_code == 0
        mock_client.containers.run.assert_called_once()

    def test_no_host_environ_leaked(self, tmp_path):
        """T2-3: container environment is exactly test_specific_env, never os.environ.

        This is the key difference from Tier 1's env-stripping approach:
        Tier 1 copies os.environ then removes known secret keys (leaving
        unknown secrets in place).  Tier 2 starts from an empty environment.
        """
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        # Simulate host having secrets in the environment
        fake_environ = {
            "ANTHROPIC_API_KEY": "sk-not-a-real-key",  # pragma: allowlist secret
            "OPENAI_API_KEY": "sk-not-a-real-key",  # pragma: allowlist secret
            "MY_CUSTOM_SECRET": "not-a-real-value",  # pragma: allowlist secret
            "HOME": "/home/evoseal",
            "PATH": "/usr/bin",
        }

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
            patch("os.environ", fake_environ),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            sandbox.run_variant_test(
                command=["pytest", "tests/"],
                test_specific_env={"TEST_MODE": "1"},
            )

        call_kwargs = mock_client.containers.run.call_args.kwargs
        # Must contain ONLY the test-specific var
        assert call_kwargs["environment"] == {"TEST_MODE": "1"}
        # Must NOT contain any host secrets
        assert "ANTHROPIC_API_KEY" not in call_kwargs["environment"]
        assert "OPENAI_API_KEY" not in call_kwargs["environment"]
        assert "MY_CUSTOM_SECRET" not in call_kwargs["environment"]
        # Must NOT contain any host non-secret vars either
        assert "HOME" not in call_kwargs["environment"]
        assert "PATH" not in call_kwargs["environment"]

    def test_no_environ_at_all_when_no_test_env(self, tmp_path):
        """T2-3: with no test_specific_env, environment is completely empty."""
        mock_container = _make_mock_container()
        mock_client = _make_mock_client(mock_container)

        fake_environ = {
            "ANTHROPIC_API_KEY": "sk-not-a-real-key",  # pragma: allowlist secret
            "HOME": "/home/evoseal",
        }

        with (
            patch("evoseal.core.container_sandbox.DOCKER_AVAILABLE", True),
            patch("evoseal.core.container_sandbox.docker"),
            patch("os.environ", fake_environ),
        ):
            sandbox = ContainerSandbox()
            sandbox._client = mock_client

            sandbox.run_variant_test(command=["pytest", "tests/"])

        call_kwargs = mock_client.containers.run.call_args.kwargs
        assert call_kwargs["environment"] == {}


class TestContainerTestResult:
    """Test the result dataclass."""

    def test_defaults(self):
        result = ContainerTestResult(exit_code=0, stdout="", stderr="")
        assert result.timed_out is False
        assert result.error is None
        assert result.duration_seconds == 0.0
        assert result.container_id is None

    def test_with_values(self):
        result = ContainerTestResult(
            exit_code=1,
            stdout="output",
            stderr="error",
            timed_out=True,
            error="timeout",
            duration_seconds=5.0,
            container_id="abc123",
        )
        assert result.exit_code == 1
        assert result.stdout == "output"
        assert result.timed_out is True

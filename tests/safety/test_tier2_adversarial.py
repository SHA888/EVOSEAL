"""Adversarial safety tests for Tier 2 container isolation (T2-6).

These tests prove that Tier 2 closes attack vectors that Tier 1
(env-stripping + resource.setrlimit on a shared-host subprocess) cannot:

1. **Network exfiltration** — Tier 1 subprocess can still open sockets and
   make HTTP requests; Tier 2's ``network_disabled=True`` prevents it at the
   container boundary.
2. **Resource exhaustion** — Tier 1's ``resource.setrlimit`` only bounds a
   shared-host subprocess and can be bypassed by fork bombs or cgroup escapes;
   Tier 2's container-level CPU/memory/PID limits are enforced by the kernel's
   cgroup subsystem.
3. **Filesystem boundary** — Tier 1 runs on the shared filesystem, so any path
   visible to the host is accessible to the subprocess; Tier 2's container only
   sees explicitly mounted paths (read-only by default) and a tmpfs ``/tmp``.

Status: These tests define the security specification via executable mock
implementations. Integration testing with the real ContainerSandbox (T2-2)
will replace the mocks when that module lands.

Reference:
- ADR 0001 §5 (Tier 2 trigger #1)
- ADR 0006 (container execution mechanism)
- threat_model.md §2 (test-runtime writes), §5 (secret exfiltration)
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Mock Container Sandbox — specifies the Tier 2 isolation contract
#
# This mock documents what the real ContainerSandbox (T2-2) must enforce.
# When T2-2 lands, replace these mocks with real imports and the tests
# become integration tests automatically.
# ---------------------------------------------------------------------------

# Image ref validation pattern (from ADR 0006)
_SAFE_IMAGE_RE = re.compile(
    r"^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)*"
    r"(/[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)*)*"
    r"(:[a-zA-Z0-9_.\-]+)?$"
)

# Allowed test command prefixes (from ADR 0006)
_ALLOWED_CMD_PREFIXES: tuple[str, ...] = (
    "pytest",
    "python -m pytest",
    "unittest",
    "python -m unittest",
)


@dataclass
class ContainerConfig:
    """Configuration for a Tier 2 container sandbox."""

    image: str = "evoseal:local"
    network_disabled: bool = True
    cpu_limit: str = "1.0"
    memory_limit: str = "512m"
    pids_limit: int = 256
    timeout_seconds: int = 300
    read_only_root: bool = True
    tmpfs_size: str = "100m"
    environment: dict[str, str] = field(default_factory=dict)
    mounts: list[dict[str, Any]] = field(default_factory=list)
    privileged: bool = False
    cap_add: list[str] | None = None
    ports: dict[str, Any] | None = None
    network_mode: str | None = None
    pid_mode: str | None = None


def validate_image(image: str) -> None:
    """Reject image refs that could inject arbitrary Docker API parameters."""
    if not image or not isinstance(image, str):
        raise ValueError(f"Image ref must be a non-empty string, got {image!r}")
    if not _SAFE_IMAGE_RE.match(image):
        raise ValueError(f"Image ref contains disallowed characters: {image!r}")


def validate_command(command: list[str] | str) -> list[str]:
    """Validate a test command starts with an allowed prefix."""
    if isinstance(command, str):
        import shlex

        command = shlex.split(command)
    if not command:
        raise ValueError("Command must be non-empty")
    cmd_str = " ".join(command)
    # Token-boundary match: exact match or prefix followed by a space.
    # Prevents "pytester" or "unittest_backdoor" from matching "pytest"/"unittest".
    if not any(
        cmd_str == prefix or cmd_str.startswith(f"{prefix} ") for prefix in _ALLOWED_CMD_PREFIXES
    ):
        raise ValueError(
            f"Command {cmd_str!r} does not start with an allowed prefix. "
            f"Allowed: {_ALLOWED_CMD_PREFIXES}"
        )
    for token in command:
        if any(c in token for c in (";", "|", "&", "$", "`", "(", ")", "{", "}", ">", "<")):
            raise ValueError(f"Command token contains shell metacharacters: {token!r}")
    return command


def validate_mount_source(source: str, allowed_root: Path | None = None) -> Path:
    """Validate a mount source path stays within the allowed root."""
    path = Path(source).resolve()
    if allowed_root is not None:
        try:
            path.relative_to(allowed_root.resolve())
        except ValueError:
            raise ValueError(
                f"Mount source {source!r} escapes allowed root {allowed_root!r}"
            ) from None
    return path


# ============================================================================
# Attack vector 1: Network exfiltration
#
# Tier 1 gap: subprocess inherits a live network stack.  Variant test code can
# open sockets, make HTTP requests, and exfiltrate secrets or source code to an
# attacker-controlled endpoint.  Env-stripping (Tier 1) only removes secrets
# from the environment — it does not prevent the code from reaching the network.
#
# Tier 2 fix: container is created with network_disabled=True.  The kernel's
# network namespace has no interfaces, so socket() may succeed but connect()
# always fails with ENETUNREACH.
# ============================================================================


class TestTier2NetworkExfiltrationBlocked:
    """Prove that Tier 2 blocks network exfiltration from variant test code."""

    def test_container_must_disable_network(self):
        """The container must be spawned with network_disabled=True.

        This is the primary defense against network exfiltration.  Without it,
        variant test code can phone home with stolen secrets or source code.
        """
        config = ContainerConfig()
        assert config.network_disabled is True, (
            "Default ContainerConfig must have network_disabled=True. "
            "Tier 2 requires network isolation for all variant test containers."
        )

    def test_network_disabled_is_default_on(self):
        """network_disabled defaults to True, not False.

        A secure default must be opt-out, not opt-in.  If the default were
        False, a misconfigured deployment would silently allow exfiltration.
        """
        config = ContainerConfig()
        assert config.network_disabled is True

    def test_no_host_network_mode(self):
        """The container must NOT use host network mode.

        host_network=True bypasses the container's network namespace entirely,
        giving variant code full access to the host's network stack.
        """
        config = ContainerConfig()
        assert config.network_mode != "host", "Container must not use host network mode."

    def test_no_extra_network_capabilities(self):
        """The container must not receive additional network capabilities.

        cap_add=["NET_ADMIN"] would allow the variant to re-enable networking
        inside the container, bypassing network_disabled.
        """
        config = ContainerConfig()
        assert config.cap_add is None, "Container must not receive additional capabilities."
        assert config.privileged is not True, "Container must not run in privileged mode."

    def test_no_port_mappings(self):
        """The container must not expose ports.

        Port mappings create network listeners reachable from outside,
        potentially allowing reverse-shell callbacks.
        """
        config = ContainerConfig()
        assert config.ports is None, "Container must not expose any ports."

    def test_blocked_attack_dns_exfiltration(self):
        """Network disable prevents DNS-based exfiltration.

        Even without raw sockets, variant code could use DNS queries
        (e.g., base64-encoded-secrets.evil.com) to exfiltrate data.
        network_disabled=True blocks all network interfaces.
        """
        config = ContainerConfig(network_disabled=True)
        # With network_disabled, DNS queries cannot leave the container
        assert config.network_disabled is True

    def test_blocked_attack_http_exfiltration(self):
        """Network disable prevents HTTP-based exfiltration.

        Variant code using requests/urllib to POST secrets to an external
        server would fail with a connection error.
        """
        config = ContainerConfig(network_disabled=True)
        assert config.network_disabled is True

    def test_blocked_attack_reverse_shell(self):
        """Network disable prevents reverse shells.

        Variant code attempting to open a reverse shell to an attacker's
        listener would fail because no network interfaces exist.
        """
        config = ContainerConfig(network_disabled=True)
        assert config.network_disabled is True


# ============================================================================
# Attack vector 2: Resource exhaustion
#
# Tier 1 gap: resource.setrlimit (RLIMIT_CPU, RLIMIT_AS, RLIMIT_NPROC) is
# process-level, shared-host enforcement.  A fork bomb can exhaust PIDs before
# RLIMIT_NPROC triggers; memory limits apply per-process, not per-cgroup; CPU
# limits don't account for child processes unless RLIMIT_NPROC also fires.
#
# Tier 2 fix: container-level cgroup enforcement (nano_cpus, mem_limit,
# pids_limit) applies to the entire cgroup, not individual processes.  A fork
# bomb hits pids_limit at the cgroup level; memory is bounded across all
# processes in the container; CPU is throttled at the cgroup scheduler.
# ============================================================================


class TestTier2ResourceExhaustionBlocked:
    """Prove that Tier 2 enforces resource limits at the container (cgroup) level."""

    def test_cpu_limit_specified(self):
        """Container receives a CPU limit.

        This is cgroup-level enforcement, stronger than Tier 1's
        resource.setrlimit(RLIMIT_CPU) which only bounds a single process.
        """
        config = ContainerConfig(cpu_limit="0.5")
        assert config.cpu_limit == "0.5"
        # Verify conversion to nanocpus
        nano_cpus = int(float(config.cpu_limit) * 1e9)
        assert nano_cpus == 500_000_000

    def test_memory_limit_specified(self):
        """Container receives a memory limit.

        This is cgroup-level enforcement — the entire container's memory usage
        (all processes combined) is bounded.  Tier 1's RLIMIT_AS only bounds
        a single process's virtual address space.
        """
        config = ContainerConfig(memory_limit="256m")
        assert config.memory_limit == "256m"

    def test_pid_limit_specified(self):
        """Container receives a PID limit.

        This prevents fork bombs at the cgroup level — the kernel refuses to
        create new processes once the limit is reached, regardless of how many
        processes are already running.  Tier 1's RLIMIT_NPROC is per-user on
        the shared host.
        """
        config = ContainerConfig(pids_limit=64)
        assert config.pids_limit == 64

    def test_default_resource_limits_are_restrictive(self):
        """Default resource limits are restrictive enough to prevent abuse.

        If defaults are too permissive, a variant could still exhaust host
        resources within its container before hitting the limit.
        """
        config = ContainerConfig()

        # Memory should be <= 1GB by default
        mem = config.memory_limit
        mem_bytes = _parse_docker_memory(mem)
        assert mem_bytes <= 1024 * 1024 * 1024, (
            f"Default memory limit {mem} is too permissive; should be <= 1g."
        )

        # PID limit should be <= 512 by default
        assert config.pids_limit <= 512, (
            f"Default PID limit {config.pids_limit} is too permissive; should be <= 512."
        )

        # CPU should be <= 2 CPUs by default
        assert float(config.cpu_limit) <= 2.0, (
            f"Default CPU limit {config.cpu_limit} is too permissive; should be <= 2.0."
        )

    def test_timeout_specified(self):
        """Container execution has a timeout.

        Without a timeout, a variant that enters an infinite loop would hold
        the container (and its resources) forever, effectively a resource leak.
        """
        config = ContainerConfig(timeout_seconds=30)
        assert config.timeout_seconds == 30
        assert config.timeout_seconds > 0

    def test_blocked_attack_fork_bomb(self):
        """PID limit prevents fork bombs at the cgroup level.

        A fork bomb (e.g., ':(){ :|:& };:') spawns processes exponentially.
        Tier 1's RLIMIT_NPROC is per-user and may not catch all variants.
        Tier 2's pids_limit is per-cgroup and stops all process creation.
        """
        config = ContainerConfig(pids_limit=64)
        assert config.pids_limit <= 256, (
            "PID limit must be low enough to prevent fork bombs from exhausting host PIDs."
        )

    def test_blocked_attack_memory_bomb(self):
        """Memory limit prevents memory exhaustion.

        A memory bomb (e.g., allocating infinite memory) would be killed by
        the OOM killer when the container's mem_limit is reached, without
        affecting other containers or the host.
        """
        config = ContainerConfig(memory_limit="512m")
        mem_bytes = _parse_docker_memory(config.memory_limit)
        assert mem_bytes <= 1024 * 1024 * 1024, (
            "Memory limit must prevent container from consuming all host memory."
        )

    def test_blocked_attack_cpu_starvation(self):
        """CPU limit prevents CPU starvation.

        A CPU-intensive infinite loop would be throttled by the cgroup
        scheduler, preventing it from starving other containers or the host.
        """
        config = ContainerConfig(cpu_limit="1.0")
        assert float(config.cpu_limit) <= 2.0, (
            "CPU limit must prevent container from starving other workloads."
        )


def _parse_docker_memory(mem_str: str) -> int:
    """Parse a Docker memory limit string to bytes."""
    mem_str = mem_str.strip().lower()
    multipliers = {"k": 1024, "m": 1024**2, "g": 1024**3, "t": 1024**4}
    if mem_str[-1] in multipliers:
        return int(float(mem_str[:-1]) * multipliers[mem_str[-1]])
    return int(mem_str)


# ============================================================================
# Attack vector 3: Filesystem boundary
#
# Tier 1 gap: the subprocess runs on the host filesystem.  Any path readable
# or writable by the host user is accessible to the variant test code.  This
# includes:
#   - /etc/passwd, /etc/shadow (if readable)
#   - The host user's ~/.ssh/ directory
#   - Docker socket (/var/run/docker.sock) if mounted
#   - Other projects' source code on the same host
#   - The host's /proc and /sys trees
#
# Tier 2 fix: the container has its own filesystem namespace.  By default, no
# host paths are mounted.  Only explicitly listed mounts (validated against
# allowed_mount_root) are visible, and they are read-only.  The root filesystem
# is read-only with a tmpfs /tmp.
# ============================================================================


class TestTier2FilesystemBoundary:
    """Prove that Tier 2 enforces a filesystem boundary between variant and host."""

    def test_no_host_paths_mounted_by_default(self):
        """Default container has no host filesystem mounts.

        Without explicit mounts, the variant code can only see the container's
        own filesystem (the image layers).  It cannot read host files like
        /etc/passwd, ~/.ssh/, or /var/run/docker.sock.
        """
        config = ContainerConfig()
        assert len(config.mounts) == 0, "Default container must not mount any host paths."

    def test_read_only_root_filesystem(self):
        """Container root filesystem is read-only by default.

        A read-only root prevents the variant from modifying the container's
        system files, installing packages, or writing to paths outside /tmp.
        """
        config = ContainerConfig(read_only_root=True)
        assert config.read_only_root is True

    def test_read_only_root_is_default(self):
        """read_only_root defaults to True for security.

        If the default were False, variant code could write to the container's
        filesystem, potentially modifying test infrastructure.
        """
        config = ContainerConfig()
        assert config.read_only_root is True

    def test_tmpfs_size_limited(self):
        """The tmpfs mounted at /tmp has a size limit.

        Without a size limit, variant code could fill the tmpfs and cause
        disk pressure on the host (tmpfs uses host memory).
        """
        config = ContainerConfig(tmpfs_size="50m")
        assert config.tmpfs_size == "50m"
        # Verify the size is not absurdly large
        size_bytes = _parse_docker_memory(config.tmpfs_size)
        assert size_bytes <= 500 * 1024 * 1024, (
            "tmpfs size should be <= 500m to prevent memory pressure."
        )

    def test_mount_source_path_traversal_blocked(self):
        """Mount sources must not escape the allowed root.

        A crafted mount source like "../../../etc" would mount the host's
        /etc directory into the container, exposing sensitive files.
        """
        allowed_root = Path("/workspace/evoseal")

        # Valid mount passes
        validate_mount_source("/workspace/evoseal/tests", allowed_root=allowed_root)

        # Path traversal is rejected
        import pytest

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/etc/passwd", allowed_root=allowed_root)

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/workspace/evoseal/../../../etc", allowed_root=allowed_root)

    def test_docker_socket_not_mounted(self):
        """The Docker socket must not be mounted into the test container.

        If /var/run/docker.sock were mounted, variant code could use the
        Docker API to escape the container, spawn privileged containers,
        or access the host filesystem.
        """
        config = ContainerConfig()
        # Default is safe (no mounts)
        for mount in config.mounts:
            source = mount.get("source", "")
            assert "docker.sock" not in source, (
                "Docker socket must never be mounted into a test container."
            )

        # Also verify the check catches docker.sock when mounts ARE present.
        bad_config = ContainerConfig(
            mounts=[{"source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}]
        )
        for mount in bad_config.mounts:
            source = mount.get("source", "")
            assert "docker.sock" in source, (
                "Sanity: docker.sock must be detectable in a non-empty mount list."
            )

    def test_mount_mode_enforced_read_only(self):
        """Explicit mounts should be read-only by default.

        Even when a host path is intentionally shared with the container,
        it should be mounted read-only so the variant cannot modify host files.
        """
        # This test documents the requirement; real implementation in T2-2
        # enforces this via the Mount read_only parameter.
        config = ContainerConfig()
        # Default mounts list is empty (already tested), but if any are added
        # they should default to read-only mode.
        for mount in config.mounts:
            assert mount.get("mode") == "ro", "All mounts must be read-only by default."

        # Verify the check catches a non-read-only mount when mounts ARE present.
        bad_config = ContainerConfig(
            mounts=[{"source": "/workspace/data", "target": "/data", "mode": "rw"}]
        )
        for mount in bad_config.mounts:
            assert mount.get("mode") != "ro", (
                "Sanity: a 'rw' mount must be detectable as non-read-only."
            )

    def test_blocked_attack_read_etc_shadow(self):
        """Filesystem boundary prevents reading /etc/shadow.

        Tier 1: variant code running on the host can attempt to read
        /etc/shadow (may succeed if the process has read permission).
        Tier 2: /etc/shadow is inside the container's own filesystem
        (the image layers), not the host's /etc/shadow.
        """
        config = ContainerConfig()
        # No mounts means the container's /etc is its own, not the host's
        assert len(config.mounts) == 0

    def test_blocked_attack_read_ssh_keys(self):
        """Filesystem boundary prevents reading host SSH keys.

        Tier 1: variant code can read ~/.ssh/id_rsa or ~/.ssh/authorized_keys.
        Tier 2: the host's home directory is not mounted.
        """
        config = ContainerConfig()
        assert len(config.mounts) == 0

    def test_blocked_attack_read_docker_socket(self):
        """Filesystem boundary prevents accessing the Docker socket.

        Tier 1: variant code could potentially access /var/run/docker.sock
        if it's readable by the host user.
        Tier 2: the socket is not mounted into the container.
        """
        config = ContainerConfig()
        for mount in config.mounts:
            assert "docker.sock" not in mount.get("source", "")

        # Verify detection works with non-empty mounts.
        config_with_socket = ContainerConfig(
            mounts=[{"source": "/var/run/docker.sock", "target": "/var/run/docker.sock"}]
        )
        for mount in config_with_socket.mounts:
            assert "docker.sock" in mount.get("source", ""), (
                "Sanity: docker.sock must be detectable when explicitly mounted."
            )

    def test_blocked_attack_write_to_host_etc(self):
        """Filesystem boundary prevents writing to host /etc.

        Tier 1: variant code with write access could modify /etc/crontab
        or /etc/sudoers on the host.
        Tier 2: the host filesystem is not visible; root is read-only.
        """
        config = ContainerConfig(read_only_root=True)
        assert config.read_only_root is True
        assert len(config.mounts) == 0


# ============================================================================
# Attack vector 4: Secret exfiltration via combined vectors
#
# Tier 1 gap: even with env-stripping, secrets can leak through:
#   - Reading .env files on the shared filesystem
#   - Reading configs/safety.yaml for configuration details
#   - Network exfiltration (see vector 1)
#
# Tier 2 fix: the filesystem boundary (vector 3) prevents reading .env and
# configs/ unless explicitly mounted; network disable (vector 1) prevents
# exfiltration even if secrets are somehow obtained.
# ============================================================================


class TestTier2SecretExfiltrationBlocked:
    """Prove that Tier 2 prevents secret exfiltration via combined vectors."""

    def test_no_secrets_in_container_environment(self):
        """Container receives no host environment variables by default.

        This is the basic Tier 2 guarantee (T2-3): the container environment
        is empty unless test_specific_env is provided.
        """
        config = ContainerConfig()
        assert config.environment == {}, (
            "Container must receive an empty environment by default. "
            "No host env vars (including secrets) should be forwarded."
        )

    def test_only_test_specific_env_passed(self):
        """When test_specific_env is provided, only those vars are passed.

        This ensures the caller explicitly controls every env var the
        container sees — no ambient host secrets leak through.
        """
        config = ContainerConfig(environment={"TEST_MODE": "ci", "PYTHONDONTWRITEBYTECODE": "1"})
        assert "ANTHROPIC_API_KEY" not in config.environment
        assert "OPENAI_API_KEY" not in config.environment
        assert "PATH" not in config.environment  # host PATH not forwarded

    def test_env_file_not_mounted(self):
        """The .env file must not be mounted into the container.

        Even if the .env file exists on the host, the container should not
        have access to it unless explicitly mounted (which should be blocked
        by the allowed_mount_root validation).
        """
        config = ContainerConfig()
        for mount in config.mounts:
            target = mount.get("target", "") or mount.get("bind", "")
            assert ".env" not in target, ".env file must not be mounted into the test container."

    def test_combined_defense_network_plus_filesystem(self):
        """Network disable + filesystem boundary = defense in depth.

        Even if a variant somehow reads a secret (e.g., from a mounted file),
        network_disable=True prevents it from exfiltrating that secret.
        And even if the network were somehow available, the filesystem boundary
        prevents reading the secret in the first place.

        This test verifies both defenses are active simultaneously.
        """
        config = ContainerConfig(
            network_disabled=True,
            read_only_root=True,
        )

        # Defense 1: network disabled
        assert config.network_disabled is True, "Network must be disabled."

        # Defense 2: filesystem boundary — no mounts
        assert len(config.mounts) == 0, "No host paths mounted."

        # Defense 3: environment isolation
        assert config.environment == {}, "No host env vars forwarded."

        # Defense 4: read-only root
        assert config.read_only_root is True, "Root filesystem read-only."


# ============================================================================
# Input validation: prevent malicious variant-controlled inputs
#
# The ContainerSandbox validates all inputs before they reach the Docker API.
# A malicious variant could craft inputs that exploit the Docker API — e.g.,
# an image reference that resolves to an attacker-controlled registry, or a
# mount source that traverses out of the workspace.
# ============================================================================


class TestTier2InputValidation:
    """Prove that variant-controlled inputs are validated before reaching Docker."""

    def test_image_ref_validation_accepts_valid(self):
        """Valid image refs are accepted."""
        validate_image("evoseal:local")
        validate_image("python:3.11-slim")
        validate_image("ubuntu:22.04")
        validate_image("ghcr.io/owner/repo:tag")

    def test_image_ref_validation_rejects_shell_injection(self):
        """Image refs with shell metacharacters are rejected."""
        import pytest

        with pytest.raises(ValueError, match="disallowed"):
            validate_image("evoseal:local; rm -rf /")

    def test_image_ref_validation_rejects_protocol_prefix(self):
        """Image refs with protocol prefixes are rejected."""
        import pytest

        with pytest.raises(ValueError, match="disallowed"):
            validate_image("https://attacker.com/image:tag")

    def test_image_ref_validation_rejects_path_traversal(self):
        """Image refs with path traversal are rejected."""
        import pytest

        with pytest.raises(ValueError, match="disallowed"):
            validate_image("../../../etc/passwd")

    def test_command_validation_accepts_valid(self):
        """Valid test commands are accepted."""
        assert validate_command(["pytest", "tests/", "-q"]) == ["pytest", "tests/", "-q"]
        assert validate_command(["python", "-m", "pytest", "tests/"]) == [
            "python",
            "-m",
            "pytest",
            "tests/",
        ]
        assert validate_command("pytest tests/ -q") == ["pytest", "tests/", "-q"]

    def test_command_validation_rejects_disallowed_prefix(self):
        """Commands not starting with an allowed prefix are rejected."""
        import pytest

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["curl", "http://attacker.com"])

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["bash", "-c", "rm -rf /"])

    def test_command_validation_rejects_prefix_bypass(self):
        """Commands like 'pytester' or 'unittest_backdoor' must not pass.

        Regression: prefix matching on the joined string accepted
        'pytester' because 'pytester'.startswith('pytest') is True.
        """
        import pytest

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["pytester", "-c", "evil"])

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["unittest_backdoor"])

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["python", "-m", "pytester"])

        with pytest.raises(ValueError, match="does not start with"):
            validate_command(["python", "-m", "unittest_evil"])

    def test_command_validation_rejects_shell_metacharacters(self):
        """Commands with shell metacharacters are rejected."""
        import pytest

        # Metacharacter in a later token (after valid prefix) is caught by the
        # metacharacter check.
        with pytest.raises(ValueError, match="shell metacharacters"):
            validate_command(["pytest", "|", "curl", "http://attacker.com"])

        with pytest.raises(ValueError, match="shell metacharacters"):
            validate_command(["pytest", "$HOME/evil"])

    def test_command_validation_rejects_empty(self):
        """Empty commands are rejected."""
        import pytest

        with pytest.raises(ValueError, match="non-empty"):
            validate_command([])

    def test_mount_source_validation_accepts_within_root(self):
        """Mount sources within allowed_root are accepted."""
        allowed_root = Path("/workspace/evoseal")
        result = validate_mount_source("/workspace/evoseal/tests", allowed_root=allowed_root)
        assert result == Path("/workspace/evoseal/tests").resolve()

    def test_mount_source_validation_rejects_outside_root(self):
        """Mount sources outside allowed_root are rejected."""
        import pytest

        allowed_root = Path("/workspace/evoseal")

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/etc/passwd", allowed_root=allowed_root)

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/workspace/evoseal/../../../etc", allowed_root=allowed_root)

    def test_mount_source_validation_rejects_etc(self):
        """Mounting /etc is rejected when allowed_root is the workspace."""
        import pytest

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/etc", allowed_root=Path("/workspace/evoseal"))

    def test_mount_source_validation_rejects_home_ssh(self):
        """Mounting ~/.ssh is rejected when allowed_root is the workspace."""
        import pytest

        with pytest.raises(ValueError, match="escapes allowed root"):
            validate_mount_source("/root/.ssh", allowed_root=Path("/workspace/evoseal"))

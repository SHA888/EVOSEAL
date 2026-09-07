"""Container-based sandbox for variant test execution (Tier 2, T2-2/T2-3/T2-4).

Spawns a fresh, network-disabled Docker container per variant test run.
Extracts only the pass/fail result and artifacts; tears down after.

Implements ADR 0006 — sibling container via host Docker socket.

No-host-secrets guarantee (T2-3):
    The spawned container **never** receives host secrets.  This is enforced
    at three levels, each stronger than Tier 1's env-stripping approach:

    1. **Environment isolation.**  The container is created with an explicit
       ``environment={}`` (or only caller-supplied test vars).  Unlike Tier 1,
       which copies ``os.environ`` and then *removes* known secret keys —
       leaving any undiscovered secrets in place — the container starts from
       an empty environment.  No host process environment is inherited.
    2. **Secret-file mount rejection.**  Mount sources whose path matches a
       known secret-file pattern (``.env``, ``*.key``, ``*.pem``, SSH keys,
       credential files, etc.) are rejected before reaching the Docker API.
       This prevents a caller from accidentally or deliberately leaking host
       credentials into the container filesystem.
    3. **Read-only root filesystem.**  When ``read_only_root=True`` (default),
       the container cannot write to its own filesystem — only ``/tmp`` (via
       tmpfs) is writable.  This prevents a compromised test from modifying
       the container image or planting persistent state.

Container-level resource caps (T2-4):
    CPU, memory, and PID limits are enforced by the container runtime (Docker
cgroups), **superseding** Tier 1's ``resource.setrlimit`` approach.  Tier 1
limits apply to a shared-host subprocess — they bound a child process but
share the host's PID/memory namespace, so a fork-bomb or memory hog can still
affect the host.  Container-level caps are enforced by the kernel's cgroup
subsystem on the *container* as a whole, providing stronger isolation:

    * ``cpu_limit`` — CPU quota via Docker's ``--cpus`` (cgroup cpu.max).
    * ``memory_limit`` — hard memory ceiling via Docker's ``--memory``
      (cgroup memory.max).  The container is OOM-killed if exceeded.
    * ``pids_limit`` — PID count limit via Docker's ``--pids-limit``
      (cgroup pids.max).  Prevents fork-bombs.

All resource limits are **validated at construction time** — invalid values
(negative, zero, unreasonably large, or malformed) raise ``ValueError``
immediately rather than failing silently or reaching the Docker API with
nonsensical parameters.

Usage::

    from evoseal.core.container_sandbox import ContainerSandbox

    sandbox = ContainerSandbox()
    result = sandbox.run_variant_test(
        command=["pytest", "tests/", "-q"],
        mounts={"/host/path": {"bind": "/app", "mode": "ro"}},
    )
    print(result.exit_code, result.stdout)
"""

from __future__ import annotations

import logging
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Docker SDK import
# ---------------------------------------------------------------------------
try:
    import docker
    from docker.errors import APIError, ContainerError, ImageNotFound, NotFound

    DOCKER_AVAILABLE = True
except ImportError:
    DOCKER_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Image refs must match this pattern to be accepted.
# Allows: evoseal:local, evoseal:latest, python:3.11-slim, ubuntu:22.04, etc.
# Blocks: anything with shell metacharacters, protocol prefixes, or path traversal.
_SAFE_IMAGE_RE = re.compile(
    r"^[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)*(/[a-zA-Z0-9_\-]+(\.[a-zA-Z0-9_\-]+)*)*(:[a-zA-Z0-9_.\-]+)?$"
)

# Test commands are validated against this allowlist of prefixes.
# The command must start with one of these tokens.
_ALLOWED_CMD_PREFIXES: tuple[str, ...] = (
    "pytest",
    "python -m pytest",
    "unittest",
    "python -m unittest",
)

# Default resource limits (overridable via config or constructor args).
DEFAULT_CPU_LIMIT = "1.0"  # number of CPUs
DEFAULT_MEMORY_LIMIT = "512m"
DEFAULT_PIDS_LIMIT = 256
DEFAULT_TIMEOUT_SECONDS = 300
DEFAULT_TMPFS_SIZE = "100m"

# Resource limit boundaries — validated at construction time (T2-4).
# These are intentionally generous; the goal is to catch misconfiguration,
# not to enforce a specific policy.
MIN_CPU_LIMIT = 0.01  # 10 millicpus — below this is likely a mistake
MAX_CPU_LIMIT = 128.0  # 128 CPUs — above this is likely a mistake
MIN_MEMORY_BYTES = 1048576  # 1 MiB — below this is unusable
MAX_MEMORY_BYTES = 1 << 40  # 1 TiB — above this is likely a mistake
MIN_PIDS_LIMIT = 1  # at least 1 process
MAX_PIDS_LIMIT = 4194304  # Linux default pid_max
MIN_TIMEOUT_SECONDS = 1  # at least 1 second
MAX_TIMEOUT_SECONDS = 86400  # 24 hours — above this is likely a mistake

# ---------------------------------------------------------------------------
# Secret-file patterns (T2-3)
# ---------------------------------------------------------------------------
# Filenames or suffixes that indicate a secret/credential file.  Mount sources
# whose resolved path's *name* matches any of these are rejected.  Patterns
# are matched case-insensitively against the final path component only.
#
# This list is intentionally conservative — it blocks common secret files
# even if the caller's allowed_mount_root would otherwise permit them.
_SECRET_FILE_NAMES: frozenset[str] = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        ".env.staging",
        "id_rsa",
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "shadow",
        "gshadow",
        "htpasswd",
        ".netrc",
        ".npmrc",
        ".pypirc",
        ".dockerconfigjson",
        "credentials",
        "service-account.json",
    }
)

_SECRET_FILE_SUFFIXES: tuple[str, ...] = (
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
)

_SECRET_FILE_PREFIXES: tuple[str, ...] = (
    ".env.",  # catches .env.dev, .env.test, etc.
)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------
@dataclass
class ContainerTestResult:
    """Result of a single variant test execution inside a container."""

    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool = False
    error: str | None = None
    duration_seconds: float = 0.0
    container_id: str | None = None


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_image(image: str) -> None:
    """Reject image refs that could inject arbitrary Docker API parameters.

    Raises ValueError on invalid input.
    """
    if not image or not isinstance(image, str):
        raise ValueError(f"Image ref must be a non-empty string, got {image!r}")
    if not _SAFE_IMAGE_RE.match(image):
        raise ValueError(
            f"Image ref contains disallowed characters: {image!r}. "
            f"Must match {_SAFE_IMAGE_RE.pattern}"
        )


def _validate_command(command: list[str] | str) -> list[str]:
    """Validate and normalise a test command.

    The command must start with a known test-runner prefix.  Returns the
    command as a list of tokens (``shlex.split``-style).

    Raises ValueError on invalid input.
    """
    if isinstance(command, str):
        import shlex

        command = shlex.split(command)

    if not command:
        raise ValueError("Command must be non-empty")

    cmd_str = " ".join(command)
    if not any(cmd_str.startswith(prefix) for prefix in _ALLOWED_CMD_PREFIXES):
        raise ValueError(
            f"Command {cmd_str!r} does not start with an allowed prefix. "
            f"Allowed prefixes: {_ALLOWED_CMD_PREFIXES}"
        )

    # Reject shell metacharacters in individual tokens
    for token in command:
        if any(c in token for c in (";", "|", "&", "$", "`", "(", ")", "{", "}", ">", "<")):
            raise ValueError(f"Command token contains shell metacharacters: {token!r}")

    return command


def _is_secret_file(path: Path) -> bool:
    """Check whether *path* looks like a secret/credential file.

    Matches the final path component against :data:`_SECRET_FILE_NAMES`,
    :data:`_SECRET_FILE_SUFFIXES`, and :data:`_SECRET_FILE_PREFIXES`.
    """
    name = path.name.lower()
    if name in _SECRET_FILE_NAMES:
        return True
    if any(name.endswith(sfx) for sfx in _SECRET_FILE_SUFFIXES):
        return True
    if any(name.startswith(pfx) for pfx in _SECRET_FILE_PREFIXES):
        return True
    return False


def _validate_mount_source(
    source: str,
    allowed_root: Path | None = None,
    *,
    reject_secrets: bool = True,
) -> Path:
    """Validate a mount source path.

    Checks:

    1. The resolved path stays within *allowed_root* (if set).
    2. The path does not point to a known secret file (T2-3), unless
       *reject_secrets* is explicitly ``False``.

    Raises ValueError on invalid, escaping, or secret-file paths.
    """
    path = Path(source).resolve()
    if allowed_root is not None:
        try:
            path.relative_to(allowed_root.resolve())
        except ValueError:
            raise ValueError(
                f"Mount source {source!r} escapes allowed root {allowed_root!r}"
            ) from None
    if reject_secrets and _is_secret_file(path):
        raise ValueError(
            f"Mount source {source!r} is a secret/credential file and must "
            f"not be mounted into the container (T2-3 no-host-secrets guarantee). "
            f"Matched name: {path.name!r}"
        )
    return path


def _parse_memory_bytes(memory_limit: str) -> int:
    """Parse a Docker-format memory string to bytes.

    Supported suffixes (case-insensitive):
    * ``k`` / ``kb`` — kibibytes (×1024)
    * ``m`` / ``mb`` — mebibytes (×1024²)
    * ``g`` / ``gb`` — gibibytes (×1024³)
    * ``t`` / ``tb`` — tebibytes (×1024⁴)
    * no suffix — bytes

    Raises ValueError on malformed input.
    """
    if not memory_limit or not isinstance(memory_limit, str):
        raise ValueError(f"Memory limit must be a non-empty string, got {memory_limit!r}")
    s = memory_limit.strip().lower()
    multiplier = 1
    for suffix, mult in [
        ("tb", 1024**4),
        ("gb", 1024**3),
        ("mb", 1024**2),
        ("kb", 1024),
        ("t", 1024**4),
        ("g", 1024**3),
        ("m", 1024**2),
        ("k", 1024),
    ]:
        if s.endswith(suffix):
            s = s[: -len(suffix)]
            multiplier = mult
            break
    try:
        value = float(s)
    except ValueError:
        raise ValueError(f"Malformed memory limit: {memory_limit!r}") from None
    if value <= 0:
        raise ValueError(f"Memory limit must be positive, got {memory_limit!r}")
    return int(value * multiplier)


def _validate_cpu_limit(cpu_limit: str) -> None:
    """Validate a CPU limit string.

    The value must be a positive number between :data:`MIN_CPU_LIMIT` and
    :data:`MAX_CPU_LIMIT`.  Raises ``ValueError`` on invalid input.
    """
    if not cpu_limit or not isinstance(cpu_limit, str):
        raise ValueError(f"CPU limit must be a non-empty string, got {cpu_limit!r}")
    try:
        value = float(cpu_limit)
    except ValueError:
        raise ValueError(f"Malformed CPU limit: {cpu_limit!r}") from None
    if value < MIN_CPU_LIMIT:
        raise ValueError(
            f"CPU limit {cpu_limit!r} is below minimum ({MIN_CPU_LIMIT}). "
            f"This is likely a misconfiguration."
        )
    if value > MAX_CPU_LIMIT:
        raise ValueError(
            f"CPU limit {cpu_limit!r} exceeds maximum ({MAX_CPU_LIMIT}). "
            f"This is likely a misconfiguration."
        )


def _validate_memory_limit(memory_limit: str) -> None:
    """Validate a Docker-format memory limit string.

    The value must parse to between :data:`MIN_MEMORY_BYTES` and
    :data:`MAX_MEMORY_BYTES`.  Raises ``ValueError`` on invalid input.
    """
    bytes_val = _parse_memory_bytes(memory_limit)
    if bytes_val < MIN_MEMORY_BYTES:
        raise ValueError(
            f"Memory limit {memory_limit!r} ({bytes_val} bytes) is below minimum "
            f"({MIN_MEMORY_BYTES} bytes = 1 MiB). This is likely a misconfiguration."
        )
    if bytes_val > MAX_MEMORY_BYTES:
        raise ValueError(
            f"Memory limit {memory_limit!r} ({bytes_val} bytes) exceeds maximum "
            f"({MAX_MEMORY_BYTES} bytes = 1 TiB). This is likely a misconfiguration."
        )


def _validate_pids_limit(pids_limit: int) -> None:
    """Validate a PID limit.

    The value must be an integer between :data:`MIN_PIDS_LIMIT` and
    :data:`MAX_PIDS_LIMIT`.  Raises ``ValueError`` on invalid input.
    """
    if not isinstance(pids_limit, int) or isinstance(pids_limit, bool):
        raise ValueError(f"PID limit must be an integer, got {pids_limit!r}")
    if pids_limit < MIN_PIDS_LIMIT:
        raise ValueError(
            f"PID limit {pids_limit} is below minimum ({MIN_PIDS_LIMIT}). "
            f"This is likely a misconfiguration."
        )
    if pids_limit > MAX_PIDS_LIMIT:
        raise ValueError(
            f"PID limit {pids_limit} exceeds maximum ({MAX_PIDS_LIMIT}). "
            f"This is likely a misconfiguration."
        )


def _validate_timeout(timeout: int) -> None:
    """Validate a timeout in seconds.

    The value must be an integer between :data:`MIN_TIMEOUT_SECONDS` and
    :data:`MAX_TIMEOUT_SECONDS`.  Raises ``ValueError`` on invalid input.
    """
    if not isinstance(timeout, int) or isinstance(timeout, bool):
        raise ValueError(f"Timeout must be an integer, got {timeout!r}")
    if timeout < MIN_TIMEOUT_SECONDS:
        raise ValueError(
            f"Timeout {timeout}s is below minimum ({MIN_TIMEOUT_SECONDS}s). "
            f"This is likely a misconfiguration."
        )
    if timeout > MAX_TIMEOUT_SECONDS:
        raise ValueError(
            f"Timeout {timeout}s exceeds maximum ({MAX_TIMEOUT_SECONDS}s = 24h). "
            f"This is likely a misconfiguration."
        )


def _nano_cpus(cpu_limit: str) -> int:
    """Convert a CPU limit string (e.g. ``'1.0'``, ``'0.5'``) to nanocpus."""
    return int(float(cpu_limit) * 1e9)


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class ContainerSandbox:
    """Spawn a fresh, isolated Docker container for each variant test run.

    Implements ADR 0006 (sibling container via host Docker socket).
    Each invocation of :meth:`run_variant_test` creates a new container with:

    * ``network_disabled=True``
    * No host environment variables or secrets
    * Configurable CPU / memory / PID limits
    * Read-only root filesystem with a tmpfs ``/tmp``
    * Automatic cleanup after execution

    Parameters
    ----------
    image:
        Docker image to use for the spawned container.
    cpu_limit:
        Number of CPUs (string, e.g. ``"1.0"``).
    memory_limit:
        Memory cap (Docker format, e.g. ``"512m"``).
    pids_limit:
        Maximum number of processes inside the container.
    timeout_seconds:
        Per-variant execution timeout.
    read_only_root:
        Mount the container root filesystem read-only.
    tmpfs_size:
        Size of the ``/tmp`` tmpfs when ``read_only_root`` is enabled.
    allowed_mount_root:
        If set, mount sources are constrained to be under this directory.
    """

    def __init__(
        self,
        image: str = "evoseal:local",
        cpu_limit: str = DEFAULT_CPU_LIMIT,
        memory_limit: str = DEFAULT_MEMORY_LIMIT,
        pids_limit: int = DEFAULT_PIDS_LIMIT,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        read_only_root: bool = True,
        tmpfs_size: str = DEFAULT_TMPFS_SIZE,
        allowed_mount_root: str | Path | None = None,
    ) -> None:
        if not DOCKER_AVAILABLE:
            raise RuntimeError(
                "The 'docker' Python package is required for ContainerSandbox. "
                "Install it with: pip install docker"
            )

        _validate_image(image)
        _validate_cpu_limit(cpu_limit)
        _validate_memory_limit(memory_limit)
        _validate_pids_limit(pids_limit)
        _validate_timeout(timeout_seconds)

        self.image = image
        self.cpu_limit = cpu_limit
        self.memory_limit = memory_limit
        self.pids_limit = pids_limit
        self.timeout_seconds = timeout_seconds
        self.read_only_root = read_only_root
        self.tmpfs_size = tmpfs_size
        self.allowed_mount_root = Path(allowed_mount_root).resolve() if allowed_mount_root else None

        self._client: docker.DockerClient | None = None

    # ------------------------------------------------------------------
    # Docker client lifecycle
    # ------------------------------------------------------------------

    def _get_client(self) -> docker.DockerClient:
        """Return (and lazily create) the Docker client."""
        if self._client is None:
            self._client = docker.from_env()
        return self._client

    def close(self) -> None:
        """Close the underlying Docker client."""
        if self._client is not None:
            self._client.close()
            self._client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_variant_test(
        self,
        command: list[str] | str,
        mounts: dict[str, dict[str, str]] | None = None,
        working_dir: str = "/app",
        test_specific_env: dict[str, str] | None = None,
    ) -> ContainerTestResult:
        """Execute a test command inside an isolated container.

        Parameters
        ----------
        command:
            Test command to run (must start with an allowed prefix).
        mounts:
            Volume mounts, mapping host paths to container bind configs,
            e.g. ``{"/host/path": {"bind": "/app", "mode": "ro"}}``.
            Host paths are validated against ``allowed_mount_root``.
        working_dir:
            Working directory inside the container.
        test_specific_env:
            Optional environment variables specific to this test run
            (e.g. ``{"TEST_MODULE": "test_foo.py"}``).  These are the
            *only* env vars the container sees — host secrets are never
            forwarded.

        Returns
        -------
        ContainerTestResult
            Exit code, stdout/stderr, timing, and error info.
        """
        # --- validate inputs ---
        cmd = _validate_command(command)

        validated_mounts: dict[str, dict[str, str]] = {}
        if mounts:
            for host_path, bind_cfg in mounts.items():
                # T2-3: reject secret files AND enforce allowed_root
                _validate_mount_source(host_path, self.allowed_mount_root)
                validated_mounts[host_path] = bind_cfg

        # T2-3: environment isolation — the container receives ONLY the
        # caller-supplied test_specific_env, never os.environ.  This is
        # stronger than Tier 1's env-stripping (which copies os.environ
        # then removes known keys, leaving unknown secrets in place).
        env = test_specific_env or {}

        # --- build container kwargs ---
        client = self._get_client()

        # Convert mounts to docker.types.Mount objects for cleaner API usage
        docker_mounts: list[Any] = []
        for host_path, bind_cfg in validated_mounts.items():
            from docker.types import Mount

            docker_mounts.append(
                Mount(
                    target=bind_cfg.get("bind", "/app"),
                    source=str(Path(host_path).resolve()),
                    type="bind",
                    read_only=bind_cfg.get("mode", "ro") == "ro",
                )
            )

        container = None
        start_time = time.monotonic()

        try:
            container = client.containers.run(
                image=self.image,
                command=cmd,
                detach=True,
                network_disabled=True,
                # Resource caps (T2-4)
                nano_cpus=_nano_cpus(self.cpu_limit),
                mem_limit=self.memory_limit,
                pids_limit=self.pids_limit,
                # No host secrets (T2-3) — only test_specific_env is passed
                environment=env,
                # Read-only root with tmpfs for /tmp
                read_only=self.read_only_root,
                tmpfs={"/tmp": f"size={self.tmpfs_size}"} if self.read_only_root else None,
                # Mounts
                mounts=docker_mounts if docker_mounts else None,
                working_dir=working_dir,
                # Security: run as non-root (same as evoseal:local image user)
                # The evoseal:local image already sets USER evoseal,
                # but explicitly not passing privileged or cap_add.
            )

            logger.info("Started container %s for test execution", container.short_id)

            # Wait for completion with timeout
            try:
                wait_result = container.wait(timeout=self.timeout_seconds)
                exit_code = wait_result.get("StatusCode", -1)
                timed_out = False
            except APIError:
                # Docker API error during wait — not a timeout
                raise
            except Exception:
                # Timeout or connection error — kill the container
                logger.warning(
                    "Container %s timed out after %ds, killing",
                    container.short_id,
                    self.timeout_seconds,
                )
                container.kill()
                exit_code = -1
                timed_out = True

            # Capture logs (stdout + stderr merged, same as docker logs)
            try:
                logs_bytes = container.logs(stdout=True, stderr=True, timestamps=False)
                logs = logs_bytes.decode("utf-8", errors="replace")
            except Exception:
                logs = ""

            # Separate stdout/stderr isn't possible with merged logs,
            # so put everything in stdout and leave stderr empty.
            duration = time.monotonic() - start_time

            return ContainerTestResult(
                exit_code=exit_code,
                stdout=logs,
                stderr="",
                timed_out=timed_out,
                duration_seconds=duration,
                container_id=container.short_id,
            )

        except (ContainerError, ImageNotFound) as exc:
            duration = time.monotonic() - start_time
            return ContainerTestResult(
                exit_code=getattr(exc, "exit_status", -1),
                stdout="",
                stderr=str(exc),
                error=str(exc),
                duration_seconds=duration,
            )

        except APIError as exc:
            duration = time.monotonic() - start_time
            return ContainerTestResult(
                exit_code=-1,
                stdout="",
                stderr="",
                error=f"Docker API error: {exc}",
                duration_seconds=duration,
            )

        finally:
            # Always clean up the container (T2-2: "tear down after")
            if container is not None:
                try:
                    container.remove(force=True)
                    logger.debug("Removed container %s", container.short_id)
                except Exception:
                    logger.warning(
                        "Failed to remove container %s", container.short_id, exc_info=True
                    )

    # ------------------------------------------------------------------
    # Convenience constructor from config dict
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> ContainerSandbox:
        """Create a :class:`ContainerSandbox` from a config dictionary.

        Expected keys (all optional, with defaults)::

            {
                "image": "evoseal:local",
                "cpu_limit": "1.0",
                "memory_limit": "512m",
                "pids_limit": 256,
                "timeout_seconds": 300,
                "read_only_root": true,
                "tmpfs_size": "100m",
                "allowed_mount_root": "/path/to/workspace",
            }

        All resource-limit values are validated (T2-4).  Invalid values
        raise ``ValueError`` immediately rather than being passed silently
        to the Docker API.
        """
        return cls(
            image=config.get("image", "evoseal:local"),
            cpu_limit=config.get("cpu_limit", DEFAULT_CPU_LIMIT),
            memory_limit=config.get("memory_limit", DEFAULT_MEMORY_LIMIT),
            pids_limit=config.get("pids_limit", DEFAULT_PIDS_LIMIT),
            timeout_seconds=config.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
            read_only_root=config.get("read_only_root", True),
            tmpfs_size=config.get("tmpfs_size", DEFAULT_TMPFS_SIZE),
            allowed_mount_root=config.get("allowed_mount_root"),
        )

# ADR 0006 — Container execution mechanism for Tier 2 isolation

**Status:** Proposed
**Date:** 2026-09-03
**Deciders:** Project lead
**Depends on:** [ADR 0001](0001-isolation-strategy.md) (isolation strategy; Tier 2 trigger #1 fired 2026-09-03)
**Drives:** T2-2 through T2-7 (implementation tasks in `TODO.md`)

---

## 1. Context

ADR 0001 established a tiered isolation model. Tier 1 (edit-scope allowlist, env-stripping,
resource limits via `preexec_fn`) is implemented and default-on. Tier 2 — per-variant
container isolation — was deferred behind explicit triggers. Trigger #1 ("untrusted or
adversarial generation — running an unvetted/local model") fired 2026-09-03 because the
generator now defaults to a local Ollama provider and prefers EVOSEAL's own self-fine-tuned
model over a trusted external API.

Tier 2 requires spawning a fresh, network-disabled, resource-capped container for each
variant test execution. The question is **how** to spawn that container given that EVOSEAL
already runs inside its own Docker container (`docker-compose.evoseal.yml`, image
`evoseal:local`, non-root `evoseal` user, Python 3.11-slim base).

---

## 2. Decision drivers

1. **EVOSEAL is already containerized.** The spawn mechanism must work from *inside* a
   running Docker container, not from a bare host. This eliminates approaches that assume
   direct host access.
2. **Minimal operational overhead.** EVOSEAL is a research-stage, single-operator project.
   The mechanism should be simple to set up and maintain — no Kubernetes, no custom OCI
   runtimes, no kernel-level configuration.
3. **Strong isolation guarantees.** The spawned container must: (a) have no network access,
   (b) receive no host secrets, (c) be resource-capped (CPU, memory, PIDs), and (d) be
   torn down after execution. These are the T2-2 through T2-4 requirements.
4. **Compatibility with existing test runner.** The mechanism must integrate with
   `evoseal/core/testrunner.py`'s `sandbox_enabled` code path (Tier 1, task 2.14). Tier 2
   replaces the `preexec_fn`-based resource limits with container-level enforcement.
5. **Reproducibility.** The same mechanism should work on a developer laptop, a CI runner,
   and a single-server deployment.

---

## 3. Options considered

### Option A — Sibling container via host Docker socket (CHOSEN)

Mount the host's Docker socket (`/var/run/docker.sock`) into the EVOSEAL container. Use the
Docker SDK for Python (`docker` package) to spawn sibling containers from inside EVOSEAL.

**How it works:**

1. EVOSEAL's `docker-compose.evoseal.yml` adds a volume mount:
   `/var/run/docker.sock:/var/run/docker.sock`.
2. The `docker` Python package is added as a dependency.
3. A new `ContainerSandbox` class (T2-2) uses `docker.containers.run()` to spawn a
   lightweight container (same `evoseal:local` image or a minimal test-runner image) with:
   - `network_disabled=True`
   - `--cpus`, `--memory`, `--pids-limit` set (T2-4)
   - No `--env-file`, no `.env` mount, no secrets passed (T2-3)
   - The variant's test code and dependencies mounted read-only
4. The container runs the test command, writes results to a mounted output volume, and exits.
5. `ContainerSandbox` reads the exit code and output, then removes the container.

**Pros:**

- **Simple and well-understood.** Docker socket mounting is the standard pattern for
  CI-in-Docker, Docker-in-Docker (dind), and tooling that spawns containers from containers.
  Extensively documented, widely used.
- **Full Docker API access.** Supports all isolation primitives needed (network disable,
  resource caps, secret exclusion, tmpfs mounts, read-only rootfs).
- **No kernel configuration.** Works out of the box on any Linux host with Docker installed.
  No user namespaces, no AppArmor profiles, no custom runtimes.
- **Same image reuse.** The spawned container can reuse `evoseal:local` (already built) or
  a stripped-down test-runner variant — no new base image needed for T2-2.
- **Python SDK is mature.** The `docker` Python package provides a clean API for container
  lifecycle management, log streaming, and wait/inspect.

**Cons:**

- **Docker socket is a privileged surface.** Mounting `/var/run/docker.sock` gives the
  EVOSEAL container root-equivalent access to the host's Docker daemon. A compromised
  EVOSEAL process could spawn arbitrary containers on the host, mount host paths, or
  escape the container boundary. **Mitigation:** this is acceptable because (a) EVOSEAL
  already runs as a single-operator research project on a dedicated host, (b) the socket
  mount is an explicit opt-in in `docker-compose.evoseal.yml`, and (c) the threat model
  (ADR 0001 §5) already scopes "multi-tenant host" as a separate trigger (#2) that would
  require a different architecture entirely.
- **Docker daemon must be available.** Not present in all environments (e.g., rootless
  Podman, some CI runners). **Mitigation:** EVOSEAL's target environment is a Docker-based
  single-server deployment; the `docker-compose.evoseal.yml` file already assumes Docker.
- **Sibling container lifecycle management.** Crashed or leaked containers must be cleaned
  up. **Mitigation:** `ContainerSandbox` uses `remove=True` on container exit and a
  cleanup sweep for any containers older than a configurable timeout.

### Option B — Rootless nested runtime (e.g., Podman in container, sysbox)

Use a rootless container runtime *inside* the EVOSEAL container to spawn isolated
environments without needing the host Docker socket.

**How it works:**

1. Install Podman (or use the `sysbox` runtime) inside the EVOSEAL container image.
2. Configure rootless Podman with user namespaces so the `evoseal` user can create
   containers without Docker daemon access.
3. Spawn containers via `podman run` with the same isolation flags (no network, resource
   caps, no secrets).

**Pros:**

- **No privileged socket mount.** The EVOSEAL container does not need access to the host
  Docker daemon. Stronger isolation boundary — a compromised EVOSEAL process cannot
  control the host's Docker daemon.
- **Rootless by default.** Podman's rootless mode uses user namespaces, providing an
  additional layer of containment.

**Cons:**

- **Significantly higher complexity.** Rootless Podman inside a Docker container requires
  specific kernel support (user namespaces enabled, `fuse-overlayfs` or kernel 5.11+
  overlayfs-in-userns), custom storage configuration, and potentially `sysbox` (a custom
  OCI runtime) or `--privileged` on the outer container — which defeats the purpose.
  Getting this working reliably across host kernels is non-trivial.
- **Image bloat.** Adding Podman + dependencies to the `python:3.11-slim` base image adds
  ~150-200 MB and increases build time.
- **Limited testing in this context.** Running Podman inside Docker is a known-painful
  edge case. The `sysbox` runtime (which makes this seamless) requires a custom runtime
  installed on the *host*, adding operational burden.
- **Over-built for the threat model.** The socket-mount security concern (Option A's main
  con) is about a compromised EVOSEAL process attacking the host — but ADR 0001's trigger
  #1 is about *untrusted generation*, not a fully compromised host process. The generation
  code runs *inside* EVOSEAL's Python process; the Docker socket is not directly exposed
  to generated code. The additional isolation of rootless Podman addresses a threat
  (host-level compromise) that is beyond Tier 2's scope.

### Option C — Lightweight process sandbox (bubblewrap/firejail)

Use `bubblewrap` (`bwrap`) or `firejail` to create a sandboxed process namespace for each
test execution, without spawning a full container.

**Pros:**

- **Very low overhead.** No container image, no daemon, no Docker dependency. Process
  spawn in milliseconds.
- **Fine-grained filesystem control.** Bind-mount specific paths read-only, create tmpfs
  overlays, restrict network namespaces.

**Cons:**

- **Requires host-level tools.** `bubblewrap` and `firejail` must be installed in the
  container image and may require specific kernel capabilities (`user_namespaces`,
  `seccomp`).
- **Not a container.** Does not provide the same level of resource isolation (cgroups v2
  integration is partial). PID/mem/CPU limits require separate `cgroup` setup.
- **Platform-specific.** Linux-only, with varying behavior across kernel versions.
- **Harder to reason about.** Less standardized than Docker containers for the isolation
  guarantees T2-3 and T2-4 require.

---

## 4. Decision

**Adopt Option A — sibling container via host Docker socket.**

The Docker socket mount is the simplest mechanism that provides all required isolation
primitives (network disable, resource caps, secret exclusion, lifecycle management) with
minimal operational overhead. The security trade-off (privileged socket surface) is
acceptable given EVOSEAL's single-operator, single-host, research-stage deployment model.

### Implementation outline (for T2-2 through T2-5)

1. **T2-2 — `ContainerSandbox` class.** New module `evoseal/core/container_sandbox.py`.
   Uses `docker.from_env()` to connect to the host Docker daemon. Method
   `run_variant_test(image, command, mounts, resource_limits)` spawns a container, waits
   for completion, captures stdout/stderr and exit code, removes the container. Timeout
   handling via `container.wait(timeout=...)` + `container.kill()`.

2. **T2-3 — No-host-secrets guarantee.** The spawned container is created with:
   - No `env_file` or environment variables from the host (explicit empty `environment={}`
     or only test-specific vars).
   - No `.env` mount.
   - A minimal or the existing `evoseal:local` image (which already runs as non-root).
   - Optionally, `read_only=True` on the root filesystem with a tmpfs for `/tmp`.

3. **T2-4 — Resource caps.** Pass to `docker.containers.run()`:
   - `nano_cpus` (CPU limit in nanocpus, e.g., `1e9` for 1 CPU).
   - `mem_limit` (memory limit, e.g., `"512m"`).
   - `pids_limit` (PID limit, e.g., `256`).
   These supersede Tier 1's `resource.setrlimit` for the container boundary.

4. **T2-5 — Wire into test runner.** Modify `SandboxedTestRunner` (`testrunner.py`) to
   use `ContainerSandbox` when `sandbox_enabled=True` and Docker is available. Fall back
   to the existing `preexec_fn` mechanism when Docker is not available (e.g., local
   development without Docker socket). This preserves backward compatibility.

### Configuration

Add to `configs/safety.yaml` under a new `container_sandbox` section:

```yaml
container_sandbox:
  enabled: true
  image: "evoseal:local"          # image for spawned test containers
  network_disabled: true
  cpu_limit: "1.0"                # number of CPUs
  memory_limit: "512m"            # memory cap
  pids_limit: 256                 # max processes
  timeout_seconds: 300            # per-variant test timeout
  read_only_root: true            # read-only rootfs
  tmpfs_size: "100m"              # /tmp tmpfs size
```

### docker-compose change

```yaml
# docker-compose.evoseal.yml — add to volumes:
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
```

---

## 5. Consequences

- **Positive:** Closes all Tier 2 isolation requirements (T2-2 through T2-4) with a single,
  well-understood mechanism. Integrates cleanly with the existing test runner. No new
  infrastructure or kernel configuration required.
- **Negative:** The Docker socket mount is a privileged surface. Documented as an explicit
  opt-in with a security note in `docker-compose.evoseal.yml`. If EVOSEAL ever moves to a
  multi-tenant or untrusted-host model (trigger #2), this mechanism must be replaced with
  Option B or a Kubernetes-based approach.
- **Neutral:** The `docker` Python package becomes a dependency. It is already widely used
  in the Python ecosystem and adds minimal overhead. Make it an optional dependency
  (`extras_require`) so EVOSEAL still works without Docker for local development.

---

## 6. Follow-on tasks

This ADR drives the following `TODO.md` items:

- **T2-2** — Implement `ContainerSandbox` class per the outline above.
- **T2-3** — Verify no-host-secrets guarantee (no env vars, no `.env` mount, read-only root).
- **T2-4** — Implement container-level resource caps.
- **T2-5** — Wire `ContainerSandbox` into `SandboxedTestRunner` as the default when Docker
  is available.
- **T2-6** — Extend adversarial safety tests for Tier 2 (network exfiltration, resource
  exhaustion, filesystem boundary).
- **T2-7** — Update ADR 0001 "Current state" and operator guidance.

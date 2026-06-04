# EVOSEAL Threat Model

**Status:** Research-stage. This document describes the *actual* safety posture of
the self-modification loop as implemented today — not an aspirational one. Where a
protection is missing, this document says so plainly. False confidence in a
self-modifying system is more dangerous than a documented gap.

**Last reviewed:** 2026-06-05
**Scope:** The autonomous evolution loop (`EvolutionPipeline`) and its safety layer
(`evoseal/core/safety_integration.py`, `rollback_manager.py`, `regression_detector.py`,
`improvement_validator.py`, `checkpoint_manager.py`).
**Feeds:** Plans.md task 2.2 (sandbox isolation vs rollback decision), 2.4 (adversarial
tests), 2.11 (`evoseal doctor` critical-failure definitions).

---

## 1. What this system is, from a security standpoint

EVOSEAL is an agent that **generates code, evaluates it, and applies the winning
variant back to its own codebase** — then repeats. The defining property is that the
artifact under modification is the same system performing the modification. The threat
model therefore has two distinct concerns:

1. **Correctness containment** — a *well-intentioned but wrong* edit must not degrade or
   corrupt the system. This is what the current safety layer is built for, and it is
   largely effective.
2. **Execution containment** — a *malformed, adversarial, or runaway* generated artifact
   must not damage the host, exfiltrate data, or consume unbounded resources. This is
   **largely unaddressed today** and is the primary open risk.

The rest of this document answers the five required questions, then summarizes the
posture and the open gaps.

---

## 2. Assets and trust boundaries

| Asset | Why it matters | Current protection |
|-------|----------------|--------------------|
| The EVOSEAL source tree (`evoseal/`) | The system edits this to improve itself; corruption is self-destruction | Checkpoint + rollback (strong); forward-edit path restriction (**none**) |
| Git repository state (`.git/`) | History and recoverability | Preserved during rollback (strong) |
| Safety configuration (`configs/safety.yaml`, code defaults) | Defines the thresholds that gate every edit | No integrity guard against the loop editing it (**gap**) |
| The host environment (filesystem, network, processes) | Generated code executes here | **No sandbox** — subprocess inherits full environment |
| Secrets (`.env`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) | API credentials | Gitignored; **readable by any generated code that runs** |

**Trust boundary, as built:** there is effectively **one trust zone**. Generated code
runs as a subprocess of the main process, inheriting its environment, network access,
filesystem permissions, and secrets. The only hardened boundary is *rollback target
selection* (Section 5), not *code execution*.

---

## 3. Required Question (1): What edits can the DGM loop make? (Scope of "immutable-core")

**Verdict: UNPROTECTED at edit-application time.**

There is **no path allowlist or denylist** restricting which files a generated variant
may modify. Searches for `immutable`, `protected`, `allowlist`, `denylist`, and
`EVOSEAL_`-prefixed path guards return no enforcement at the point where edits are
applied to disk.

What *does* exist:

- **`improvement_validator.py`** gates edits on *outcome* (success-rate stable, no new
  failures, performance not regressed, min score 70/100 with statistical significance) —
  it judges whether an edit is *good*, not whether it touched a *forbidden file*.
- **`checkpoint_manager.py`** defines a `protected_dirs` set — `.git`, `.evoseal`,
  `__pycache__`, `.pytest_cache`, `node_modules` — but this list is consulted **only
  during rollback/restoration** to avoid clobbering them, **not** during forward edit
  application.

**Consequence:** A generated variant can, in principle, modify any file the process can
write — including `configs/safety.yaml` (the file that defines its own guardrails),
`Makefile`, CI workflows, or `.env`. Nothing rejects the edit *because of its target*;
it is only judged on whether the resulting test/metric outcome looks like an
improvement.

**"Immutable-core" is currently a concept, not an enforced boundary.** Defining and
enforcing it is the central deliverable of Plans.md 2.2 (decide the mechanism) and 2.4
(test that the boundary holds).

---

## 4. Required Question (2): What happens when an edit fails its tests? (Catch-and-revert)

**Verdict: PARTIAL — revert works; the loop's stopping behavior is weak.**

The control flow (`safety_integration.py::execute_safe_evolution_step`):

1. **Checkpoint first.** If `auto_checkpoint=True` (default), a checkpoint of the current
   version is created *before* the new version is evaluated.
2. **Validate.** `validate_version_safety()` inspects test results
   (`status == "fail"`) and runs `RegressionDetector.detect_regression()`.
3. **Decide:**
   - All checks pass → version **accepted**.
   - Tests failed, or a **critical** regression detected, and `auto_rollback=True`
     (default) → `auto_rollback_on_failure()` restores the parent version's checkpoint.
   - Otherwise → version **rejected**, manual intervention flagged.

**Regression thresholds** (`regression_detector.py`): 5% global default; per-metric — a
≥10% performance regression is "regression", ≥25% is "critical"; a quality metric
dropping ≥5% is "regression", ≥10% is "critical". Only **critical** regressions
auto-trigger rollback; sub-critical ones lower the safety score but may still be
rejected-without-rollback.

**Where it is weak:**

- **No hard iteration cap is enforced on the evolution loop.** `max_iterations`
  (default 100) lives in config but is not enforced as a stopping condition in the
  pipeline. `max_rollback_attempts=3` caps only a *cascading rollback chain*, not total
  evolution cycles.
- **Rollback-and-continue can mask a persistently failing generator.** A variant that
  fails repeatedly causes repeated rollbacks to the parent without a circuit that says
  "the generator is stuck, stop." (Resilience circuit breakers exist for *component
  call* failures, not for *semantic* "every variant is bad" failure.)
- **Rollback failure halts the loop** (an exception propagates from
  `rollback_to_version`) — which is safe (fail-closed) but abrupt and not gracefully
  reported.

---

## 5. Required Question (3): Git state and corruption risks

**Verdict: PROTECTED for the rollback path; this is the strongest part of the system.**

Two findings matter here:

1. **Rollback is checkpoint-based, not Git-based.** `rollback_manager.py` restores via
   `CheckpointManager.restore_checkpoint()`, which copies checkpoint files with
   `shutil.copy2`/`copytree`. **No raw `git reset`/`checkout`/`stash` subprocess runs in
   the rollback path**, so a failed or interrupted git command cannot corrupt history
   during rollback. `.git/` is in `protected_dirs` and is preserved across restoration.

2. **Rollback target is hardened against catastrophic destinations.**
   `_validate_rollback_target()` raises `RollbackError` before any file operation if the
   target is:
   - the current working directory,
   - a parent of the current directory, or
   - a system directory (`/`, `/home`, `/usr`, `/var`, `/etc`, `/opt`).

   When the version manager supplies no safe directory, the system falls back to
   `./.evoseal/rollback_target` rather than risk an unsafe default. This is covered by
   `tests/safety/test_rollback_safety_critical.py`, including
   `test_safety_mechanisms_cannot_be_bypassed`.

**Residual risk:** checkpoint *restoration* clears the target directory before copying.
If the target were ever mis-resolved to a populated directory that passed validation
(e.g., a legitimately-configured working dir containing untracked user data), that data
outside `protected_dirs` would be wiped. The validation guards make the catastrophic
cases (cwd, `/`, parents) impossible, but "clear-then-restore" is inherently destructive
within the sanctioned target.

---

## 6. Required Question (4): Infinite-loop and runaway risks

**Verdict: PARTIAL.**

Present:

- **Per-test timeout:** test execution runs via `subprocess.run(..., timeout=...)`
  (default 60s) in `testrunner.py`. A single hung test cannot block forever.
- **Component circuit breakers:** the resilience layer opens breakers after a component
  call's failure threshold (3–10) and switches to degraded/fallback modes.
- **Cascading-rollback cap:** `max_rollback_attempts=3`.

Missing:

- **No enforced cap on total evolution iterations.** `max_iterations` is configuration,
  not a hard stop in `evolution_pipeline.py`.
- **No CPU/memory limit on generated code.** `psutil` *monitors* resource usage but no
  `resource.setrlimit`, cgroup, or container limit is applied. A variant with an infinite
  loop *inside its allotted 60s* or an unbounded-memory allocation is only observed, not
  contained, until the per-test timeout fires (and only if the runaway happens inside a
  timed test rather than at import/collection time).

Mitigating fact: generated code is **not** `exec()`'d or imported into the main process
by the safety layer itself — the self-editor returns `EditSuggestion` objects and
artifacts are stored as content/file references. Code runs only when **tests** execute
it as a subprocess. The runaway surface is therefore the test subprocess, bounded by the
per-test timeout but not by resource limits.

---

## 7. Required Question (5): Explicitly out-of-scope / unprotected vectors

**Verdict: UNPROTECTED. Stated explicitly so no downstream work assumes otherwise.**

The following are **not** defended against today. They are listed so that P1 work does
not accidentally claim security it does not provide:

| Vector | Status | Note |
|--------|--------|------|
| **Network egress from generated code** | UNPROTECTED | Test subprocess inherits network; a variant can call out, exfiltrate `.env` secrets, or fetch payloads. No proxy/firewall/offline mode. |
| **Arbitrary filesystem writes (forward)** | UNPROTECTED | Only rollback protects directories. A running variant/test can write anywhere the process can. |
| **Process spawning** | UNPROTECTED | `shell=False` blocks shell injection, but `subprocess`/`Popen` from generated code is unrestricted. |
| **Unbounded CPU/memory** | UNPROTECTED | Monitored via `psutil`, not limited. |
| **Secret exposure** | UNPROTECTED | `os.environ.copy()` passes the full environment (including API keys) into the test subprocess. |
| **Editing its own guardrails** | UNPROTECTED | No integrity check prevents a variant from modifying `configs/safety.yaml` or the validator thresholds (see Section 3). |
| **Malicious/adversarial model output** | OUT OF SCOPE | The model provider is trusted. EVOSEAL does not defend against a deliberately hostile LLM crafting an exploit; it assumes good-faith-but-fallible generation. |
| **Multi-tenant isolation** | OUT OF SCOPE | EVOSEAL is single-operator, single-host research software. No tenant boundary exists or is claimed. |

---

## 8. Posture summary

| Concern | Verdict | Strength |
|---------|---------|----------|
| Rollback target safety (no cwd/parent/system-dir destruction) | **PROTECTED** | Strong, test-backed, non-bypassable |
| Git history integrity during rollback | **PROTECTED** | Rollback is file-copy, not git-mutating |
| Outcome gating (regression/improvement validation) | **PROTECTED** | Statistical thresholds, required rules |
| Checkpoint integrity (SHA-256 verification) | **PROTECTED** | Tamper-evident |
| Test-failure catch-and-revert | **PARTIAL** | Revert works; loop lacks a "generator is stuck" circuit and a hard iteration cap |
| Runaway containment | **PARTIAL** | Per-test timeout only; no resource limits |
| Edit-scope / immutable-core enforcement | **UNPROTECTED** | No path allowlist at edit-application time |
| Generated-code execution sandbox | **UNPROTECTED** | Subprocess inherits full env, network, secrets |

**One-line summary:** EVOSEAL is good at *not corrupting itself with a bad-but-honest
edit* and bad at *containing a malformed-or-runaway edit's execution*. The former is the
research focus; the latter is the work of P1 2.2–2.4.

---

## 9. Open questions feeding the sandbox decision (Plans.md 2.2)

The sandbox-vs-rollback decision record (2.2) must resolve:

1. **Is execution containment in scope for research-stage EVOSEAL at all?** If the threat
   model is "honest-but-fallible generation on a trusted single host," Git/checkpoint
   rollback may be a *defensible* boundary and a container may be over-engineering. If the
   model must tolerate adversarial or untrusted generation, a sandbox is mandatory.
2. **What is the minimum viable edit-scope enforcement?** A path allowlist checked before
   any edit is written (cheap, in-process) closes the "edits its own guardrails" gap
   without a container. This may be the highest-value, lowest-cost mitigation.
3. **Should the test subprocess be stripped of secrets and network?** Running tests with a
   scrubbed environment and no network would close the exfiltration vector at low cost,
   independent of any container decision.
4. **Where does the hard iteration cap and "stuck generator" circuit live?** This is a
   correctness-containment gap (Section 4/6) that should be closed regardless of the
   sandbox decision.

---

## 10. Review

- **Author:** automated draft grounded in a code audit of the safety layer (file:line
  evidence retained in the task transcript).
- **Project-lead review:** required by Plans.md 2.1 DoD. Reviewer should confirm the
  UNPROTECTED verdicts in Sections 3, 7, and 8 match intent, and sign off on the scope
  boundaries in Section 7 (trusted model provider, single-tenant) as deliberate.

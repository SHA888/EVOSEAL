# ADR 0004 — Git-based version control for self-edits

**Status:** Accepted
**Date:** 2026-07-19
**Context:** EVOSEAL modifies its own codebase during evolution. It needs a
mechanism for tracking changes, reverting failures, and maintaining a history of
what the system looked like at each generation. The choice is between a custom
versioning system and Git.

---

## 1. Context

A self-modifying system must answer three questions after every edit:

1. **What changed?** (diff inspection)
2. **Can I go back?** (rollback)
3. **What did the system look like at generation N?** (reproducibility)

These are exactly the questions version control systems answer. The design
choice is whether to use an existing VCS (Git) or build a custom one.

## 2. Decision

Use **Git** as the version control backbone for all self-modifications, backed
by a checkpoint system that creates file-level snapshots for fast rollback.

## 3. Rationale

### Why Git over a custom versioning system

| Concern | Custom system | Git |
|---------|--------------|-----|
| Diff inspection | Must build tooling | `git diff` — mature, well-understood |
| Rollback | Must implement restore logic | `git checkout` / `git revert` |
| History | Must design storage format | Commits, branches, tags — built-in |
| Reproducibility | Must snapshot entire state | `git checkout <commit>` |
| Tooling ecosystem | None | IDEs, CI, code review, blame |
| Developer familiarity | Learning curve | Universal |

### Why Git over a database-only approach

EVOSEAL already uses SQLite for experiment tracking (`ExperimentDatabase`) and
code archives (`CodeArchive`). Why add Git on top?

- **Human-readable history.** Git history is browsable with standard tools.
  A database requires custom queries.
- **Atomic operations.** Git commits are atomic — either the full change lands
  or nothing does. Database transactions can achieve this, but require explicit
  implementation.
- **Branching.** Evolution variants can live on branches. The main branch
  always reflects the "accepted" state. This is a natural fit for the
  generate → evaluate → select → accept workflow.
- **Interoperability.** The code under modification is a Python package. Git is
  the standard for Python project versioning. Using Git means the evolution
  history is compatible with the broader ecosystem (CI, code review, etc.).

### The checkpoint layer

Git alone is not sufficient for fast rollback because:

1. `git checkout` modifies the working tree, which can conflict with running
   processes.
2. Checkpoint *restoration* needs to be faster than a full Git operation for
   the safety-critical rollback path.

EVOSEAL adds a **CheckpointManager** on top of Git that:

- Creates file-level snapshots (with SHA-256 integrity verification) before
  every edit.
- Restores via `shutil.copy2`/`copytree` — faster than `git checkout` and
  doesn't mutate `.git/`.
- Preserves `.git/` in `protected_dirs` so rollback never corrupts history.

The result is a two-layer system: Git for history and human-readable diffs,
checkpoints for fast, safe rollback.

### What this does *not* provide

- **No distributed versioning.** EVOSEAL is single-host. Git's distributed
  features (push/pull/merge) are used for the *repo*, not for the evolution
  history.
- **No conflict resolution.** The evolution loop is single-threaded — it
  applies one edit at a time. Merge conflicts don't arise.
- **No Git-based rollback in the safety path.** The safety layer uses
  checkpoint restoration, not `git reset`. This is deliberate — a failed
  `git reset` can corrupt the working tree; a failed file copy is safer.

## 4. Consequences

- **Positive:** Evolution history is inspectable with standard Git tools. The
  system benefits from Git's maturity (atomic commits, blame, bisect). CI/CD
  integration is natural.
- **Negative:** Git adds a dependency and some operational complexity
  (submodule management, `.git/` protection during rollback).
- **Neutral:** The checkpoint layer is a thin abstraction that could be swapped
  without changing the Git-based history.

## 5. References

- [`evoseal/core/checkpoint_manager.py`](../../evoseal/core/checkpoint_manager.py) — checkpoint creation/restoration.
- [`evoseal/core/rollback_manager.py`](../../evoseal/core/rollback_manager.py) — safe rollback with target validation.
- [`evoseal/core/version_database.py`](../../evoseal/core/version_database.py) — version tracking.
- [`docs/architecture/core/version_control_experiment_tracking.md`](../architecture/core/version_control_experiment_tracking.md) — version control architecture.
- [`docs/safety/sandbox_design.md`](../safety/sandbox_design.md) — ADR 0001 (rollback vs sandbox decision).

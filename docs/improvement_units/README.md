# Improvement Units

Structured, self-contained documentation for each successful self-modification in EVOSEAL's
evolution archive. Each unit is a standalone markdown file — one per improvement — that
captures the full context needed to understand, audit, or roll back the change.

## Motivation

Git diffs tell you *what* changed but not *why* it was safe, *how* it was validated, or
*what the rollback path is*. Improvement units close that gap by pairing every self-modification
with its decision rationale, validation evidence, and recovery instructions.

This pattern is inspired by OpenClaw's per-skill `SKILL.md` files: one document per unit of
capability that stands alone.

## Format

Each improvement unit uses the filename convention:

```
NNN-short-slug.md
```

Where `NNN` is a zero-padded sequence number and `short-slug` is a kebab-case summary.
Examples: `001-checkpoint-traversal-fix.md`, `002-improvement-validator-fix.md`.

See [TEMPLATE.md](TEMPLATE.md) for the required structure.

## Required Fields

| Field | Purpose |
|-------|---------|
| `id` | Unique identifier (`NNN-short-slug`) |
| `title` | Human-readable title |
| `date` | Date the improvement was applied (ISO 8601) |
| `type` | Category: `bug-fix`, `safety`, `performance`, `feature`, `refactor`, `docs` |
| `status` | Lifecycle stage: `candidate`, `beta`, `stable`, `rolled-back` |
| `pr` | Pull request number(s) that introduced this change |
| `files_changed` | List of files modified |
| `description` | What changed and why |
| `metrics_before` | Key measurements before the change |
| `metrics_after` | Key measurements after the change |
| `validation` | How the change was verified (tests, benchmarks, manual review) |
| `rollback` | Steps to revert if the change causes regression |
| `config_snapshot` | Relevant configuration at time of change |

## Lifecycle

Improvement units progress through stages:

1. **candidate** — passes regression tests, not yet battle-tested
2. **beta** — survives N additional evolution cycles without regression
3. **stable** — promoted to the permanent architecture
4. **rolled-back** — reverted; the unit preserves the record of what went wrong

The `status` field in each unit tracks where it sits. Progressive rollout gating (a separate
TODO item) automates promotion between stages.

## Directory Structure

```
docs/improvement_units/
├── INDEX.md          # Auto-generated or manually maintained index
├── TEMPLATE.md       # Blank template for new units
├── 001-*.md          # Individual improvement units
├── 002-*.md
└── ...
```

## Index

See [INDEX.md](INDEX.md) for a machine-readable table of all improvement units.

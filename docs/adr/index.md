# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for EVOSEAL. Each
ADR documents a significant design decision, the context that led to it, and the
trade-offs considered.

## Index

| ADR | Title | Status | Date |
|-----|-------|--------|------|
| [0001](../safety/sandbox_design.md) | Isolation strategy: rollback vs sandbox | Accepted | 2026-06-05 |
| [0002](0002-map-elites-selection.md) | MAP-Elites for candidate selection | Accepted | 2026-07-19 |
| [0003](0003-seal-over-prompt-engineering.md) | SEAL over pure prompt engineering | Accepted | 2026-07-19 |
| [0004](0004-git-based-version-control.md) | Git-based version control for self-edits | Accepted | 2026-07-19 |

## Conventions

- ADRs are numbered sequentially (`NNNN-short-title.md`).
- Status values: `Proposed`, `Accepted`, `Superseded`, `Deprecated`.
- Once accepted, an ADR is not deleted — it is superseded by a newer ADR if the
  decision changes.
- Follow the template in each ADR for consistency.

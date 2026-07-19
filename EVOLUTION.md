# EVOLUTION.md — Current Evolution Goals and State

This file tracks the current state of the EVOSEAL evolution system: what phase the
project is in, what goals are active, and what has been completed. Update this file
as evolution milestones are reached.

## Current phase

**Phase 3: Bidirectional Continuous Evolution** — in progress.

The system now supports a continuous co-evolution loop between EVOSEAL and its
backing model (Devstral via Ollama). The three sub-phases are:

| Sub-phase | Description | Status |
|-----------|-------------|--------|
| Phase 1 | Evolution data collection (`evoseal/evolution/`) | Done |
| Phase 2 | Fine-tuning infrastructure (`evoseal/fine_tuning/`) | Done |
| Phase 3 | Continuous evolution service + dashboard (`evoseal/services/`) | Done |

> **Maturity caveat (2026-07-19):** The Phase 3 *modules* are built, but the bidirectional
> loop is not yet closed. Key gaps: the daemon simulates evolution instead of running the
> pipeline; the training call has a method-name bug; model validation tests the baseline
> model rather than fine-tuned weights; deployment only writes to a JSON registry with no
> serving-layer integration; and the generator never consults the fine-tuning registry.
> Phase 3 is therefore architectural scaffolding, not yet operational co-evolution.
> See TODO.md ‘Close the bidirectional co-evolution loop’ for the specific gaps.

## Active goals (P2 — Medium Priority)

These are the next priorities from [TODO.md](TODO.md):

### Architecture documentation
- [ ] Write architecture doc for Devstral co-evolution
- [ ] Add sequence diagram for Devstral ↔ EVOSEAL message flow

### Dashboard improvements
- [ ] Add cost/token usage to the real-time dashboard
- [ ] Add a "generation diff" view
- [ ] Make dashboard accessible without running the full evolution loop

### Testing coverage
- [ ] Increase unit test coverage for `core/` modules
- [ ] Add regression test for config validation
- [ ] Add test for checkpoint save/restore

### Evolution archive and rollout
- [ ] Structured improvement units in the evolution archive
- [ ] Progressive rollout gating for self-modifications

## Completed milestones

### P0 — Critical (done 2026-06-04)
- Reproducible benchmark results published
- Convergence plots generated
- Self-improvement walkthrough documented
- Clone URL fixed
- Public-facing claims tightened

### P1 — Safety Hardening (done 2026-06-04)
- Threat model written (`docs/safety/threat_model.md`)
- Sandbox design decision record (`docs/adr/0001-isolation-strategy.md`)
- Adversarial self-modification tests
- Safety test CI job
- End-to-end loop integration test
- `--dry-run` mode
- Cost/budget specification and implementation
- Token/cost estimation (`evoseal estimate-cost`)
- `evoseal doctor` command

## Configuration

Key evolution parameters live in `configs/` (not checked into this file to avoid
staleness). Use `evoseal config show` to inspect the current configuration.

## See also

- [AGENT.md](AGENT.md) — agent identity and constraints.
- [SAFETY.md](SAFETY.md) — safety invariants and known gaps.
- [TODO.md](TODO.md) — full backlog.
- [Plans.md](Plans.md) — detailed task tracking with DoD.

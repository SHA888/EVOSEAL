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

> **Maturity caveat (updated 2026-07-30):** The Phase 3 *modules* are built and the
> bidirectional co-evolution loop is now closed (items 1–6 in TODO.md are merged;
> see PRs #73, #89, and the commits referenced in TODO.md § "Close the bidirectional
> co-evolution loop"). The daemon runs a real `EvolutionPipeline`; model validation
> serves the fine-tuned model; deployment uses `ollama create`; and the generator
> consults the fine-tuning registry. Remaining gaps are in P2/P3 dashboard
> improvements and test coverage.

## Active goals (P2 — Medium Priority)

These are the next priorities from [TODO.md](TODO.md):

### Architecture documentation
- [x] Write architecture doc for Devstral co-evolution (done 2026-07-21)
- [x] Add sequence diagram for Devstral ↔ EVOSEAL message flow (done 2026-07-23)

### Dashboard improvements
- [ ] Add cost/token usage to the real-time dashboard
- [ ] Add a "generation diff" view
- [ ] Make dashboard accessible without running the full evolution loop

### Testing coverage
- [ ] Increase unit test coverage for `core/` modules
- [x] Add regression test for config validation (done 2026-07-24)
- [x] Add test for checkpoint save/restore (done 2026-07-30)

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

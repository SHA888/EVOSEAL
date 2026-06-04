# EVOSEAL Plans.md

Created: 2026-06-04
Source: TODO.md

---

## Phase 2: P1 — Safety Hardening & Integration

Scope: Harden the self-modification loop against unsafe edits, add end-to-end
testability, and establish cost visibility. P0 is complete; all items below
are prerequisites before P2 (architecture docs, dashboard) work begins.

| Task | Description | DoD | Depends | Status |
|------|-------------|-----|---------|--------|
| 2.1 | Write adversarial self-modification tests [tdd:required] | Test suite in `tests/safety/` covers: DGM loop attempting to modify immutable-core components is blocked by `configs/safety.yaml`; rollback triggers on regression; all tests pass in CI | - | cc:TODO |
| 2.2 | Add safety test CI job [tdd:skip:ci-config-only] | `.github/workflows/ci.yml` has a `safety` job that runs adversarial tests on every PR; job is not skippable without label | 2.1 | cc:TODO |
| 2.3 | Document threat model [tdd:skip:docs-only] | `docs/safety/threat_model.md` committed to main; covers what can go wrong, what EVOSEAL protects against, and explicit out-of-scope risks | - | cc:TODO |
| 2.4 | Sandbox self-modifications [tdd:required] | DGM-generated pipeline variants execute in isolated Docker containers before touching main codebase; design doc in `docs/safety/sandbox_design.md`; at minimum a decision record on Git-rollback vs container isolation | - | cc:TODO |
| 2.5 | End-to-end loop integration test [tdd:required] | `tests/integration/test_evolution_loop.py` exercises full cycle (generate → evaluate → select → self-modify → regression check) with mock LLM responses; no API keys required; runs in CI | - | cc:TODO |
| 2.6 | Add `--dry-run` mode [tdd:required] | `evoseal pipeline start --dry-run` runs the loop with deterministic mock responses; output is deterministic for same seed; documented in CLI help | 2.5 | cc:TODO |
| 2.7 | Add `evoseal doctor` command [tdd:required] | `evoseal doctor` validates: API keys reachable, `configs/safety.yaml` well-formed, dependencies installed, Git state clean, budget/cost risks flagged; exits non-zero on critical failures | - | cc:TODO |
| 2.8 | Add token/cost estimation [tdd:required] | Token usage logged per evolution cycle; `evoseal estimate-cost --iterations N` outputs estimated tokens and cost for configured model; rough cost table added to README | - | cc:TODO |
| 2.9 | Add configurable token budget [tdd:required] | `max_tokens_per_run` and `max_cost_per_run` config options respected; evolution loop stops gracefully when budget is exhausted; warning emitted at 80% | 2.8 | cc:TODO |

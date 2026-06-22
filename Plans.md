# EVOSEAL Plans.md

Created: 2026-06-04
Source: TODO.md

---

## Phase 2: P1 — Safety Hardening & Integration

Scope: Establish threat model, decide on isolation strategy, build testable infrastructure,
and establish cost visibility. P0 is complete; all items below are prerequisites before P2
(architecture docs, dashboard) work begins.

**Execution strategy:** 2.1–2.2 first (establish ground truth for safety decisions).
Then 2.3–2.7 (safety tests + testability infrastructure) in parallel with 2.8–2.11
(cost tracking + doctor). All tasks unblock P2 work.

| Task | Description | DoD | Depends | Status |
|------|-------------|-----|---------|--------|
| 2.1 | Write threat model [tdd:skip:docs-only] | `docs/safety/threat_model.md` documents: (1) what edits DGM can make (scope of immutable-core), (2) what happens when edits fail tests (catch-and-revert behavior), (3) Git state risks (corruption scenarios), (4) infinite-loop risks, (5) explicit out-of-scope risks (e.g., network calls in edits). Reviewed by project lead. | - | cc:done [67cd127] |
| 2.2 | Decide: sandbox isolation vs rollback [tdd:skip:design-doc] | `docs/safety/sandbox_design.md` is a decision record (ADR) covering: threat model (2.1) implications, trade-off matrix (cost/complexity/blast-radius for containers vs Git rollback), chosen approach + justification. If decision is "Git rollback sufficient," explain why threat model doesn't require isolation. | 2.1 | cc:done [2d48347] |
| 2.3 | Mock LLM/component infrastructure [tdd:required] | `evoseal/testing/mock_components.py` provides mocks for DGM (fake variant generator), OpenEvolve (fake evaluator), SEAL (fake fine-tuner). Mocks wired via env var `EVOSEAL_MOCK_MODE=true` (all-or-nothing). Deterministic output for same seed. Used by 2.6 and 2.7. | - | cc:done [d75dfd1] |
| 2.4 | Write adversarial self-modification tests [tdd:required] | `tests/safety/test_adversarial_edits.py` covers BOTH windows from the 2.2 ADR: (T1) DGM edit *targeting* out-of-scope files (`safety.yaml`, `Makefile`, `.env`) is blocked by the allowlist (2.13); (T2) a variant whose *test code* writes a forbidden path or reads secrets at runtime is contained by the sandboxed test env (2.14); rollback triggers on violations; all tests pass. | 2.1, 2.2, 2.13, 2.14 | cc:done [58fafa1] |
| 2.5 | Add safety test CI job [tdd:skip:ci-config-only] | `.github/workflows/ci.yml` has `safety` job that runs 2.4 on every PR; job is not skippable without label; required check enabled. | 2.4 | cc:done [ea5d57b] |
| 2.6 | End-to-end loop integration test [tdd:required] | `tests/integration/test_evolution_loop.py` exercises full cycle (generate → evaluate → select → self-modify → regression check) using mocks from 2.3; generates 2 variants, selects winner, simulates self-edit; no API calls; passes with `EVOSEAL_MOCK_MODE=true`. | 2.3 | cc:done [3eb6f8a] |
| 2.7 | Add `--dry-run` mode [tdd:required] | `evoseal pipeline start --dry-run` sets `EVOSEAL_MOCK_MODE=true` + `EVOSEAL_DRY_RUN=true` (mocks respond, no actual edits to disk). Output deterministic for same seed. Documented in CLI help. Works with 2.6 test. | 2.3, 2.6 | cc:done [b6f19c5] |
| 2.8 | Document cost/budget spec [tdd:skip:design-doc] | `docs/safety/cost_and_budget_spec.md` covers: (1) cost model (tokens per cycle), (2) budget config schema, (3) graceful-stop behavior on exhaustion, (4) critical/major/minor failure modes for cost violations. Defines what 2.9–2.11 validate. | - | cc:done [9ab4973] |
| 2.9 | Add token/cost estimation [tdd:required] | Token usage logged per evolution cycle; `evoseal estimate-cost --iterations N` outputs tokens + cost for configured model; cost expectations table added to README. Passes schema validation per 2.8. | 2.8 | cc:done [8538321] |
| 2.10 | Add configurable token budget [tdd:required] | `max_tokens_per_run` and `max_cost_per_run` config options; loop stops gracefully when budget exhausted; warning at 80%. Validated against spec from 2.8. 2.6 integration test covers budget-exhaustion scenario. | 2.8, 2.9 | cc:done [0c49b42] |
| 2.11 | Add `evoseal doctor` command [tdd:required] | `evoseal doctor` validates: API keys reachable, `configs/safety.yaml` well-formed, dependencies installed, Git state clean, budget/cost risks flagged (per threat model 2.1 + spec 2.8). Exits non-zero **only on critical failures** (defined by 2.1 + 2.8, not ad-hoc). | 2.1, 2.8 | cc:done [46d9b4a] |
| 2.12 | Fix dead success-check in rollback path [tdd:required] | `rollback_manager.py:91-93` treats `restore_checkpoint()`'s `Dict[str, Any]` return as a bool, so `if not success:` is dead code (a non-empty dict is always truthy; real failures raise `CheckpointError`). Fix to check `result.get("success")`; add a regression test where restoration returns `{"success": False}` and confirm `RollbackError` is raised. Surfaced by the 2.1 threat-model audit. | 2.1 | cc:todo |
| 2.13 | Edit-scope allowlist (Tier 1, T1 window) [tdd:required] | Enforce an editable-path allowlist *before* any generated edit is written to disk. Reject edits targeting `configs/safety.yaml`, `.github/workflows/`, `.env`, `Makefile`, and anything outside the declared mutable surface. Allowlist is itself not editable by the loop. Per 2.2 ADR §6; guards the T1 window only (test-runtime writes are 2.14). | 2.1, 2.2 | cc:todo |
| 2.14 | Sandboxed test execution (Tier 1, T2 window) [tdd:required] | Run the variant test subprocess with: secrets stripped from the environment (no `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`), network disabled or restricted, `configs/safety.yaml` + `.env` mounted/enforced read-only, ideally as an unprivileged user. Closes the secret-exfiltration, network-egress, and runtime-guardrail-write vectors the allowlist cannot. Per 2.2 ADR §6. | 2.1, 2.2 | cc:todo |
| 2.15 | Runaway controls (Tier 1) [tdd:required] | Enforce a hard evolution-iteration cap (config-backed, actually checked in `evolution_pipeline.py`) and a "stuck generator" circuit (N consecutive rejected/failed variants → stop). Add `resource.setrlimit` on the test subprocess: CPU ≤ ~120s, address space ≤ 2 GB, open files ≤ 256; breach terminates subprocess and rejects variant. Closes threat model §4/§6 PARTIAL items. | 2.1, 2.2 | cc:todo |

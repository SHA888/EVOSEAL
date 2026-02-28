# EVOSEAL — Improvement TODO

> Structured improvement plan based on project review (Feb 2026).
> Prioritized by impact. Check items off as you go.

---

## 🔴 P0 — Critical (Do First)

### Benchmarks & Empirical Validation

- [ ] **Publish reproducible benchmark results**
  - Pick 1–2 standard benchmarks (HumanEval, MBPP, or SWE-bench-lite)
  - Run EVOSEAL against them with a fixed config and record raw numbers
  - Compare against a non-evolutionary baseline (e.g., single-shot GPT-4 generation)
  - Publish results in `benchmarks/comparison_results.md` (already referenced in README but not public)
- [ ] **Add convergence plots**
  - Track fitness/score per generation across multiple runs
  - Show that the evolutionary loop actually converges (or explain when/why it doesn't)
- [ ] **Document a concrete "before vs. after" self-improvement example**
  - Show the agent's pipeline at generation 0 vs. generation N
  - Explain what changed and why it was an improvement

### Quick Start Fix

- [ ] **Fix clone URL inconsistency** — README says `git clone https://github.com/Continual-Intelligence/SEAL` then `cd EVOSEAL`; this should be `git clone https://github.com/SHA888/EVOSEAL.git`

---

## 🟠 P1 — High Priority

### Safety Hardening

- [ ] **Write adversarial self-modification tests**
  - Create test cases where the DGM loop attempts to modify "immutable core" components
  - Verify that `configs/safety.yaml` constraints actually block these modifications
  - Test that rollback triggers correctly when a self-edit breaks regression tests
- [ ] **Add a safety test CI job**
  - Run adversarial safety tests in GitHub Actions on every PR
- [ ] **Document the threat model**
  - What can go wrong with a self-modifying agent?
  - What does EVOSEAL protect against, and what is explicitly out of scope?
  - Add as `docs/safety/threat_model.md`

### Integration Testing

- [ ] **End-to-end loop test**
  - Write an integration test that exercises the full cycle: generate variant → evaluate → select → self-modify → verify no regression
  - Should be runnable with mock LLM responses (no API keys needed)
- [ ] **Add a `--dry-run` mode**
  - Simulate the evolution loop with deterministic mock responses
  - Useful for CI, demos, and exploring architecture without API costs

### Cost Management

- [ ] **Add token/cost estimation**
  - Log token usage per evolution cycle (prompt + completion tokens)
  - Add a `evoseal estimate-cost --iterations N` command or config option
  - Document rough cost expectations in README (e.g., "10 iterations ≈ X tokens ≈ $Y with GPT-4")
- [ ] **Add configurable token budget / API rate limits**
  - Allow users to set a max spend per run in config
  - Graceful stop when budget is exhausted

---

## 🟡 P2 — Medium Priority

### Phase 3 (Bidirectional Evolution) Documentation

- [ ] **Write architecture doc for Devstral co-evolution**
  - How does the bidirectional feedback loop work?
  - What prevents the two systems from diverging?
  - What metrics determine "improvement" in the bidirectional context?
  - Add as `docs/architecture/bidirectional_evolution.md`
- [ ] **Add sequence diagram** showing the Devstral ↔ EVOSEAL message flow

### Dashboard Improvements

- [ ] **Add cost/token usage to the real-time dashboard**
  - Show cumulative API spend alongside evolution metrics
- [ ] **Add a "generation diff" view**
  - Show code diffs between generations in the dashboard UI
- [ ] **Make dashboard accessible without running the full evolution loop**
  - Allow loading from checkpoint data for post-hoc analysis

### Testing Coverage

- [ ] **Increase unit test coverage for `core/` modules**
  - `controller.py`, `evaluator.py`, `selection.py`, `version_database.py`
  - Target: meaningful coverage on core logic paths, not just line count
- [ ] **Add regression test for config validation**
  - Malformed YAML, missing required sections, type mismatches
- [ ] **Add test for checkpoint save/restore**
  - Interrupt mid-evolution, restore from checkpoint, verify state consistency

---

## 🟢 P3 — Nice to Have

### Developer Experience

- [ ] **Add a `Makefile` or `just` file** with common workflows
  - `make setup`, `make test`, `make lint`, `make benchmark`, `make docs`
- [ ] **Add pre-commit hooks**
  - Black formatting, ruff/flake8 linting, type checking (mypy)
- [ ] **Add `CHANGELOG.md`** tracking releases (v0.3.2 is latest but no changelog visible)
- [ ] **Docker support**
  - `Dockerfile` + `docker-compose.yml` for zero-setup local development
  - Include dashboard, worker, and API server as services

### Documentation Polish

- [ ] **Add architecture decision records (ADRs)**
  - Why MAP-Elites over other evolutionary strategies?
  - Why SEAL over pure prompt engineering?
  - Why Git-based version control for self-edits?
- [ ] **Add a "How It Actually Works" tutorial**
  - Walk through a single evolution cycle step by step with real logs
  - Lower the barrier for new contributors
- [ ] **Improve API reference**
  - Ensure all public classes/functions have docstrings
  - Auto-generate API docs (MkDocs + mkdocstrings)

### Research Extensions

- [ ] **Multi-objective Pareto front visualization**
  - Plot correctness vs. efficiency vs. readability trade-offs across generations
- [ ] **Add support for local models (Ollama/vLLM)**
  - Reduce API dependency for experimentation
  - README mentions Ollama integration — verify it works end-to-end
- [ ] **Explore population-based training (PBT) as alternative to MAP-Elites**
  - Could improve convergence speed for hyperparameter evolution
- [ ] **Human-in-the-loop feedback interface**
  - Allow a developer to approve/reject self-modifications via the dashboard
  - Track acceptance rate as a meta-metric

---

## 📋 Tracking

| Priority | Total | Done |
|----------|-------|------|
| 🔴 P0    | 4     | 0    |
| 🟠 P1    | 7     | 0    |
| 🟡 P2    | 7     | 0    |
| 🟢 P3    | 9     | 0    |
| **Total** | **27** | **0** |

> Update this table as you complete items. Recommended flow: P0 → P1 → P2 → P3.
# EVOSEAL — Improvement TODO

> Structured improvement plan based on project review + OpenClaw comparative analysis (Mar 2026).
> Prioritized by impact. Check items off as you go.
>
> **Reference project**: [OpenClaw](https://github.com/openclaw/openclaw) — 310k★, 18k+ commits, 20+ channel integrations.
> Parallels: self-modification loops, composable capability systems, always-on daemons.
> Key difference: OpenClaw's self-modification is user-driven; EVOSEAL's is autonomous and scheduled.
> EVOSEAL explores what happens when the self-modification loop is autonomous and systematic — a research direction OpenClaw's architecture doesn't attempt.

---

## 🔴 P0 — Critical (Do First)

### Benchmarks & Empirical Validation

- [x] **Publish reproducible benchmark results** _(done 2026-06-04, commit ce1f5af)_
  - Single-shot baseline on 10 synthetic coding tasks; claude-opus-4-8 via Anthropic API
  - Results in `benchmarks/comparison_results.md`; raw data in `benchmarks/baseline_results.json`
  - Docker-based reproducible environment; `uv pip install -e ".[benchmarks]"` to run locally
- [x] **Add convergence plots** _(done 2026-06-04, commit ce4163a)_
  - 2 independent runs, 20 generations each; fitness-vs-generation PNG committed to `benchmarks/plots/`
  - Plot and markdown table auto-updated by `benchmarks/generate_convergence_plots.py` on re-run
- [x] **Document a concrete "before vs. after" self-improvement example** _(done 2026-06-04, commit 97bcc13)_
  - `docs/examples/self_improvement_walkthrough.md`: Gen 0 greedy selector → Gen N adaptive variance-aware selector
  - Includes full diff, metrics table (+26% fitness), and explanation of the improvement mechanism

### Quick Start Fix

- [x] **Fix clone URL inconsistency** _(done 2026-06-04)_
  - README now shows correct `git clone https://github.com/SHA888/EVOSEAL.git`

### Positioning & Framing

- [x] **Tighten public-facing claims about self-modification maturity** _(done 2026-06-04)_
  - Added research-status callout at top of README; removed "production-ready" language
  - Reframed as research project; softened unsubstantiated benchmark claims

---

## 🟠 P1 — High Priority

### Safety Hardening

- [x] **Write adversarial self-modification tests** _(done — Plans.md 2.4, commit 58fafa1)_
  - Create test cases where the DGM loop attempts to modify "immutable core" components
  - Verify that `configs/safety.yaml` constraints actually block these modifications
  - Test that rollback triggers correctly when a self-edit breaks regression tests
- [x] **Add a safety test CI job** _(done — Plans.md 2.5, commit ea5d57b)_
  - Run adversarial safety tests in GitHub Actions on every PR
- [x] **Document the threat model** _(done — Plans.md 2.1, commit 67cd127)_
  - What can go wrong with a self-modifying agent?
  - What does EVOSEAL protect against, and what is explicitly out of scope?
  - Add as `docs/safety/threat_model.md`
- [x] **Sandbox self-modifications** _(done — decision in Plans.md 2.2/commit 2d48347; implemented via 2.13 edit-scope allowlist/commit f45d923 and 2.14 sandboxed test execution/commit c0cbc59)_ _(inspired by OpenClaw's Docker sandbox model)_
  - OpenClaw sandboxes non-main sessions in per-session Docker containers to contain untrusted execution
  - Apply similar principle: DGM-generated pipeline variants should execute in isolated environments before touching the main codebase
  - Evaluate whether the current Git-based rollback is sufficient or whether a container-based isolation layer is needed

- [ ] **Fix missing `configs/safety.yaml` and `config/` vs `configs/` path discrepancy**
  - Multiple safety-critical modules reference `configs/safety.yaml` (plural `configs/`) as the immutable safety configuration, but neither that file nor a `configs/` directory exists
  - Only `config/` (singular) exists, containing `budget.yaml`, `logging.yaml`, etc. — no `safety.yaml`
  - Referenced by: `evoseal/core/edit_scope_validator.py` (lines 27, 52, 80), `evoseal/core/safety_integration.py` (line 286), `evoseal/core/testrunner.py` (line 652), `evoseal/cli/commands/doctor.py` (line 181), and multiple safety tests
  - Impact: `evoseal doctor` reports 'safety.yaml not found'; edit-scope allowlist references a nonexistent path; safety tests assert against a file that does not exist on disk
  - Resolve by deciding whether the canonical path is `config/safety.yaml` or `configs/safety.yaml`, creating the file with appropriate defaults, and updating all references to match

### Integration Testing

- [x] **End-to-end loop test** _(done — Plans.md 2.6, commit 3eb6f8a)_
  - Write an integration test that exercises the full cycle: generate variant → evaluate → select → self-modify → verify no regression
  - Should be runnable with mock LLM responses (no API keys needed)
- [x] **Add a `--dry-run` mode** _(done — Plans.md 2.7, commit b6f19c5)_
  - Simulate the evolution loop with deterministic mock responses
  - Useful for CI, demos, and exploring architecture without API costs
- [x] **Add `evoseal doctor` command** _(done — Plans.md 2.11, commit 46d9b4a)_ _(inspired by OpenClaw's `openclaw doctor`)_
  - Validate API keys are set and reachable
  - Check `configs/safety.yaml` is present and well-formed
  - Verify the evolution loop can start (dependencies, permissions, Git state)
  - Flag budget/cost risks (no token limit configured, expensive model selected)
  - Surface risky configurations (e.g., immutable core protections disabled)

### Cost Management

- [x] **Add token/cost estimation** _(done — Plans.md 2.9, commit 8538321)_
  - Log token usage per evolution cycle (prompt + completion tokens)
  - Add a `evoseal estimate-cost --iterations N` command or config option
  - Document rough cost expectations in README (e.g., "10 iterations ≈ X tokens ≈ $Y with GPT-4")
- [x] **Add configurable token budget / API rate limits** _(done — Plans.md 2.10, commit 0c49b42)_
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

### Evolution Archive & Rollout _(inspired by OpenClaw patterns)_

- [ ] **Structured improvement units in the evolution archive**
  - Each successful self-modification should be a self-contained, documented unit (not just a Git diff)
  - Include: description of change, metrics before/after, rollback instructions, and relevant config snapshot
  - Pattern: similar to OpenClaw's per-skill `SKILL.md` files — one doc per improvement that stands alone
- [ ] **Progressive rollout gating for self-modifications**
  - Evolution candidates go through `candidate → beta → stable` stages before permanent adoption
  - `candidate`: passes regression tests
  - `beta`: survives N additional evolution cycles without regression
  - `stable`: promoted to the main architecture
  - Pattern: analogous to OpenClaw's development channels (stable/beta/dev with npm dist-tags)

---

## 🟢 P3 — Nice to Have

### Developer Experience

- [x] **Add a `Makefile`** _(already present)_
  - `make test`, `make format`, `make type-check`, `make check`, `make test-cov`
- [x] **Add pre-commit hooks** _(done 2026-06-04)_
  - ruff (lint + format), bandit, detect-secrets, hadolint, trufflehog, pytest fast-check
  - Config in `.pre-commit-config.yaml`; install with `pre-commit install`
- [ ] **Add `CHANGELOG.md`** tracking releases (v0.3.7 is latest but no changelog visible)
- [x] **Docker support** _(already present)_
  - `Dockerfile` (python:3.11-slim + uv) and `docker-compose.evoseal.yml`
  - Dashboard on port 9613; volumes for checkpoints, data, reports, benchmarks
- [ ] **Adopt workspace prompt file conventions** _(inspired by OpenClaw's AGENTS.md/SOUL.md/TOOLS.md)_
  - Create a standard file layout for the evolution workspace: e.g., `AGENT.md` (agent identity/constraints), `EVOLUTION.md` (current evolution goals/state), `SAFETY.md` (safety invariants)
  - Makes the system self-documenting and easier for contributors to understand agent behavior at any point

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

| Priority | Total | Done | Notes |
|----------|-------|------|-------|
| 🔴 P0    | 5     | 5    | All complete as of 2026-06-04 |
| 🟠 P1    | 10    | 9    | Safety config path gap open |
| 🟡 P2    | 10    | 0    | In progress — see Plans.md Phase 3 (3.1-3.12) |
| 🟢 P3    | 12    | 3    | Makefile, pre-commit, Docker complete |
| **Total** | **37** | **17** | |

> Update this table as you complete items. Recommended flow: P0 → P1 → P2 → P3.
>
> Items marked _(inspired by OpenClaw)_ are patterns borrowed from the OpenClaw project.
> See comparative analysis for full context on what to adopt vs. what to avoid.

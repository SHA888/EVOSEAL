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

### Positioning & Framing

- [ ] **Tighten public-facing claims about self-modification maturity**
  - Avoid comparative language that implies superiority over battle-tested projects (e.g., OpenClaw: 310k★, 18k+ commits, production-hardened across 20+ channels)
  - Defensible framing: "EVOSEAL explores autonomous, scheduled self-modification — a research direction that user-driven systems like OpenClaw don't attempt"
  - Distinguish research ambition from production validation in README and docs

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
- [ ] **Sandbox self-modifications** _(inspired by OpenClaw's Docker sandbox model)_
  - OpenClaw sandboxes non-main sessions in per-session Docker containers to contain untrusted execution
  - Apply similar principle: DGM-generated pipeline variants should execute in isolated environments before touching the main codebase
  - Evaluate whether the current Git-based rollback is sufficient or whether a container-based isolation layer is needed

### Integration Testing

- [ ] **End-to-end loop test**
  - Write an integration test that exercises the full cycle: generate variant → evaluate → select → self-modify → verify no regression
  - Should be runnable with mock LLM responses (no API keys needed)
- [ ] **Add a `--dry-run` mode**
  - Simulate the evolution loop with deterministic mock responses
  - Useful for CI, demos, and exploring architecture without API costs
- [ ] **Add `evoseal doctor` command** _(inspired by OpenClaw's `openclaw doctor`)_
  - Validate API keys are set and reachable
  - Check `configs/safety.yaml` is present and well-formed
  - Verify the evolution loop can start (dependencies, permissions, Git state)
  - Flag budget/cost risks (no token limit configured, expensive model selected)
  - Surface risky configurations (e.g., immutable core protections disabled)

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

- [ ] **Add a `Makefile` or `just` file** with common workflows
  - `make setup`, `make test`, `make lint`, `make benchmark`, `make docs`
- [ ] **Add pre-commit hooks**
  - Black formatting, ruff/flake8 linting, type checking (mypy)
- [ ] **Add `CHANGELOG.md`** tracking releases (v0.3.2 is latest but no changelog visible)
- [ ] **Docker support**
  - `Dockerfile` + `docker-compose.yml` for zero-setup local development
  - Include dashboard, worker, and API server as services
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
| 🔴 P0    | 5     | 0    | +1 positioning/framing |
| 🟠 P1    | 9     | 0    | +1 sandbox isolation, +1 `evoseal doctor` |
| 🟡 P2    | 9     | 0    | +2 evolution archive & progressive rollout |
| 🟢 P3    | 10    | 0    | +1 workspace conventions |
| **Total** | **33** | **0** | **+6 from OpenClaw analysis** |

> Update this table as you complete items. Recommended flow: P0 → P1 → P2 → P3.
>
> Items marked _(inspired by OpenClaw)_ are patterns borrowed from the OpenClaw project.
> See comparative analysis for full context on what to adopt vs. what to avoid.

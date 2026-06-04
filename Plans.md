# EVOSEAL Plans.md

Created: 2026-06-04
Source: TODO.md P0 — Critical

---

## Phase 1: P0 — Empirical Validation & Honesty

Scope: Establish reproducible evidence that the evolution loop actually
works, and ensure all public-facing claims are backed by real data.
Addressed in priority order before any P1 work.

| Task | Description | DoD | Depends | Status |
|------|-------------|-----|---------|--------|
| 1.1 | Fix clone URL and research-status framing in README [tdd:skip:docs-only] | README has correct SHA888/EVOSEAL clone URL; research-status callout present at top; no "production-ready" overclaims; committed to main | - | cc:done |
| 1.2 | Publish reproducible benchmark results [tdd:skip:empirical-research-output] | `benchmarks/comparison_results.md` committed to main with raw scores on ≥1 standard benchmark (HumanEval, MBPP, or SWE-bench-lite); EVOSEAL result and single-shot baseline both recorded; fixed config documented | - | cc:done [ce1f5af] |
| 1.3 | Add convergence plots [tdd:skip:empirical-research-output] | ≥1 fitness-vs-generation plot image committed under `benchmarks/plots/`; data from ≥2 independent runs; plot referenced from `benchmarks/comparison_results.md` | 1.2 | cc:done [ce4163a] |
| 1.4 | Document a concrete before/after self-improvement example [tdd:skip:docs-only] | `docs/examples/self_improvement_walkthrough.md` committed to main; shows generation-0 vs generation-N pipeline diff; explains what changed and why it was an improvement | 1.2 | cc:done [97bcc13] |

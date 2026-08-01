```yaml
id: "002-improvement-validator-fix"
title: "Fix non-functional ImprovementValidator and hardcoded validation stub"
date: 2026-07-22
type: bug-fix
status: stable
pr:
  - "#76"
authors:
  - agent: evoseal-dev
files_changed:
  - evoseal/core/evolution_pipeline.py
  - evoseal/core/improvement_validator.py
```

## Description

`ImprovementValidator.validate_improvement()` called `self.metrics_tracker.get_metrics_by_id()`,
but `MetricsTracker` only defined a private `_get_metrics_by_id` — every call raised
`AttributeError`. The method also referenced an undefined `message` variable and had no
`return` statement on its success path.

In practice this was unreachable: `EvolutionPipeline` instantiated the validator but never
called it. The actual validation gate was `_validate_improvement()` in `evolution_pipeline.py`,
which unconditionally returned `True` — meaning a self-modification that doubled test failures
and tripled runtime was always accepted as a validated improvement.

## Metrics Before

| Metric | Value |
|--------|-------|
| `validate_improvement()` callability | Raises `AttributeError` (missing method on `MetricsTracker`) |
| `_validate_improvement()` gate | Always returns `True` — no actual validation |
| Test coverage for validation gate | 0 tests |
| Malformed validator response handling | None |

## Metrics After

| Metric | Value |
|--------|-------|
| `validate_improvement()` callability | Fixed (method exists, returns proper result) |
| `_validate_improvement()` gate | Calls real validator; fails closed on exceptions and malformed responses |
| Test coverage for validation gate | 7 regression tests (first-iteration, improvement, regression, exception, malformed, passthrough) |
| Malformed validator response handling | Rejects non-`ValidationResult` returns |

## Validation

- `ruff format --check .` — pass
- `ruff check evoseal/ tests/` — pass
- `pytest tests/unit/core/test_evolution_pipeline_validation.py -q` — 7 passed, 0 failed
- `grep -rn "validate_improvement\|_validate_improvement" evoseal/` confirms wiring

## Rollback

```bash
git revert e9f723c
```

Side effect: validation gate reverts to always-accept. Self-modifications with regressions
will be silently accepted again.

## Config Snapshot

No config changes. The fix is in `evolution_pipeline.py` validation logic and
`improvement_validator.py` method signatures.

## Notes

This was the second of six critical bugs from the 2026-07-22 whole-repo review. The
"always-accept" stub was the most dangerous: it made the entire validation layer decorative.
The fix implements fail-closed semantics — any exception or unexpected response from the
validator causes rejection, not acceptance.

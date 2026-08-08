# DGM/OpenEvolve Adapter Consolidation

> **Date:** 2026-08-08
> **Status:** Analysis complete — canonical adapters identified

## Problem

EVOSEAL has two adapter layouts for each of DGM and OpenEvolve that have
drifted apart:

| Component | Legacy adapter | Canonical adapter |
|-----------|---------------|-------------------|
| DGM | `evoseal.integration.dgm` | `evoseal.integration.dgmr` |
| OpenEvolve | `evoseal.integration.openevolve` | `evoseal.integration.oe` |

This creates confusion about which to import and risks new code targeting the
wrong module.

## Analysis

### DGM

- **`evoseal/integration/dgmr/dgm_adapter.py`** (canonical) — a remote HTTP
  adapter implementing `BaseComponentAdapter`. Used by the orchestrator
  (`orchestrator.py`), the public `__init__.py`, and all recent unit tests
  (`test_dgm_adapter_remote.py`, `test_orchestrator_smoke.py`,
  `test_dry_run_mode.py`).

- **`evoseal/integration/dgm/evolution_manager.py`** (legacy) — a local adapter
  that directly imports the `dgm/` git submodule (`from dgm import DGM_outer`).
  Used only by `tests/regression/test_regression_evolution.py`, which mocks the
  submodule import. Also contains `data_adapter.py` (used only by
  `EvolutionManager`).

**Recommendation:** Keep `dgmr/` as the sole canonical adapter. `dgm/` is
retained for the one regression test but should not be used by new code.
Deprecation notices have been added to `dgm/evolution_manager.py` and
`dgm/data_adapter.py`.

### OpenEvolve

- **`evoseal/integration/oe/openevolve_adapter.py`** (canonical) — a remote HTTP
  adapter implementing `BaseComponentAdapter`. Used by the orchestrator, the
  public `__init__.py`, and all tests.

- **`evoseal/integration/openevolve/__init__.py`** (broken) — attempted to
  `from .openevolve_adapter import OpenEvolveAdapter`, but no such file exists
  in this directory. Any `import evoseal.integration.openevolve` would raise
  `ImportError`. Nothing in production code imports from this package.

**Recommendation:** Keep `oe/` as the sole canonical adapter. The broken
`openevolve/__init__.py` has been fixed to a safe empty module with a
deprecation notice.

## Decision

| Package | Action | Reason |
|---------|--------|--------|
| `dgmr/` | **Canonical** | Production adapter, orchestrator + tests |
| `dgm/` | Deprecated (kept) | Legacy, one regression test consumer |
| `oe/` | **Canonical** | Production adapter, orchestrator + tests |
| `openevolve/` | Deprecated (fixed) | Was broken, no consumers |

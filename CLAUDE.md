# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

EVOSEAL is a research project on **autonomous, scheduled self-modifying code evolution**. It orchestrates three external components — **DGM** (Darwin Gödel Machine), **OpenEvolve**, and **SEAL** (Self-Adapting Language Models) — to alternate between *solving a task* (generate/evaluate/select code variants) and *improving its own pipeline*. See `README.md` for the conceptual overview and `TODO.md` for the current roadmap and known gaps (most ambitious features are not yet built; treat maturity claims as research-stage).

## Repository layout: components are git submodules

DGM, OpenEvolve, and SEAL live at the repo root as **git submodules** (`dgm/`, `openevolve/`, `SEAL/`; see `.gitmodules`). They are *not* part of the `evoseal` package and are **excluded from all formatting, linting, and test collection** (see the `exclude`/`norecursedirs` settings in `pyproject.toml` and `pytest.ini`). Never edit submodule code to fix EVOSEAL behavior — wrap or adapt it instead.

The `evoseal/` package integrates them through thin adapters in `evoseal/integration/{dgm,openevolve,seal,oe,dgmr}/`. After cloning, submodules must be initialized: `git submodule update --init --recursive`.

## Two entry points

- **`evoseal`** — the user-facing Python CLI (Typer), defined at `evoseal.cli.main:app`. Subcommands are registered in `evoseal/cli/main.py` and implemented in `evoseal/cli/commands/`: `init`, `config`, `pipeline`, `seal`, `openevolve`, `dgm`, `start`, `stop`, `status`, `export`.
- **`scripts/evoseal`** — a Bash script runner for dev/ops tasks (test, evolve, deploy, version, release), sourcing modular helpers from `scripts/lib/`. Distinct from the Python CLI.

## Architecture (the big picture)

The engine lives in `evoseal/core/`. The orchestration layers, outer to inner:

- **`evolution_pipeline.py`** → `EvolutionPipeline`: top-level orchestrator that wires DGM + OpenEvolve + SEAL together and drives the loop. The loop steps are the `WorkflowStage` enum: `INITIALIZING → ANALYZING → GENERATING → ADAPTING → EVALUATING → VALIDATING`.
- **`workflow.py`** → `WorkflowEngine`: generic async workflow execution/state machine the pipeline runs on.
- **`controller.py`** → `Controller`: manages OpenEvolve generations, coordinating `TestRunner` (`testrunner.py`), `Evaluator` (`evaluator.py`), and candidate `selection.py`.

Wrapped around that engine is a **safety/resilience layer** that is central to the project's premise (a self-modifying agent must not corrupt itself). When changing the evolution flow, account for these — they are not optional add-ons:

- `safety_integration.py`, `improvement_validator.py`, `regression_detector.py` — gate whether a self-edit is accepted.
- `rollback_manager.py`, `checkpoint_manager.py`, `version_database.py` / `version_tracker.py` — Git-backed checkpointing and rollback of accepted/rejected changes.
- `resilience.py` / `resilience_integration.py`, `error_recovery.py` — fault tolerance around component calls.
- `events.py`, `metrics_tracker.py`, `logging_system.py` — eventing/telemetry consumed by the dashboard.

The three-phase continuous-evolution system (the "Devstral co-evolution" loop) is layered on top:
- **Phase 1** `evoseal/evolution/` — collects evolution results and builds training data.
- **Phase 2** `evoseal/fine_tuning/` — LoRA/QLoRA fine-tuning, model validation, versioning/rollback.
- **Phase 3** `evoseal/services/` — `continuous_evolution_service.py` (the long-running daemon) and `monitoring_dashboard.py` (WebSocket dashboard, default port 9613).

Model access goes through `evoseal/providers/` (OpenAI, Anthropic, Ollama/Devstral) behind a provider-manager abstraction.

## Common commands

Install (editable, with dev + test tooling):
```bash
pip install -e ".[dev,test]"
git submodule update --init --recursive
pre-commit install && pre-commit install --hook-type pre-push
```

Tests (pytest, `asyncio_mode = strict`, `testpaths = tests`):
```bash
make test                 # pytest tests/
make test-cov             # with coverage (term + xml)
pytest tests/unit/core/test_foo.py::TestClass::test_method   # single test
pytest -m "not slow"      # skip slow tests
pytest -m integration     # run only one marker
pytest -n auto            # parallel (pytest-xdist is available)
```
Markers (defined in `pytest.ini`): `slow`, `integration`, `unit`, `regression`, `e2e`, `requires_gpu`, `requires_dgm`, `requires_openevolve`.

Format / lint / type-check (line length **100**, black with `skip-string-normalization`):
```bash
make format        # black . && isort .
make type-check    # mypy evoseal/   (config in mypy.ini, not pyproject)
make check         # check-format + lint + type-check + test  (run before pushing)
```
Note: the `make lint` target has a shell typo in the Makefile; if it fails, run the linters directly: `flake8 evoseal tests/` and `pylint evoseal/` (or `ruff check evoseal/`).

## Conventions

- **Conventional Commits** are required (`feat:`, `fix:`, `docs:`, …); `commitizen` is configured. PRs target `main`.
- **Do not include `Co-Authored-By:` trailers in commit messages.** This applies to all assistant-generated commits, including those produced by Claude Code or any other AI tool. Commit attribution stays with the human author. Boilerplate trailers add noise to the history without conveying meaningful authorship and have been retroactively stripped from past commits.
- **English-only:** all `Plans.md` content (headers, table columns, task descriptions, status markers) must be in English — use `cc:done` / `cc:wip`, never `cc:完了` / `cc:WIP`. All harness output and documentation must be in English. This applies strictly to tracked files.
- The local runtime env file is `.evoseal.env` (gitignored); `.evoseal.env.template` is the committed reference.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

Tradeoff: These guidelines bias toward caution over speed. For trivial tasks, use judgment.

1. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs.

Before implementing:

State your assumptions explicitly. If uncertain, ask.
If multiple interpretations exist, present them - don't pick silently.
If a simpler approach exists, say so. Push back when warranted.
If something is unclear, stop. Name what's confusing. Ask.
2. Simplicity First
Minimum code that solves the problem. Nothing speculative.

No features beyond what was asked.
No abstractions for single-use code.
No "flexibility" or "configurability" that wasn't requested.
No error handling for impossible scenarios.
If you write 200 lines and it could be 50, rewrite it.
Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

3. Surgical Changes
Touch only what you must. Clean up only your own mess.

When editing existing code:

Don't "improve" adjacent code, comments, or formatting.
Don't refactor things that aren't broken.
Match existing style, even if you'd do it differently.
If you notice unrelated dead code, mention it - don't delete it.
When your changes create orphans:

Remove imports/variables/functions that YOUR changes made unused.
Don't remove pre-existing dead code unless asked.
The test: Every changed line should trace directly to the user's request.

4. Goal-Driven Execution
Define success criteria. Loop until verified.

Transform tasks into verifiable goals:

"Add validation" → "Write tests for invalid inputs, then make them pass"
"Fix the bug" → "Write a test that reproduces it, then make it pass"
"Refactor X" → "Ensure tests pass before and after"
For multi-step tasks, state a brief plan:

1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.

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

**Note:** This project uses **`uv`** as its package manager and task runner (not `pip`). All Python commands should use `uv run`.

Install (editable, with dev + test tooling):
```bash
uv sync
git submodule update --init --recursive
pre-commit install && pre-commit install --hook-type pre-push
```

Tests (pytest, `asyncio_mode = strict`, `testpaths = tests`):
```bash
uv run pytest tests/                          # Run all tests
uv run pytest tests/unit/core/test_foo.py::TestClass::test_method   # Single test
uv run pytest -m "not slow"                   # Skip slow tests
uv run pytest -m integration                  # Run only one marker
uv run pytest -n auto                         # Parallel (pytest-xdist)
```
Markers (defined in `pytest.ini`): `slow`, `integration`, `unit`, `regression`, `e2e`, `requires_gpu`, `requires_dgm`, `requires_openevolve`.

Format / lint / type-check (line length **100**, black with `skip-string-normalization`):
```bash
uv run black evoseal tests/
uv run isort evoseal tests/
uv run mypy evoseal/                          # (config in mypy.ini, not pyproject)
uv run ruff check evoseal/                    # Modern linter (preferred over flake8/pylint)
```

## Conventions

- **Conventional Commits** are required (`feat:`, `fix:`, `docs:`, …); `commitizen` is configured. PRs target `main`.
- **Do not include `Co-Authored-By:` trailers in commit messages.** This applies to all assistant-generated commits, including those produced by Claude Code or any other AI tool. Commit attribution stays with the human author. Boilerplate trailers add noise to the history without conveying meaningful authorship and have been retroactively stripped from past commits.
- **English-only:** all `Plans.md` content (headers, table columns, task descriptions, status markers) must be in English — use `cc:done` / `cc:wip`, never `cc:完了` / `cc:WIP`. All harness output and documentation must be in English. This applies to tracked files **and** to conversational/chat output — harness skill templates (e.g. `claude-code-harness:*`) are often written in Japanese internally, but any text quoted or adapted from them into a response to the user must be translated to English before sending, not copied verbatim.
- The local env file is `.env` (gitignored) — put API keys and `EVOSEAL_*` settings there. Do not commit it.

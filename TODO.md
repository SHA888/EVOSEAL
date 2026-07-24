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

### Critical Bugs Found in Whole-Repo Code Review (2026-07-22)

> Full-repo review (`origin/main`, 9 parallel subsystem agents + 4 deep re-verification passes). Items below are read-confirmed against source, not speculative.

- [x] **Checkpoint identifiers/paths allow directory traversal — attacker-controlled arbitrary file write** _(done 2026-07-22, PR #74, commit 4975940)_
  - `evoseal/core/checkpoint_manager.py`: `create_checkpoint()` (line 100), `restore_checkpoint()` (line 236), `get_checkpoint_path()` (line 393) all build `self.checkpoint_dir / f"checkpoint_{version_id}"` with zero validation of `version_id`. A `version_id` like `"../../../../etc/cron.d/evil"` resolves outside `checkpoint_dir` entirely (verified with `os.path.normpath`)
  - Same file, lines 119-122: `changes` dict keys (`file_path`, attacker-controlled via evolution-pipeline results) are joined onto `checkpoint_path` unsanitized and written with attacker-controlled content — full arbitrary path + arbitrary bytes write primitive
  - Sibling bug, same class: `evoseal/core/version_tracker.py:265-271` — public `checkpoint_name` parameter (via `evoseal/core/experiment_integration.py:369`) concatenated into a checkpoint id with no sanitization
  - `EditScopeValidator` (`evoseal/core/edit_scope_validator.py`), which implements the correct `.resolve()` + `relative_to()` containment check, is **never called on this path** — `SafetyIntegration` holds instances of both `CheckpointManager` and `EditScopeValidator` but never bridges them
  - Reachable from the live self-modification loop via `SafetyIntegration.create_safety_checkpoint()` → `checkpoint_manager.create_checkpoint()`
- [x] **`ImprovementValidator` is non-functional; the pipeline's actual validation gate is a hardcoded stub that always passes** _(done 2026-07-22, PR #76, commit e9f723c)_
  - `evoseal/core/improvement_validator.py:315-316` — `validate_improvement()` calls `self.metrics_tracker.get_metrics_by_id()`, but `MetricsTracker` only defines a private `_get_metrics_by_id` — every call raises `AttributeError`
  - Same file, line 424 references an undefined `message` variable (`NameError` if Bug 1 were fixed); the method also has no `return` statement on its success path (always returns `None`)
  - Irrelevant in practice: `grep` shows `validate_improvement()` is called from nowhere in production code (only the module's own `__main__` demo). `EvolutionPipeline` instantiates the validator (`evolution_pipeline.py:152`) but never calls it
  - The actual gate wired into the pipeline is `evoseal/core/evolution_pipeline.py:919-922`: `async def _validate_improvement(...): # TODO: Implement improvement validation logic \n return True` — unconditionally returns `True`, feeding directly into `should_continue`. A self-modification that doubles test failures and triples runtime is accepted as a validated improvement, every time
- [x] **`EvolutionPipeline.__init__` never awaits its own resilience/circuit-breaker setup — every pipeline instance silently runs with zero resilience protection** _(done 2026-07-22, PR #77, commit dba2aa4)_
  - `evoseal/core/evolution_pipeline.py:169` — `self._init_resilience_mechanisms()` is called from sync `__init__`, but the target (`evolution_pipeline.py:207`) is `async def`. The call just constructs and discards a coroutine (Python emits an unawaited-coroutine warning, no exception)
  - Silently skips: starting `resilience_manager` monitoring, registering all component circuit breakers, the pipeline recovery strategy, degradation/fallback handlers, isolation policies, and the escalation handler — no error surfaced
- [x] **`run_evolution_cycle` always raises `TypeError` on its success path (malformed `Event` construction)** _(done 2026-07-22, PR #77, commit dba2aa4)_
  - `evoseal/core/evolution_pipeline.py:450-459` and `:463-468` — `Event(EventType.EVOLUTION_COMPLETED, {...})` passes only 2 positional args, but `Event` (`evoseal/core/events.py:129`, a dataclass) requires 3 (`event_type, source, data`) — `TypeError: Event.__init__() missing 1 required positional argument: 'data'`
  - The `except Exception` handler that's supposed to catch and report this constructs a second malformed `Event` for `ERROR_OCCURRED` (lines 464-468), which raises its own `TypeError` while handling the first — the second exception is what actually propagates
  - Every documented example that calls the plain (non-`_with_safety`) cycle hits this on normal completion, no failure required. `run_evolution_cycle_with_safety` (line 474) has the identical malformed-`Event` bug at lines 676-680/700-707
  - Secondary: `self.event_bus.publish(...)` is `async def` but called without `await` in these same blocks — even once `Event(...)` is fixed, these publishes would silently no-op rather than actually emitting the event
- [x] **`run_training_cycle` can never execute — readiness check always sees itself as "already running"** _(done 2026-07-22, PR #78, commit ab289bf)_
  - `evoseal/fine_tuning/training_manager.py:204` sets `self.current_training = {...}` *before* calling `check_training_readiness()` (line 214), which treats any non-`None` `self.current_training` as "training in progress" (lines 105-108) and aborts
  - Every call to `run_training_cycle` fails at the readiness-check phase — the entire automated fine-tuning pipeline can never run. Same ordering-bug class as the `deploy_version` supersede-before-confirm bug fixed in PR #72 (commit `dd8364fa`)
- [x] **SEAL `BaseEditStrategy.apply()` corrupts files when `original_text` is empty** _(done 2026-07-22, PR #79, commit 729173b)_
  - `evoseal/integration/seal/self_editor/strategies/base_strategy.py:53-54` — `if suggestion.original_text in content: return content.replace(suggestion.original_text, suggestion.suggested_text)`. Since `"" in content` is always `True`, an empty `original_text` hits `content.replace("", suggested_text)`, which splices the replacement before *every character* of the file
  - `documentation_strategy.py` deliberately constructs `original_text=""` (meaning "insert here") at 4 call sites: lines 665, 698, 754, 1000
  - Not hit by the current production path — `SelfEditor.apply_edit()` (`self_editor.py`) already guards against empty `original_text` correctly and is what production calls — but `BaseEditStrategy.apply()` is still public API, is called directly in `tests/unit/seal/self_editor/strategies/test_code_style_strategy.py:64`, and is the pattern documented in `self_editor/README.md:69`
  - Fix belongs in `base_strategy.py:53` — reject/special-case empty `original_text` instead of relying on substring containment

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

- [ ] **Tier 2 container isolation (DEFERRED — trigger-gated per ADR 0001 section 5; implement only if a trust-model trigger fires, e.g. untrusted generation, multi-tenant host)**

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
- [x] **Fix `test_authentication_handling` making a real unmocked network call** _(done 2026-07-22)_ — `tests/version_control/test_advanced_operations.py:187` now mocks `CmdGit._run_git_command` to simulate an authentication failure instead of calling the real GitHub API. Eliminates the hang in interactive TTYs (credential prompt) and stray directory on failure.

### Cost Management

- [x] **Add token/cost estimation** _(done — Plans.md 2.9, commit 8538321)_
  - Log token usage per evolution cycle (prompt + completion tokens)
  - Add a `evoseal estimate-cost --iterations N` command or config option
  - Document rough cost expectations in README (e.g., "10 iterations ≈ X tokens ≈ $Y with GPT-4")
- [x] **Add configurable token budget / API rate limits** _(done — Plans.md 2.10, commit 0c49b42)_
  - Allow users to set a max spend per run in config
  - Graceful stop when budget is exhausted

### Safety & Correctness Bugs Found in Whole-Repo Code Review (2026-07-22)

- [x] **Model-safety validator can be defeated by an incidental safety word** _(done 2026-07-23, fix/safety-validator-bypass)_
  - `evoseal/fine_tuning/model_validator.py:432-454` — `_is_safe_response` returned `has_safety or not has_unsafe`. A response containing both an unsafe instruction and any safety-sounding word (e.g. `"Sorry, but here's how: rm -rf /"`) was classified safe regardless of the unsafe content. Fixed to `return not has_unsafe`; added 7 regression tests in `test_model_validator.py`
- [ ] **Path traversal in git-file read/write helpers**
  - `evoseal/utils/version_control/cmd_git.py:1130-1134` (`get_file_content`) and `:1176-1177` (`write_file_content`) — `full_path = self.repo_path / file_path` with no containment check. `pathlib` resolves an absolute RHS by discarding the LHS (`Path('/repo') / '/etc/passwd'` → `/etc/passwd`), and `..` segments aren't normalized either. Any caller passing an absolute or `..`-containing `file_path` (e.g. a model-generated patch) causes arbitrary file read/write outside the repo
- [ ] **Monitoring dashboard has no authentication and permissive CORS-with-credentials**
  - `evoseal/services/monitoring_dashboard.py:75-91` (`setup_cors`) — every route gets `aiohttp_cors.ResourceOptions(allow_credentials=True, allow_headers="*", allow_methods="*", expose_headers="*")` on a wildcard origin (CWE-942). No auth on any HTTP or WebSocket endpoint (`/api/status`, `/api/metrics`, `/api/report`, `/ws`), which return internal operational data (data paths, config, error strings). Defaults to `localhost` (limits blast radius today) but nothing prevents/warns against a `0.0.0.0` deploy, at which point this is unauthenticated remote information disclosure

### CI/CD & Release Pipeline Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **Release pipeline is broken** _(exact failure mode needs re-verification — flagged by initial review pass, not yet deep-dived)_
- [ ] **Some `workflow_run` triggers reference the wrong workflow name**, so dependent workflows don't actually fire when expected
- [ ] **A `requirements/` directory referenced by tooling/CI does not exist**
- [ ] **Security-scan gate is defeated by `continue-on-error: true`**, so a failing security check doesn't actually block anything

### DGM/OpenEvolve Adapter Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **`evoseal/integration/dgm/` + `dgmr/` and `evoseal/integration/oe/` + `openevolve/` look like duplicated/forked adapter implementations that have drifted apart** — needs a decision on which is canonical and whether the other should be removed or reconciled
- [ ] **DGM/OpenEvolve job runner reports failed jobs as successful** _(exact file:line needs re-verification — flagged by initial review pass, not yet deep-dived)_

### CLI Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **`evoseal export` fabricates results instead of reporting real failures** _(exact file:line needs re-verification)_
- [ ] **Several `evoseal pipeline` subcommands are stubs**, not implemented behavior _(exact file:line needs re-verification)_

### SEAL Subsystem Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **Knowledge retrieval in the SEAL subsystem is broken** _(exact file:line needs re-verification — flagged by initial review pass, not yet deep-dived)_

---

## 🟡 P2 — Medium Priority

### Close the bidirectional co-evolution loop

> **Audit finding (2026-07-19, reverified 2026-07-21):** The Phase 3 components/modules exist, but the bidirectional
> feedback edges are not wired. The daemon simulates evolution instead of running it, model validation tests the
> baseline instead of the fine-tuned model, deployment is a JSON registry with no serving-layer integration, and the
> generator never consults the fine-tuning registry. Closing the loop requires the dependency order below — each
> step builds on the previous one landing first.

- [x] **1. Merge CLI wiring for `evoseal start evolution`** _(done 2026-07-21)_ — added `evoseal start evolution`, which constructs and runs `ContinuousEvolutionService` (the `api`/`worker` stubs are untouched); prints an explicit research-stage notice since the loop itself is still open per the gaps below. Along the way, fixed a pre-existing bug in `evoseal/cli/__init__.py` that clobbered the app's `--version` callback with a bare `lambda version: None`, breaking dispatch for every CLI subcommand invocation with arguments (the only prior CLI-dispatch test was a false positive that happened to pass regardless)
- [x] **2. Wire daemon to real EvolutionPipeline** _(done 2026-07-21)_ — `continuous_evolution_service.py` `_run_evolution_cycle` now constructs and invokes `EvolutionPipeline.run_evolution_cycle()` instead of simulating; accepts optional `pipeline` param, lazy-inits if not injected
- [x] **FIX: training call used nonexistent method** _(done 2026-07-19, commit fix/training-method-name-bug, on `main` as of 81156b3)_ — `continuous_evolution_service.py:234` called `training_manager.start_training()` which did not exist; changed to `run_training_cycle()` and fixed `validation_passed` → `validation_results.passed`
- [x] **3. validate_model must serve the fine-tuned model, not baseline** _(done 2026-07-21)_ — all 5 test suites now use `model_path` when provided via `_resolve_model_for_validation()`; removed dead `TRANSFORMERS_AVAILABLE` import block. **Known limitation:** `model_path` must be an Ollama-resolvable model tag — directory paths from `register_version()` will surface an Ollama error until item 4 (real deployment) lands.
- [x] **4. Implement real model deployment** — `version_manager.register_version` only copies weights + sets `current_version` in a JSON registry (no Modelfile / `ollama create` / symlink); need actual deployment so the serving layer can load the model
- [ ] **5. Generation must consult the fine-tuning registry** — `version_manager.get_current_version()` has zero callers — the generator (`providers/local_models.py resolve_model`, which currently just reads raw installed Ollama tags) must consult the registry instead so the deployed fine-tuned model actually gets used
- [ ] **6. Wire bidirectional_manager to orchestrate the full loop** — `bidirectional_manager.py`'s docstring promises evolve → collect → train → deploy → repeat, but the class only implements reporting/statistics methods (`get_evolution_status`, `get_evolution_history`, `generate_evolution_report`); no method actually drives the sequence end-to-end
- [ ] **Add end-to-end bidirectional loop test** — exercise the full cycle: collect → train → validate → deploy → regenerate; no such test exists today (write once steps 1–6 land)

### Phase 3 (Bidirectional Evolution) Documentation

- [x] **Write architecture doc for Devstral co-evolution** _(done 2026-07-21)_
  - How does the bidirectional feedback loop work?
  - What prevents the two systems from diverging?
  - What metrics determine "improvement" in the bidirectional context?
  - Added as `docs/architecture/bidirectional_evolution.md`
- [x] **Add sequence diagram** showing the Devstral ↔ EVOSEAL message flow _(done 2026-07-23)_ — Mermaid sequence diagram added to `docs/architecture/bidirectional_evolution.md` covering all 5 phases (evolution → training → deploy → generate → orchestrate), with solid/dashed arrows distinguishing implemented vs. gap paths and a status table

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
- [ ] **Add tests for safety-decision orchestration** _(found 2026-07-22 whole-repo review)_ — the code paths behind the checkpoint/ImprovementValidator/resilience-init bugs above have zero regression test coverage today, which is plausibly why they shipped unnoticed

### Medium-Priority Bugs Found in Whole-Repo Code Review (2026-07-22)

- [ ] **`bidirectional_manager.py` state fields are never mutated** — `self.stats`, `self.evolution_history`, `self.is_running`, `self.last_check_time` are set in `__init__` but nothing in the codebase ever updates them (confirmed via repo-wide grep); `continuous_evolution_service.py` maintains its own separate loop state instead. `get_evolution_status()`/`generate_evolution_report()` always report zero cycles and `is_running=False` even while the loop actively runs
- [ ] **`version_manager.py` registry file has no atomic write** — `_save_registry()` (lines 70-77, PR #72 branch) writes directly via `open(...,"w")` + `json.dump`; a crash/kill mid-write leaves a truncated file, and `_load_registry()` silently resets to an empty registry on parse failure, losing all version history
- [ ] **`version_manager.py` has no locking around concurrent registry mutation** — overlapping `register_version`/`deploy_version` calls can interleave writes to `self.registry["versions"]`, risking lost updates or an inconsistent `current_version`
- [ ] **`model_fine_tuner.py:160-178` uses `trust_remote_code=True`** on both `AutoTokenizer`/`AutoModelForCausalLM.from_pretrained`, combined with a fallback (`_resolve_hf_base_model()`, lines 107-120) that uses `model_name` verbatim as an HF repo id for unknown families — a bad config value or env var (`EVOSEAL_CODER_MODEL`) can execute arbitrary remote code locally. `# nosec B615` suppresses the linter, not the risk
- [ ] **`provider_manager.py` treats unhealthy providers as healthy when called from a running event loop** — `get_best_available_provider()` (lines 100-111) and `list_providers()` (lines 196-201) create a health-check task via `loop.create_task(...)` but never await/consume it, then unconditionally set `is_healthy = True`, discarding the real result; the orphaned task can also produce unretrieved-exception warnings
- [ ] **`agentic_system.py:28` logger bypasses the logging handler hierarchy** — `Logger("AgenticSystem")` is instantiated directly instead of via `logging.getLogger(name)`; `self.parent` stays `None`, no handlers attach, and all INFO-level agent-orchestration logs (create/destroy, message send, task assignment) are silently dropped by default
- [ ] **`agentic_workflow_agent.py:14` couples to a private API and can crash inside a running event loop** — `WorkflowAgent.act` calls `self.engine._execute_step(...)`, a `_`-prefixed private method of `WorkflowEngine` that internally does `asyncio.run(...)`; invoking a `WorkflowAgent` through the async entry points while already inside a running event loop raises `RuntimeError: asyncio.run() cannot be called from a running event loop`
- [ ] **`continuous_evolution_service.py:107-115` registers process-wide signal handlers from `__init__`** — `signal.signal()` only works on the main thread (raises `ValueError` if constructed off-thread), and the handler's `asyncio.create_task(self.shutdown())` requires a running event loop in the current thread at signal-time; also clobbers whatever signal handlers an embedding application had installed, since this fires on mere construction, not `start()`
- [x] **`models/experiment.py:256-260` references an undefined name `FieldValidationInfo`** — never imported anywhere in the module (only `field_validator`/`model_validator` are imported from pydantic); only survives today because `from __future__ import annotations` defers evaluation. Breaks under `typing.get_type_hints()`, strict mypy/pyright, or Sphinx autodoc. Correct type is `pydantic.ValidationInfo`
- [ ] **`models/system_config.py:33-39` `from_yaml` doesn't validate the loaded YAML is a dict** — an empty file yields `None`, a scalar/list document yields a non-dict; `self.config` is set as-is and the first `get()`/`validate()` call raises an opaque `TypeError` instead of a clear config error
- [ ] **`cmd_git.py:1754` `_find_referenced_by` passes a nonexistent `ref` kwarg** — calls `self._run_git_command(cmd, ref=ref)`, but `GitInterface._run_git_command` has no `ref` parameter; raises `TypeError` any time `find_file_references()` is called with an explicit ref

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

### Low-Priority / Hygiene Issues Found in Whole-Repo Code Review (2026-07-22)

- [x] **`cmd_git.py:977` `tag()` builds a malformed argv token** — `cmd.append("-s" if not sign_key else f"-u {sign_key}")` appends `"-u <key>"` as one argv element instead of `["-u", sign_key]`; since commands run via `subprocess.run(list, shell=False)`, git receives one malformed token and signed-tag-with-explicit-key fails
- [x] **`git_interface.py` credential-helper config is broken** _(done 2026-07-24)_ — sets `credential.helper` to the literal string `'cache --timeout=300'` including the quotes (no shell involved, so they're taken literally), via two non-`--add` `--local` sets where the second silently overwrites the first with a bogus value — HTTPS credential caching silently doesn't work. Fixed to a single `config --local credential.helper "cache --timeout=300"` call with no spurious quotes
- [ ] **Stray `evoseal/utils/validator.py.bak`** — a 1132-line backup committed to the repo tree (not gitignored), diverged from `validator.py`; risk of editing the wrong file
- [ ] **`evoseal/utils/testing/environment.py:180`** — `suffix: str = None` type-annotation mismatch (should be `Optional[str]`)
- [ ] **`providers/ollama_provider.py:98-136`** — `submit_prompt` has no retry/backoff on transient network failures despite being the sole retry/timeout surface for local model calls
- [ ] **`providers/local_models.py:103-119`** — `_query_installed_models` is `lru_cache`d indefinitely with no TTL; a newly pulled/removed Ollama model isn't picked up until something explicitly calls `clear_model_cache()`
- [ ] **`model_fine_tuner.py:122-137`** — `_check_gpu_availability()` is defined but never called; despite the module docstring claiming "Requires a CUDA GPU," `initialize_model()` silently proceeds on CPU instead of failing fast
- [ ] **`model_fine_tuner.py:220,240`** — `example['instruction']`/`example['output']` direct dict access with no `.get()`; a malformed training example raises `KeyError` surfaced only as a generic error string instead of a clear validation message
- [ ] **`models/code_archive.py:127-149`** — `__init__` manually re-implements every default already provided by `Field(default_factory=...)`, a drift hazard (two sources of truth for the same defaults)
- [ ] **`evoseal/agents/agentic_system_example.py:7`** — `from evoseal.agentic_system import ...` is the wrong module path (actual: `evoseal.agents.agentic_system`); the example fails immediately with `ModuleNotFoundError`

### Documentation Polish

- [x] **Add architecture decision records (ADRs)** _(done 2026-07-19)_
  - Why MAP-Elites over other evolutionary strategies?
  - Why SEAL over pure prompt engineering?
  - Why Git-based version control for self-edits?
- [x] **Consolidate ADR 0001 into `docs/adr/`** _(done 2026-07-19)_
  - Moved `docs/safety/sandbox_design.md` → `docs/adr/0001-isolation-strategy.md` so all
    ADRs live in one directory; updated the index and all inbound references.
- [x] **Refresh ADR 0001 to reflect implemented Tier 1 safety state** _(done 2026-07-19)_
  - Updated tier table, "Current state" block, operator guidance, and Section 6 to reflect that Tier 1 (tasks 2.13–2.15) is now implemented and default-on

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
| 🔴 P0    | 11    | 11   | Original 5 complete; all 6 critical bugs from 2026-07-22 whole-repo review fixed (PRs #74, #76-#79) |
| 🟠 P1    | 24    | 11   | Original safety/integration items done; +12 high-priority bugs from 2026-07-22 review |
| 🟡 P2    | 29    | 6    | Co-evolution loop gaps (7 items, 6 done) + existing P2 + 12 medium bugs from 2026-07-22 review |
| 🟢 P3    | 24    | 8    | Makefile, pre-commit, Docker, ADRs, ADR refresh complete; +10 hygiene items from 2026-07-22 review |
| **Total** | **88** | **35** | |

> Update this table as you complete items. Recommended flow: P0 → P1 → P2 → P3.
>
> Items marked _(inspired by OpenClaw)_ are patterns borrowed from the OpenClaw project.
> See comparative analysis for full context on what to adopt vs. what to avoid.

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

- [x] **Fix missing `configs/safety.yaml` and `config/` vs `configs/` path discrepancy** _(done 2026-07-27)_
  - Multiple safety-critical modules reference `configs/safety.yaml` (plural `configs/`) as the immutable safety configuration, but neither that file nor a `configs/` directory exists
  - Only `config/` (singular) exists, containing `budget.yaml`, `logging.yaml`, etc. — no `safety.yaml`
  - Referenced by: `evoseal/core/edit_scope_validator.py` (lines 27, 52, 80), `evoseal/core/safety_integration.py` (line 286), `evoseal/core/testrunner.py` (line 652), `evoseal/cli/commands/doctor.py` (line 181), and multiple safety tests
  - Impact: `evoseal doctor` reports 'safety.yaml not found'; edit-scope allowlist references a nonexistent path; safety tests assert against a file that does not exist on disk
  - Created `configs/safety.yaml` with defaults for edit-scope enforcement, regression detection thresholds, checkpoint/rollback policy, and sandboxed test execution. Code already references `configs/safety.yaml` (plural) consistently — no path changes needed. Verified: `check_safety_yaml()` returns well-formed, `pytest tests/safety/ tests/unit/test_doctor_command.py` passes (54 tests), `evoseal doctor` check passes.

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
- [x] **Path traversal in git-file read/write helpers** _(done 2026-07-26)_ — `get_file_content` and `write_file_content` now resolve the constructed path and verify it stays within `repo_path` via `is_relative_to()`, raising `GitError` on traversal. 3 new test functions cover `..` traversal, absolute paths, nested traversal, and legitimate subdirectory ops.
- [x] **Monitoring dashboard has no authentication and permissive CORS-with-credentials** _(done 2026-07-29)_
  - `evoseal/services/monitoring_dashboard.py:75-91` (`setup_cors`) — every route got `aiohttp_cors.ResourceOptions(allow_credentials=True, allow_headers="*", allow_methods="*", expose_headers="*")` on a wildcard origin (CWE-942). No auth on any HTTP or WebSocket endpoint (`/api/status`, `/api/metrics`, `/api/report`, `/ws`), which return internal operational data (data paths, config, error strings). Defaults to `localhost` (limits blast radius today) but nothing prevented/warned against a `0.0.0.0` deploy, at which point this was unauthenticated remote information disclosure
  - Fixed: CORS origins now default to the dashboard's own host:port (not `*`); binding to `0.0.0.0` logs a security warning; added optional `auth_token` parameter — when set, all `/api/*` and `/ws` requests must present `Authorization: Bearer <token>` (WebSocket clients can pass `?token=`); the HTML dashboard page is not gated. Wildcard `*` origin explicitly disables `allow_credentials` per CORS spec. 14 new unit tests cover auth accept/reject, CORS defaults, wildcard warning, and constructor params

### CI/CD & Release Pipeline Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **Release pipeline is broken** _(exact failure mode needs re-verification — flagged by initial review pass, not yet deep-dived)_
- [x] **Some `workflow_run` triggers reference the wrong workflow name** _(done 2026-08-01)_ — `cleanup.yml`, `docs.yml`, `pre-release.yml`, and `codeql-analysis.yml` all referenced `workflows: ["CI"]` but the actual CI workflow name is `"CI/CD Pipeline"`; updated all four to match. Only `release.yml` already had the correct reference.
- [x] **A `requirements/` directory referenced by tooling/CI does not exist** _(done 2026-08-01)_ — `docs.yml` cached and installed from `requirements/docs.txt` which didn't exist; replaced with `uv pip install --system -e ".[docs]"` matching how the main CI job installs doc dependencies (the `[docs]` extras are defined in `pyproject.toml`). No other workflows reference `requirements/`.
- [x] **Security-scan gate is defeated by `continue-on-error: true`** _(done 2026-08-01)_ — removed `continue-on-error: true` from the `security` job in `ci.yml` so bandit/safety failures now properly block the `build` and `container` downstream jobs. The remaining `continue-on-error: true` on the mypy lint step is intentional (type checking is advisory).

### DGM/OpenEvolve Adapter Issues Found in Whole-Repo Code Review (2026-07-22)

- [ ] **`evoseal/integration/dgm/` + `dgmr/` and `evoseal/integration/oe/` + `openevolve/` look like duplicated/forked adapter implementations that have drifted apart** — needs a decision on which is canonical and whether the other should be removed or reconciled
- [x] **DGM/OpenEvolve job runner reports failed jobs as successful** _(done 2026-08-07, refined per review feedback)_ — both `dgmr/dgm_adapter.py` `_advance_generation()` and `oe/openevolve_adapter.py` `_evolve_remote()` broke out of the poll loop on `status == "failed"` but then unconditionally fetched the result and returned `{"success": True}`. Fixed both to check the final status after the poll and return `success: False` with the error message when the job failed. Inverted check to `!= "completed"` so any non-terminal state (timeouts, unknown statuses) is also treated as failure. Added regression tests in `test_dgm_adapter_remote.py` and `test_openevolve_adapter_remote.py`.

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
- [x] **5. Generation must consult the fine-tuning registry** _(done 2026-07-24, PR #73)_ — `default_manager()` now calls `ModelVersionManager().get_current_version()` and passes the deployed model's Ollama tag as `registry_model` to `CoevolutionManager`, so the coder provider prefers the fine-tuned model over raw family-based discovery
- [x] **6. Wire bidirectional_manager to orchestrate the full loop** _(done 2026-07-23)_ — added `run_loop_cycle()` that drives one full iteration: check training readiness → run training cycle → deploy the improved model (when validation passes) → record results. Also added `_deploy_trained_model()` helper and `_record_cycle()` to update the previously-stale `stats`/`evolution_history`/`is_running`/`last_check_time` fields. 9 new unit tests cover: skip-when-not-ready, training failure, full success, validation-fail-skip-deploy, deploy failure, exception handling, state mutation, missing-current-version, and missing-validation-results.
- [x] **Add end-to-end bidirectional loop test** _(done 2026-07-24, revised 2026-07-25, PR #89)_ — `tests/integration/test_bidirectional_loop_e2e.py` wires real `BidirectionalEvolutionManager` + `TrainingManager` + `EvolutionDataCollector` + `ModelVersionManager`, mocking only the true external boundaries (GPU fine-tuning, Ollama validation/deploy). 5 tests: full success cycle, readiness skip, training failure, validation-fail-skip-deploy, and two sequential cycles with stat accumulation. Writing this test surfaced 4 real bugs in the collect→train path that were previously invisible because every existing unit test mocked past them — see the entry below.
- [x] **FIX: collect→train path had 4 latent bugs invisible to mock-heavy unit tests** _(done 2026-07-25)_ — found while making the e2e test above exercise real components instead of mocking around them: (1) `TrainingManager.check_training_readiness()` read a `training_candidates` key from `EvolutionDataCollector.get_statistics()` that the real implementation never returns, so readiness could never pass with a real collector — now uses `len(get_training_candidates(min_samples=...))`; (2) `TrainingManager.prepare_training_data()` called `data_collector.get_recent_results()`, which didn't exist — added it to `EvolutionDataCollector`; (3) the same method then called `TrainingDataBuilder.build_training_dataset()`, which also didn't exist (real method is the synchronous `build_training_data()`) — rewrote `prepare_training_data()` against the real `TrainingDataBuilder` API (`build_training_data()` + `save_training_data()` + `get_statistics()`); (4) `TrainingManager.__init__` defaulted to `ModelVersionManager(versions_dir=output_dir/"versions")` while `coevolution_manager.default_manager()` defaulted to bare `ModelVersionManager()` (`models/versions`) — genuinely different paths in production (traced `ContinuousEvolutionService` → `BidirectionalEvolutionManager` → `TrainingManager`), meaning the "regenerate" step would never see a model deployed by the real training pipeline; unified both on a new `version_manager.DEFAULT_VERSIONS_DIR` constant.
- [x] **`ModelFineTuner.fine_tune_model()`'s real (non-fallback) path expects an HF `datasets.load_from_disk()`-compatible directory, but `TrainingDataBuilder.save_training_data()` only produces alpaca/chat/jsonl JSON files** — a genuine format mismatch, but only reachable when `peft`/`transformers` are installed and the real (non-fallback) training path runs; this environment always runs in fallback mode so it wasn't hit while closing the loop above. Fixed by adding `format_type="huggingface"` to `TrainingDataBuilder.save_training_data()` and updating `TrainingManager.prepare_training_data()` to use it; `fine_tune_model` now receives a proper HF dataset directory via `load_from_disk()`. **Follow-up (review caught the load_from_disk() fix only moved the crash downstream):** the HF export writes raw `instruction`/`input`/`output` string columns, but `Trainer` + `DataCollatorForLanguageModeling` require pre-tokenized `input_ids` — `trainer.train()` would still fail. Added `ModelFineTuner._tokenize_if_needed()`, called right after `load_from_disk()`, which tokenizes when `input_ids` is absent and is a no-op otherwise

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

- [x] **Increase unit test coverage for `core/` modules**
  - `controller.py`, `evaluator.py`, `selection.py`, `version_database.py`
  - Target: meaningful coverage on core logic paths, not just line count
- [x] **Add regression test for config validation**
  - Malformed YAML, missing required sections, type mismatches
- [x] **Add test for checkpoint save/restore** _(done 2026-07-30)_
  - Interrupt mid-evolution, restore from checkpoint, verify state consistency
  - 13 tests in `tests/unit/core/test_checkpoint_save_restore.py`: basic round-trip, metadata preservation, integrity hash verification, tamper detection, tamper-restore integration, nonexistent restore error, multi-checkpoint isolation, list/delete, target-directory clearing (protected dirs preserved), size reporting, system-state capture, and mid-evolution interruption recovery
- [x] **Add tests for safety-decision orchestration** _(done 2026-08-01)_ — added 7 regression tests for `EvolutionPipeline._validate_improvement`, the actual validation gate in the evolution loop. Covers: first-iteration acceptance, improvement acceptance, regression rejection, exception-during-validation fail-closed, malformed validator response rejection, and test_type passthrough. Tests also caught two latent bugs in the method: `StructuredLogger` doesn't support `%s`-style args (used in `logger.info()`) and has no `.exception()` method (used in error path) — both fixed

### Medium-Priority Bugs Found in Whole-Repo Code Review (2026-07-22)

- [x] **`bidirectional_manager.py` state fields are never mutated** _(done 2026-07-23)_ — fixed by `run_loop_cycle()` in item #6 above; `stats`, `evolution_history`, `is_running`, and `last_check_time` are now all mutated each cycle.
- [x] **`version_manager.py` registry file has no atomic write** — `_save_registry()` (lines 70-77, PR #72 branch) writes directly via `open(...,"w")` + `json.dump`; a crash/kill mid-write leaves a truncated file, and `_load_registry()` silently resets to an empty registry on parse failure, losing all version history
- [x] **`version_manager.py` has no locking around concurrent registry mutation** _(done 2026-08-01)_ — overlapping `register_version`/`deploy_version` calls can interleave writes to `self.registry["versions"]`, risking lost updates or an inconsistent `current_version`. Fixed with `asyncio.Lock` + impl pattern (public methods acquire lock, delegate to `_impl` to avoid reentrant deadlock)
- [x] **`model_fine_tuner.py:160-178` uses `trust_remote_code=True`** _(done 2026-07-31)_ — changed both `AutoTokenizer` and `AutoModelForCausalLM.from_pretrained` calls to `trust_remote_code=False` (the safe default). The `# nosec B615` suppression comments remain because B615 flags missing `revision=`, not `trust_remote_code`; revision pinning is left to the caller.
- [x] **`provider_manager.py` treats unhealthy providers as healthy when called from a running event loop** _(done 2026-07-28)_ — `get_best_available_provider()` (lines 100-111) and `list_providers()` (lines 196-201) create a health-check task via `loop.create_task(...)` but never await/consume it, then unconditionally set `is_healthy = True`, discarding the real result; the orphaned task can also produce unretrieved-exception warnings
- [x] **`agentic_system.py:28` logger bypasses the logging handler hierarchy** _(done 2026-07-26)_ — `Logger("AgenticSystem")` was instantiated directly instead of via `logging.getLogger(name)`; `self.parent` stayed `None`, no handlers attached, and all INFO-level agent-orchestration logs were silently dropped. Changed to `get_logger("AgenticSystem")` to participate in the handler hierarchy
- [x] **`agentic_workflow_agent.py:14` couples to a private API and can crash inside a running event loop** _(done 2026-07-28)_ — added public `WorkflowEngine.execute_step()` that detects a running event loop and offloads to a thread instead of re-entering `asyncio.run()`; `WorkflowAgent.act()` now calls the public method. Also added `act_async()` for callers already in an async context. 10 new unit tests cover: sync context, running-loop context, error propagation, missing component, and agent state tracking
- [x] **`continuous_evolution_service.py:107-115` registers process-wide signal handlers from `__init__`** _(done 2026-07-26)_ — `signal.signal()` only works on the main thread (raises `ValueError` if constructed off-thread), and the handler's `asyncio.create_task(self.shutdown())` requires a running event loop in the current thread at signal-time; also clobbers whatever signal handlers an embedding application had installed, since this fires on mere construction, not `start()`. Fixed by moving `_setup_signal_handlers()` call to `start()`, using `loop.call_soon_threadsafe()` instead of bare `asyncio.create_task()`, and restoring original handlers in `_cleanup()`
- [x] **`models/experiment.py:256-260` references an undefined name `FieldValidationInfo`** — never imported anywhere in the module (only `field_validator`/`model_validator` are imported from pydantic); only survives today because `from __future__ import annotations` defers evaluation. Breaks under `typing.get_type_hints()`, strict mypy/pyright, or Sphinx autodoc. Correct type is `pydantic.ValidationInfo`
- [x] **`models/system_config.py:33-39` `from_yaml` doesn't validate the loaded YAML is a dict** _(done 2026-07-24)_ — an empty file yields `None`, a scalar/list document yields a non-dict; `self.config` is set as-is and the first `get()`/`validate()` call raises an opaque `TypeError` instead of a clear config error
- [x] **`models/system_config.py` `from_yaml` doesn't catch `yaml.YAMLError` on malformed YAML syntax** — `yaml.safe_load()` raises `yaml.YAMLError` on invalid YAML (e.g. bad indentation, unclosed braces); the raw exception propagates without context about which file failed to parse
- [x] **`cmd_git.py:1754` `_find_referenced_by` passes a nonexistent `ref` kwarg** — calls `self._run_git_command(cmd, ref=ref)`, but `GitInterface._run_git_command` has no `ref` parameter; raises `TypeError` any time `find_file_references()` is called with an explicit ref

### Evolution Archive & Rollout _(inspired by OpenClaw patterns)_

- [x] **Structured improvement units in the evolution archive** _(done 2026-08-01)_
  - Each successful self-modification should be a self-contained, documented unit (not just a Git diff)
  - Include: description of change, metrics before/after, rollback instructions, and relevant config snapshot
  - Pattern: similar to OpenClaw's per-skill `SKILL.md` files — one doc per improvement that stands alone
  - Created `docs/improvement_units/` with README (format spec), TEMPLATE.md, and two example units from PRs #74 and #76
  - Updated `docs/index.md` with links to the new section
- [ ] **Progressive rollout gating for self-modifications**
  - [x] Design doc at `docs/architecture/progressive_rollout_gating.md` _(done 2026-08-02)_: three-stage promotion model (candidate → beta → stable) with configurable cycle threshold, automatic rollback on regression, and integration points for the evolution pipeline, continuous evolution service, and bidirectional manager
  - [ ] Implement the gating mechanism described in the design doc
  - Pattern: analogous to OpenClaw's development channels (stable/beta/dev with npm dist-tags)

---

## 🟢 P3 — Nice to Have

### Developer Experience

- [x] **Add a `Makefile`** _(already present)_
  - `make test`, `make format`, `make type-check`, `make check`, `make test-cov`
- [x] **Add pre-commit hooks** _(done 2026-06-04)_
  - ruff (lint + format), bandit, detect-secrets, hadolint, trufflehog, pytest fast-check
  - Config in `.pre-commit-config.yaml`; install with `pre-commit install`
- [x] **Add `CHANGELOG.md`** tracking releases
- [x] **Docker support** _(already present)_
  - `Dockerfile` (python:3.11-slim + uv) and `docker-compose.evoseal.yml`
  - Dashboard on port 9613; volumes for checkpoints, data, reports, benchmarks
- [x] **Adopt workspace prompt file conventions** _(done 2026-07-30)_
  - Create a standard file layout for the evolution workspace: e.g., `AGENT.md` (agent identity/constraints), `EVOLUTION.md` (current evolution goals/state), `SAFETY.md` (safety invariants)
  - Makes the system self-documenting and easier for contributors to understand agent behavior at any point

### Low-Priority / Hygiene Issues Found in Whole-Repo Code Review (2026-07-22)

- [x] **`cmd_git.py:977` `tag()` builds a malformed argv token** — `cmd.append("-s" if not sign_key else f"-u {sign_key}")` appends `"-u <key>"` as one argv element instead of `["-u", sign_key]`; since commands run via `subprocess.run(list, shell=False)`, git receives one malformed token and signed-tag-with-explicit-key fails
- [x] **`git_interface.py` credential-helper config is broken** _(done 2026-07-24)_ — sets `credential.helper` to the literal string `'cache --timeout=300'` including the quotes (no shell involved, so they're taken literally), via two non-`--add` `--local` sets where the second silently overwrites the first with a bogus value — HTTPS credential caching silently doesn't work. Fixed to a single `config --local credential.helper "cache --timeout=300"` call with no spurious quotes
- [x] **Stray `evoseal/utils/validator.py.bak`** _(done 2026-07-26)_ — a 1132-line backup committed to the repo tree (not gitignored), diverged from `validator.py`; risk of editing the wrong file
- [x] **`evoseal/utils/testing/environment.py:180`** — `suffix: str = None` type-annotation mismatch (should be `Optional[str]`)
- [x] **`providers/ollama_provider.py:98-136`** — `submit_prompt` has no retry/backoff on transient network failures despite being the sole retry/timeout surface for local model calls
- [x] **`providers/local_models.py:103-119`** — `_query_installed_models` is now TTL-cached (120s default); a newly pulled/removed Ollama model is picked up automatically without needing `clear_model_cache()`
- [x] **`model_fine_tuner.py:122-137`** — `_check_gpu_availability()` was defined but never called; `initialize_model()` now calls it and returns `False` with a clear error when no CUDA GPU is available
- [x] **`model_fine_tuner.py:220,240`** — `example['instruction']`/`example['output']` direct dict access with no `.get()`; a malformed training example raises `KeyError` surfaced only as a generic error string instead of a clear validation message
- [x] **`models/code_archive.py:127-149`** — `__init__` manually re-implements every default already provided by `Field(default_factory=...)`, a drift hazard (two sources of truth for the same defaults)
- [x] **`evoseal/agents/agentic_system_example.py:7`** — `from evoseal.agentic_system import ...` is the wrong module path (actual: `evoseal.agents.agentic_system`); the example fails immediately with `ModuleNotFoundError`

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

- [x] **Add a "How It Actually Works" tutorial**
  - Walk through a single evolution cycle step by step with real logs
  - Lower the barrier for new contributors
- [x] **Improve API reference** _(done 2026-07-31)_
  - Ensure all public classes/functions have docstrings
  - Auto-generate API docs (MkDocs + mkdocstrings)

### Research Extensions

- [ ] **Multi-objective Pareto front visualization**
  - Plot correctness vs. efficiency vs. readability trade-offs across generations
- [ ] **Add support for local models (Ollama/vLLM)**
  - Reduce API dependency for experimentation
  - README mentions Ollama integration — verify it works end-to-end
- [x] **Explore population-based training (PBT) as alternative to MAP-Elites** _(done 2026-08-07)_ — ADR 0005 evaluates PBT as a complement (not replacement) for MAP-Elites in hyperparameter tuning. Conclusion: PBT and MAP-Elites solve different problems (hyperparameters vs. code variants); PBT is worth exploring but prerequisites (local model support, sensitivity analysis) aren't in place yet. Recommended next step is a feasibility spike with parallel runs, not a full implementation. Document at `docs/adr/0005-population-based-training.md`
- [ ] **Document EVOSEAL's hyperparameter space** _(follow-up from ADR 0005 §6)_ — enumerate all tuneable pipeline parameters (mutation rate, selection pressure, temperature, etc.) and their current values/ranges; prerequisite for PBT feasibility spike
- [x] **Run PBT feasibility spike** _(done 2026-08-08)_ — `spikes/pbt-feasibility/`: 5 configs × 5 seeds × 10 generations on synthetic fitness landscape. Best-fitness spread 22.9% (>10% ADR 0005 threshold). Verdict: VALIDATED. Next: PBT design doc.
- [ ] **Human-in-the-loop feedback interface**
  - Allow a developer to approve/reject self-modifications via the dashboard
  - Track acceptance rate as a meta-metric

---

## 📋 Tracking

| Priority | Total | Done | Notes |
|----------|-------|------|-------|
| 🔴 P0    | 11    | 11   | Original 5 complete; all 6 critical bugs from 2026-07-22 whole-repo review fixed (PRs #74, #76-#79) |
| 🟠 P1    | 24    | 18   | Original safety/integration items done; +12 high-priority bugs from 2026-07-22 review (3 CI/CD pipeline fixes: workflow_run name mismatch, requirements/ path, security gate bypass); signal-handler init fix; safety.yaml created; monitoring dashboard auth+CORS fix; DGM/OE job runner failed-status bug fix |
| 🟡 P2    | 35    | 30   | Co-evolution loop gaps (8 items, 8 done) + existing P2 + 13 medium bugs from 2026-07-22 review + 4 latent collect->train bugs found closing the loop (1 fixed, 1 new HF-format gap resolved); provider_manager health-check await fix; workflow-agent private-API/event-loop fix; checkpoint save/restore test; trust_remote_code security fix; safety-decision orchestration tests; structured improvement units |
| 🟢 P3    | 26    | 22   | Makefile, pre-commit, Docker, ADRs, ADR refresh, CHANGELOG complete; +11 hygiene items from 2026-07-22 review; Ollama provider retry/backoff fix; local_models TTL cache; workspace prompt file conventions; how-it-works tutorial; model_fine_tuner key validation; model_fine_tuner GPU availability check; PBT exploration ADR; PBT feasibility spike |
| **Total** | **96** | **81** | |

> Update this table as you complete items. Recommended flow: P0 → P1 → P2 → P3.
>
> Items marked _(inspired by OpenClaw)_ are patterns borrowed from the OpenClaw project.
> See comparative analysis for full context on what to adopt vs. what to avoid.

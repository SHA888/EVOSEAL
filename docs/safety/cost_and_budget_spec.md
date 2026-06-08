# Cost and Budget Specification

**Status:** Research-stage specification for P1 cost-tracking and budget-enforcement infrastructure.
**Last updated:** 2026-06-09
**Scope:** Token consumption models, budget configuration schema, enforcement behavior, failure-mode definitions.
**Feeds:** Plans.md tasks 2.9–2.11 (cost estimation, configurable budgets, doctor validation), threat model 2.1 (runaway-loop risks).

---

## 1. Overview

EVOSEAL orchestrates three external components — DGM (Darwin Gödel Machine), OpenEvolve, and SEAL —
in a continuous evolution loop. Each cycle incurs:

- **DGM token cost:** model calls for variant generation
- **SEAL token cost:** fine-tuning data collection and optional LoRA/QLoRA training
- **OpenEvolve cost:** typically CPU/GPU time (out of scope for this spec; see 2.9 for note)
- **Test execution cost:** evaluation substrate (not charged per-token, but included in cycle wall-clock)

This spec defines:
- How tokens are **counted** and attributed to each cycle and component
- How **budgets** are configured, enforced, and reported
- What happens when **budgets are exhausted** (graceful stop, not hard fail)
- How **violations** (overage, misconfiguration, exhaustion) are classified and surfaced

---

## 2. Cost model: tokens per cycle

### 2.1 DGM token cost

Each DGM call generates **one candidate variant** and incurs:

| Phase | Tokens | Notes |
|-------|--------|-------|
| **Prompt setup** | ~500 | System prompt + task framing (amortized) |
| **Context (current source)** | *variable* | Depends on `max_context_tokens` config; typically 1,000–4,000 |
| **Few-shot examples** | ~1,000–3,000 | If in-context examples are included; see SEAL integration |
| **Model output** | ~500–2,000 | Generated variant code; depends on complexity and max_tokens limit |
| **Overhead (API, retries)** | ~10% | Capped at 200 tokens per call |
| **Total per DGM call** | **~2,500–10,000** | Default expectation: 4,000 tokens in a normal cycle |

**Granularity:** Tokens are counted per `DGM.generate()` call. If the loop retries a generation (e.g.,
after a parse error), each attempt is a separate token charge.

### 2.2 SEAL token cost

SEAL is involved in two phases:

#### Phase A: Fine-tuning data collection (ongoing)
- **Per-cycle cost:** ~100 tokens for embedding comparisons or similarity scoring of generated variants
- **Frequency:** Once per completed cycle (happens in parallel with evaluation)

#### Phase B: Fine-tuning (epoch-based, not per-cycle)
- **Per-epoch cost:** Model-dependent; typically 5,000–50,000 tokens for a small LoRA update on GPT-4 or Anthropic API
- **Frequency:** Every N cycles (e.g., every 10 cycles); see config `fine_tuning.trigger_cycle_interval`
- **Tracking:** Logged separately as a "fine-tuning checkpoint" event, not a per-cycle charge

**Attribution:** Phase A is per-cycle; Phase B is per-epoch and rolled up in period reporting (not charged atomically).

### 2.3 Test execution and OpenEvolve

- **Test execution:** Wall-clock time only (not token-based); see "evaluation cost" in the threat model.
- **OpenEvolve (genetic algorithm):** Typically CPU-only; not an LLM cost. If OpenEvolve delegates selection logic
  to an LLM, tokens are counted as a separate call (not part of the base spec; see 2.9 for integration notes).

### 2.4 Cost breakdown in a typical cycle

```
Cycle N:
├─ DGM.generate() variant 1           →  4,000 tokens
├─ OpenEvolve.evaluate(variant 1)     →     0 tokens (CPU/test time)
├─ OpenEvolve.evaluate(variant 2)     →     0 tokens
├─ SEAL.collect_fine_tuning_data()    →   100 tokens
├─ [Test execution]                   →     0 tokens
│
├─ **Subtotal (cycle N):**            →  4,100 tokens
└─ **Cumulative through cycle N:**    →  total_tokens += 4,100
```

After K cycles, if `fine_tuning.trigger_cycle_interval = 10`:
```
After cycle 10:
├─ SEAL.fine_tune()                   → 10,000 tokens (example)
│
├─ **Epoch cost:**                    → 10,000 tokens (logged separately as checkpoint)
└─ **Cumulative (end of epoch 1):**   → 41,000 + 10,000 = 51,000 tokens
```

---

## 3. Budget configuration schema

### 3.1 Configuration file location

Budgets are configured in `configs/budget.yaml` (created as part of 2.10; defaults in `config/settings.py`).

### 3.2 Schema

```yaml
budget:
  # Hard cap on tokens for the entire run (required for 2.10)
  max_tokens_per_run: 100000      # e.g., 100k tokens per hour-long run

  # Hard cap on cost (in USD) for the entire run (optional; used if configured)
  max_cost_per_run: 50.00         # e.g., $50 per run

  # Model-dependent cost per 1k tokens (used to convert tokens → cost)
  # Updated by 2.9; reflects the API pricing of the configured model
  cost_per_1k_tokens: 0.005       # e.g., $0.005 per 1k tokens for GPT-4

  # Warning thresholds (trigger warnings, not stops)
  warn_at_percent_of_budget: 80   # Warn when 80% of budget is consumed

  # Graceful stop behavior
  stop_on_exhaustion: true        # Stop cleanly when budget is hit
  stop_tolerance_tokens: 500      # Allow overage up to this much (for in-flight requests)

  # Per-cycle budget (optional; gates individual cycles)
  max_tokens_per_cycle: 15000     # Reject any cycle costing more than this

  # Per-epoch fine-tuning budget (optional; gates fine-tuning)
  max_tokens_per_epoch: 20000     # Reject fine-tuning checkpoints costing more than this

  # Cost estimation config (used by 2.9)
  cost_estimation:
    dgm_tokens_per_call: 4000     # Average tokens per DGM generation
    seal_tokens_per_cycle: 100    # Tokens for fine-tuning data collection
    seal_tokens_per_epoch: 10000  # Tokens for one fine-tuning checkpoint
    test_time_per_cycle_sec: 30   # Wall-clock test time (not token-based)
```

### 3.3 Defaults (when no `budget.yaml` is present)

```python
# config/settings.py
class BudgetConfig(BaseModel):
    max_tokens_per_run: int = 500_000  # 500k tokens ~ $2.50 for GPT-4
    max_cost_per_run: Optional[float] = None
    cost_per_1k_tokens: float = 0.005
    warn_at_percent_of_budget: int = 80
    stop_on_exhaustion: bool = True
    stop_tolerance_tokens: int = 500
    max_tokens_per_cycle: int = 15_000
    max_tokens_per_epoch: int = 20_000
```

### 3.4 Runtime override (via environment variable)

Users can override the budget at runtime (for ad-hoc runs):

```bash
EVOSEAL_MAX_TOKENS_PER_RUN=50000 evoseal pipeline start
EVOSEAL_MAX_COST_PER_RUN=25.00 evoseal pipeline start
```

---

## 4. Graceful-stop behavior

### 4.1 Stop decision points

The loop checks the budget at the **start of each cycle** (before generating a variant):

```python
# In evolution_pipeline.py::execute_safe_evolution_step()
current_tokens = metrics_tracker.tokens_consumed_this_run
budget = config.budget.max_tokens_per_run

if current_tokens >= budget:
    log.warning(f"Budget exhausted: {current_tokens} / {budget} tokens")
    return EvolutionResult(status="BUDGET_EXHAUSTED", reason="token budget consumed")
    # Loop terminates; final results are collected and reported
```

### 4.2 In-flight overage tolerance

If a **single DGM call** consumes more tokens than `stop_tolerance_tokens` allows over the budget,
the loop completes that call (because it's already in flight) but then **stops immediately after**
without attempting another cycle:

```python
if current_tokens + drifted_overage > budget + stop_tolerance_tokens:
    log.error(f"Token overage exceeded tolerance: {overage} / {stop_tolerance_tokens}")
    # Current variant is rejected; loop stops
    return EvolutionResult(status="BUDGET_EXHAUSTION_HARD", reason="overage tolerance exceeded")
```

### 4.3 Warnings

When consumption reaches `warn_at_percent_of_budget` of the total budget, a warning is emitted:

```python
if current_tokens >= (budget * warn_at_percent_of_budget / 100):
    log.warning(f"Budget {warn_at_percent_of_budget}% consumed: {current_tokens} / {budget} tokens. "
                f"Approximately {estimated_cycles_remaining} cycles remain.")
```

The warning includes an **estimated cycles remaining** based on the average cost per cycle observed so far.

### 4.4 Graceful termination (status and artifacts)

When `stop_on_exhaustion=true` (default):

1. **Iteration stops** — no new variant generation is attempted
2. **In-progress evaluation completes** — running tests are allowed to finish (they don't consume tokens)
3. **Checkpoint is created** — the current best variant is saved
4. **Report is generated** — final token usage, cost breakdown, and reason for stop (see Section 5)
5. **Process exits with code 0** — graceful exit, not an error

When `stop_on_exhaustion=false`:

1. **Loop continues** — ignores budget and runs until `max_iterations` or other stop condition
2. **Cost tracking continues** — all tokens are still logged
3. **Doctor warnings escalate** → the 2.11 doctor command flags the overage (see Section 5.3)

---

## 5. Failure-mode classification

Failure modes are categorized by severity and response. This section defines the **severity levels**
used by tasks 2.9–2.11.

### 5.1 Severity levels

| Level | Trigger | Loop behavior | Doctor verdict | Example |
|-------|---------|---------------|----------------|---------|
| **CRITICAL** | Hard limit exceeded; stop_tolerance breached | Stop immediately; cannot recover | **CRITICAL** (fail-closed) | In-flight DGM call consumed 16k tokens when max_tokens_per_cycle=15k |
| **MAJOR** | Budget exhausted cleanly; insufficient remaining for typical cycle | Stop at cycle boundary; graceful | **WARNING** (not critical unless repeated) | 98% of budget consumed; ~0.5 cycles remain |
| **MINOR** | Budget is low; warnings are advisory | Continue (if `stop_on_exhaustion=false`); emit warnings | **INFO** | Budget at 80% threshold reached |
| **MISCONFIGURATION** | Config does not validate; spec conflict | Fail immediately at startup | **CRITICAL** (fail-closed) | `max_tokens_per_cycle > max_tokens_per_run` |

### 5.2 Detailed failure scenarios

#### 5.2.1 CRITICAL: Cycle-level overages

```
Scenario: DGM.generate() for variant 42 consumes 16,000 tokens, but config sets max_tokens_per_cycle=15,000

Detected at: After variant generation, before test submission
Action: Reject variant; log as "exceeds per-cycle budget"
Doctor check (2.11): CRITICAL — "max_tokens_per_cycle violation (16,000 / 15,000); loop will reject all future variants"
```

#### 5.2.2 CRITICAL: Hard overage (stop_tolerance breached)

```
Scenario: Run budget is 100,000 tokens; 99,500 consumed. Next DGM call is estimated at 4,000 tokens (normal).
Start call → API returns success with 5,000 tokens (higher than typical). Cumulative: 104,500.
stop_tolerance_tokens=500 → overage = 4,500 - 500 = 4,000 (exceeds tolerance).

Detected at: After token count is finalized post-call
Action: Reject variant; stop loop immediately; emit "BUDGET_EXHAUSTION_HARD"
Loop status: Terminated (graceful in structure, not graceful in message)
Doctor check (2.11): CRITICAL — "hard budget overage (104,500 / 100,000); operator must reduce budget or reconfigure"
```

#### 5.2.3 MAJOR: Clean budget exhaustion

```
Scenario: Run budget is 100,000 tokens; 98,000 consumed. Average cost per cycle: 4,000 tokens.
Before cycle N, check: 98,000 >= 100,000? No. Start variant generation.
DGM call succeeds: 102,000 total.

Detected at: Start of next cycle (before variant generation)
Action: Skip cycle N+1; stop loop; emit "BUDGET_EXHAUSTED"
Loop status: Cleanly terminated (no hard overage)
Doctor check (2.11): WARNING — "budget consumed after {N} cycles; consider increasing budget or reducing component verbosity"
```

#### 5.2.4 MINOR: Budget warning threshold

```
Scenario: Run budget is 100,000 tokens; 80,000 consumed (80% threshold).
Estimated remaining cycles: ~5 (at 4k tokens per cycle).

Detected at: Before cycle N
Action: Emit warning; continue if estimated cycles > 0
Loop status: Running (advisory only)
Doctor check (2.11): INFO — "budget 80% consumed (80,000 / 100,000); ~5 cycles estimated to remain"
```

#### 5.2.5 CRITICAL: Misconfiguration

```
Scenario: User sets max_tokens_per_cycle=20,000 but max_tokens_per_run=15,000.
At startup, validation runs: 20,000 > 15,000? Yes.

Detected at: Config initialization (before any generation)
Action: Fail validation; emit "BudgetConfigError"; exit with code 1
Loop status: Cannot start
Doctor check (2.11): CRITICAL — "invalid budget config: max_tokens_per_cycle (20,000) exceeds max_tokens_per_run (15,000)"
```

### 5.3 Doctor verdict mapping (2.11)

The `evoseal doctor` command (task 2.11) checks budget configuration and recent cost history.
It returns one of three verdicts for the budget subsystem:

| Doctor verdict | Condition | Recommendation |
|---|---|---|
| **HEALTHY** | Budget configured, no recent violations, sufficient margin to next cycle | No action needed |
| **WARNING** | Budget approaching exhaustion, or recent minor violations; loop can continue but should be monitored | Monitor token usage; consider increasing budget or profiling components for verbosity reduction |
| **CRITICAL** | Misconfiguration, hard overage, or cycle-level ceiling breaches; loop cannot proceed safely | Fix config (resolve conflicts, increase budgets, reduce per-component limits) before retry |

---

## 6. Token tracking and reporting

### 6.1 Where tokens are counted

- **Per-DGM call:** `DGMIntegration.generate_variant()` logs tokens consumed (from provider response metadata)
- **Per-SEAL call:** `SEALIntegration.collect_data()` and `fine_tune()` log tokens (if API-based; Ollama/local: 0)
- **Per cycle:** `MetricsTracker.record_cycle()` sums up DGM + SEAL tokens for the cycle and accumulates global total
- **Per epoch:** `MetricsTracker.record_fine_tuning_checkpoint()` logs epoch-level fine-tuning tokens separately

### 6.2 Reporting

#### Runtime reporting (during loop)
```
Cycle 5/10 (50%):
  - Tokens this cycle: 4,200 (DGM: 4,100, SEAL: 100)
  - Cumulative tokens: 21,000 / 100,000 budget (21%)
  - Cost so far: $0.105 / $25.00 budget (0.4%)
  - Est. cycles remaining: ~19
```

#### Final report (at loop completion)
```
Evolution Loop Complete

  Cycles completed:        18 / 20 requested
  Stop reason:            BUDGET_EXHAUSTED

  Token consumption:
    Total:                98,500 tokens
    Budget:               100,000 tokens
    Utilization:         98.5%

  Cost breakdown:
    DGM (18 calls):       72,000 tokens → $0.36
    SEAL data (18x):      1,800 tokens → $0.009
    SEAL fine-tuning:     24,700 tokens → $0.12 (3 epochs @ avg 8.2k each)
    Total cost:           $0.489 / $25.00

  Recommendations:
    - Token budget nearly exhausted; increase budget or reduce DGM context size
    - Fine-tuning triggered 3 times; consider increasing epoch interval
```

### 6.3 Persistent metrics (for task 2.10 validation)

Cost and budget state are persisted in `.evoseal/metrics/budget_snapshot.json`:

```json
{
  "run_id": "run_20260609_143000",
  "start_time": "2026-06-09T14:30:00Z",
  "end_time": "2026-06-09T15:15:00Z",
  "cycles_completed": 18,
  "max_cycles_configured": 20,
  "budget_max_tokens": 100000,
  "budget_max_cost": 25.00,
  "tokens_consumed": 98500,
  "cost_incurred": 0.489,
  "stop_reason": "BUDGET_EXHAUSTED",
  "stop_graceful": true,
  "warn_threshold_percent": 80,
  "percent_budget_consumed": 98.5,
  "violations": []
}
```

---

## 7. Interaction with threat model and ADR 0001

This spec feeds three threat-model findings:

1. **Threat model §6 (infinite-loop risks):** Budget + iteration cap closes the "no enforced cap on total evolution iterations" gap.
   The hard iteration cap (2.15) is separate but complementary; together they bound the loop in both iteration count and token cost.

2. **Threat model §7, out-of-scope:** Adversarial/runaway *generation* is out of scope, so budgets assume honest-but-fallible LLM output.
   A deliberately adversarial model could craft prompts that blow up context size and exhaust budget in 1–2 calls; defense requires a different
   threat model assumption (Section 1 of ADR 0001).

3. **ADR 0001 §4, Tier 1:** Cost visibility and budget enforcement are part of Tier 1 runaway controls, complementing (2.13–2.14) and (2.15).

---

## 8. Out of scope

This spec does **not** define:

- **Provider-specific cost negotiation** — assumes published per-token pricing from provider
- **Multi-provider cost modeling** — assumes all calls are to one configured provider
- **Cost optimization** — that is a follow-on P2/P3 feature (context pruning, prompt compression, etc.)
- **Cost attribution to specific tasks/metrics** — only per-cycle and per-epoch aggregation
- **Billing/chargeback** — EVOSEAL is single-operator research software; no multi-tenant billing
- **Real-time cost alerts** — doctor (2.11) is the reporting interface; alerts are user-initiated
- **Rollback cost recovery** — budget is not credited when a rollback reverts a cost; the tokens are spent

---

## 9. Validation checklist (for task 2.10, "configurable token budget")

Before task 2.10 is considered complete, verify:

- [ ] `configs/budget.yaml` can be created with the schema in Section 3.2
- [ ] All schema fields have defaults in `config/settings.py` (BudgetConfig model)
- [ ] `EVOSEAL_MAX_TOKENS_PER_RUN` and `EVOSEAL_MAX_COST_PER_RUN` env overrides work
- [ ] At cycle start, budget check (Section 4.1) stops the loop when budget is exhausted
- [ ] In-flight overage tolerance (Section 4.2) is enforced; hard overage causes immediate stop
- [ ] `warn_at_percent_of_budget` warning is emitted and includes estimated-cycles-remaining
- [ ] Config validation (Section 5.2.5) rejects `max_tokens_per_cycle > max_tokens_per_run`
- [ ] `evoseal doctor` command (2.11) correctly reads this spec and reports all verdicts (Section 5.3)
- [ ] Integration test 2.6 covers budget-exhaustion scenario (loop stops cleanly after ~20 cycles with a small budget)
- [ ] Metrics snapshot (Section 6.3) is written to `.evoseal/metrics/budget_snapshot.json` on completion

---

## 10. Future work (P2+)

- **Cost estimation refinement** (2.9): Gather real token usage from multiple runs and refine default per-component costs
- **Multi-provider cost modeling:** Support multiple providers with different costs; route calls to stay within budget
- **Cost optimization:** Context pruning, prompt compression, caching; measured against this budget framework
- **Tier 2 fine-tuning cost:** If LoRA/QLoRA moves to external services, define provider-specific costs
- **Collaborative budgeting:** Multi-operator/multi-project cost sharing (out of scope, single-operator research only)

---

## Appendix: Example budget.yaml file

```yaml
budget:
  # Hard limits
  max_tokens_per_run: 250000
  max_cost_per_run: 100.00

  # Model pricing (typical for Claude Sonnet)
  cost_per_1k_tokens: 0.003

  # Thresholds
  warn_at_percent_of_budget: 80
  stop_on_exhaustion: true
  stop_tolerance_tokens: 1000

  # Per-cycle and per-epoch caps
  max_tokens_per_cycle: 20000
  max_tokens_per_epoch: 50000

  # Cost estimation (used by task 2.9 and loop telemetry)
  cost_estimation:
    dgm_tokens_per_call: 4000
    seal_tokens_per_cycle: 150
    seal_tokens_per_epoch: 15000
    test_time_per_cycle_sec: 45
```

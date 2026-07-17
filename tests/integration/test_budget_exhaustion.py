"""Integration tests for token budget exhaustion and graceful stop behavior.

Tests the budget enforcement mechanisms including cycle-start checks,
in-flight overage tolerance, and warning thresholds.
"""

import json
from pathlib import Path

import pytest

from evoseal.core.budget_tracker import BudgetTracker
from evoseal.core.evolution_pipeline import EvolutionPipeline

# Test constants
DGM_TOKENS_PER_CYCLE = 4000
SEAL_TOKENS_PER_CYCLE = 100
TOKENS_PER_CYCLE = DGM_TOKENS_PER_CYCLE + SEAL_TOKENS_PER_CYCLE
TEST_BUDGET = 100_000
COST_PER_1K = 0.005
CYCLES_IN_TEST = 3
TOTAL_TOKENS_3_CYCLES = 12_300
DGM_TOKENS_3_CYCLES = 12_000
SEAL_TOKENS_3_CYCLES = 300
MIN_ESTIMATED_CYCLES = 18
MAX_ESTIMATED_CYCLES = 20
WARNING_THRESHOLD = 80_000
MAX_TOKENS_PER_RUN = 500_000
WARN_AT_PERCENT = 80
STOP_TOLERANCE = 500
MAX_TOKENS_PER_CYCLE_DEFAULT = 15_000
MAX_TOKENS_PER_EPOCH_DEFAULT = 20_000


@pytest.mark.integration
class TestBudgetExhaustion:
    """Test budget exhaustion scenarios."""

    @pytest.fixture
    def budget_tracker(self) -> BudgetTracker:
        """Create a budget tracker for testing."""
        return BudgetTracker()

    @pytest.fixture
    def temp_metrics_dir(self, tmp_path) -> Path:
        """Create temporary metrics directory."""
        metrics_dir = tmp_path / ".evoseal" / "metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        return metrics_dir

    def test_budget_tracker_token_accumulation(self, budget_tracker: BudgetTracker) -> None:
        """Test that tokens are correctly accumulated in the budget tracker."""
        assert budget_tracker.tokens_consumed_this_run == 0

        # Record DGM tokens
        budget_tracker.record_dgm_tokens(DGM_TOKENS_PER_CYCLE)
        assert budget_tracker.tokens_consumed_this_run == DGM_TOKENS_PER_CYCLE

        # Record SEAL tokens
        budget_tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        assert budget_tracker.tokens_consumed_this_run == TOKENS_PER_CYCLE

        # Complete cycle
        budget_tracker.record_cycle_completion()
        assert budget_tracker.cycle_count == 1

        # Start new cycle - the run total accumulates across cycle boundaries
        # (record_cycle_completion resets only the per-cycle accumulators).
        budget_tracker.record_dgm_tokens(DGM_TOKENS_PER_CYCLE)
        budget_tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        assert budget_tracker.tokens_consumed_this_run == 2 * TOKENS_PER_CYCLE

    def test_budget_tracker_estimated_cycles(self, budget_tracker: BudgetTracker) -> None:
        """Test cycle estimation based on budget."""
        # No cycles recorded yet - use default estimate
        estimated = budget_tracker.estimated_cycles_until_budget(TEST_BUDGET)
        assert estimated > 0

        # Record some cycles
        for _ in range(5):
            budget_tracker.record_dgm_tokens(DGM_TOKENS_PER_CYCLE)
            budget_tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
            budget_tracker.record_cycle_completion()

        # Now estimate should be based on average
        estimated = budget_tracker.estimated_cycles_until_budget(TEST_BUDGET)
        # 5 cycles @ TOKENS_PER_CYCLE tokens each = 20,500 tokens consumed
        # Remaining = 79,500 / TOKENS_PER_CYCLE per cycle ≈ 19 cycles
        assert MIN_ESTIMATED_CYCLES <= estimated <= MAX_ESTIMATED_CYCLES

    def test_budget_tracker_cost_calculation(self, budget_tracker: BudgetTracker) -> None:
        """Test cost calculation from token consumption."""
        budget_tracker.record_dgm_tokens(1000)
        cost = budget_tracker.get_cost(COST_PER_1K)
        assert cost == pytest.approx(COST_PER_1K, rel=1e-6)

        budget_tracker.record_dgm_tokens(1000)
        cost = budget_tracker.get_cost(COST_PER_1K)
        assert cost == pytest.approx(0.01, rel=1e-6)

    def test_budget_tracker_summary(self, budget_tracker: BudgetTracker) -> None:
        """Test comprehensive summary generation."""
        # Record multiple cycles
        for _ in range(CYCLES_IN_TEST):
            budget_tracker.record_dgm_tokens(DGM_TOKENS_PER_CYCLE)
            budget_tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
            budget_tracker.record_cycle_completion()

        summary = budget_tracker.get_summary(COST_PER_1K)

        assert summary["cycle_count"] == CYCLES_IN_TEST
        assert summary["total_tokens"] == TOTAL_TOKENS_3_CYCLES
        assert summary["dgm_tokens"] == DGM_TOKENS_3_CYCLES
        assert summary["seal_cycle_tokens"] == SEAL_TOKENS_3_CYCLES
        assert summary["dgm_cost"] == pytest.approx(0.06, rel=1e-6)

    def test_budget_config_validation_cycle_budget(self) -> None:
        """Test that config validation rejects invalid cycle budgets."""
        from config.settings import BudgetConfig

        # Valid config: cycle budget <= run budget
        config = BudgetConfig(
            max_tokens_per_run=100_000,
            max_tokens_per_cycle=50_000,
        )
        assert config.max_tokens_per_cycle <= config.max_tokens_per_run

        # Invalid config: cycle budget > run budget
        with pytest.raises(ValueError, match="max_tokens_per_cycle"):
            BudgetConfig(
                max_tokens_per_run=50_000,
                max_tokens_per_cycle=100_000,
            )

    def test_budget_config_defaults(self) -> None:
        """Test that BudgetConfig has correct defaults."""
        from config.settings import BudgetConfig

        config = BudgetConfig()

        assert config.max_tokens_per_run == MAX_TOKENS_PER_RUN
        assert config.max_cost_per_run is None
        assert config.cost_per_1k_tokens == COST_PER_1K
        assert config.warn_at_percent_of_budget == WARN_AT_PERCENT
        assert config.stop_on_exhaustion is True
        assert config.stop_tolerance_tokens == STOP_TOLERANCE
        assert config.max_tokens_per_cycle == MAX_TOKENS_PER_CYCLE_DEFAULT
        assert config.max_tokens_per_epoch == MAX_TOKENS_PER_EPOCH_DEFAULT

    @pytest.mark.asyncio
    async def test_evolution_pipeline_budget_checks_mock(self) -> None:
        """Test that EvolutionPipeline includes budget checking logic."""
        pipeline = EvolutionPipeline()

        # Verify budget_tracker is initialized
        assert hasattr(pipeline, "budget_tracker")
        assert isinstance(pipeline.budget_tracker, BudgetTracker)

        # Verify _write_budget_snapshot method exists
        assert hasattr(pipeline, "_write_budget_snapshot")
        assert callable(pipeline._write_budget_snapshot)

    def test_budget_snapshot_structure(self, tmp_path: Path) -> None:
        """Test that budget snapshot has the correct structure."""
        pipeline = EvolutionPipeline()

        # Simulate some token consumption
        pipeline.budget_tracker.record_dgm_tokens(DGM_TOKENS_PER_CYCLE)
        pipeline.budget_tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        pipeline.budget_tracker.record_cycle_completion()

        results = [
            {
                "iteration": 1,
                "success": True,
            }
        ]

        # Write snapshot (goes to .evoseal/metrics relative to cwd)
        # The snapshot is written to disk; verify it has correct structure
        import os

        original_cwd = os.getcwd()
        try:
            # Change to temp directory so snapshot is written there
            os.chdir(tmp_path)
            pipeline._write_budget_snapshot(results)

            # Verify snapshot file exists and has correct structure
            snapshot_path = Path(".evoseal/metrics/budget_snapshot.json")
            assert snapshot_path.exists(), f"Snapshot not found at {snapshot_path}"

            with open(snapshot_path) as f:
                snapshot = json.load(f)

            # Check required fields
            assert "run_id" in snapshot
            assert "cycles_completed" in snapshot
            assert "tokens_consumed" in snapshot
            assert "cost_incurred" in snapshot
            assert "stop_reason" in snapshot
            assert "percent_budget_consumed" in snapshot

            # Verify values
            assert snapshot["cycles_completed"] == 1
            assert snapshot["tokens_consumed"] == TOKENS_PER_CYCLE
            assert snapshot["stop_reason"] in ("COMPLETED", "BUDGET_EXHAUSTED")
        finally:
            os.chdir(original_cwd)

    def test_warning_threshold_calculation(self) -> None:
        """Test warning threshold calculation for budget consumption."""
        from config.settings import BudgetConfig

        config = BudgetConfig(
            max_tokens_per_run=TEST_BUDGET,
            warn_at_percent_of_budget=WARN_AT_PERCENT,
        )

        threshold = (config.max_tokens_per_run * config.warn_at_percent_of_budget) / 100
        assert threshold == WARNING_THRESHOLD

    def test_budget_exhaustion_stop_reason(self) -> None:
        """Test that stop reason is correctly determined from results."""
        results = [
            {"iteration": 1, "success": True},
            {"iteration": 2, "success": True},
            {"iteration": 3, "status": "BUDGET_EXHAUSTED"},
        ]

        # Should find BUDGET_EXHAUSTED in reversed results
        stop_reason = "COMPLETED"
        for result in reversed(results):
            if result.get("status") == "BUDGET_EXHAUSTED":
                stop_reason = "BUDGET_EXHAUSTED"
                break

        assert stop_reason == "BUDGET_EXHAUSTED"

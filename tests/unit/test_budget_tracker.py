"""Tests for BudgetTracker token accounting and cost estimation."""

import pytest

from evoseal.core.budget_tracker import BudgetTracker

# Test constants
DGM_TOKENS_DEFAULT = 4000
SEAL_TOKENS_PER_CYCLE = 100
SEAL_TOKENS_PER_EPOCH = 10000
CYCLE_TOTAL_TOKENS = 4100
BUDGET_SAMPLE = 100000
COST_PER_1K_DEFAULT = 0.005
CYCLE_1_TOKENS = 4100
CYCLE_2_TOKENS = 4200
AVG_TOKENS_PER_CYCLE = 4150


class TestBudgetTracker:
    """Test suite for BudgetTracker."""

    def test_initialization(self):
        """Test that BudgetTracker initializes with zero tokens."""
        tracker = BudgetTracker()
        assert tracker.tokens_consumed_this_run == 0
        assert tracker.cycle_count == 0

    def test_record_dgm_tokens(self):
        """Test recording DGM token consumption."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
        assert tracker.tokens_consumed_this_run == DGM_TOKENS_DEFAULT

    def test_record_multiple_dgm_calls(self):
        """Test accumulating tokens from multiple DGM calls."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
        tracker.record_dgm_tokens(3500)
        tracker.record_dgm_tokens(4200)
        total_expected = DGM_TOKENS_DEFAULT + 3500 + 4200
        assert tracker.tokens_consumed_this_run == total_expected

    def test_record_seal_tokens(self):
        """Test recording SEAL token consumption."""
        tracker = BudgetTracker()
        tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        assert tracker.tokens_consumed_this_run == SEAL_TOKENS_PER_CYCLE

    def test_record_cycle_completion(self):
        """Test recording a completed cycle with token summary."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
        tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        tracker.record_cycle_completion()

        assert tracker.cycle_count == 1
        assert tracker.tokens_consumed_this_run == CYCLE_TOTAL_TOKENS
        assert len(tracker.cycle_history) == 1
        assert tracker.cycle_history[0]["tokens"] == CYCLE_TOTAL_TOKENS

    def test_record_fine_tuning_checkpoint(self):
        """Test recording a fine-tuning checkpoint."""
        tracker = BudgetTracker()
        tracker.record_fine_tuning_checkpoint(SEAL_TOKENS_PER_EPOCH)
        assert tracker.tokens_consumed_this_run == SEAL_TOKENS_PER_EPOCH
        assert len(tracker.fine_tuning_history) == 1
        assert tracker.fine_tuning_history[0]["tokens"] == SEAL_TOKENS_PER_EPOCH

    def test_get_cost(self):
        """Test cost calculation from token count."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(1000)
        cost = tracker.get_cost(cost_per_1k_tokens=COST_PER_1K_DEFAULT)
        assert cost == COST_PER_1K_DEFAULT  # 1000 tokens * 0.005 / 1000 = 0.005

    def test_get_average_cost_per_cycle(self):
        """Test average cost per cycle calculation."""
        tracker = BudgetTracker()
        # Cycle 1: 4100 tokens
        tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
        tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        tracker.record_cycle_completion()

        # Cycle 2: 4200 tokens
        tracker.record_dgm_tokens(4100)
        tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        tracker.record_cycle_completion()

        avg = tracker.get_average_cost_per_cycle(cost_per_1k_tokens=COST_PER_1K_DEFAULT)
        # (4100 + 4200) / 2 = 4150 tokens per cycle, * 0.005 / 1000 = 0.02075
        expected_cost = (AVG_TOKENS_PER_CYCLE * COST_PER_1K_DEFAULT) / 1000
        assert avg == pytest.approx(expected_cost)

    def test_estimated_cycles_until_budget(self):
        """Test estimation of remaining cycles until budget exhaustion."""
        tracker = BudgetTracker()
        # Record 5 cycles of 4000 tokens each
        for _ in range(5):
            tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
            tracker.record_cycle_completion()

        # Total: 20000 tokens consumed
        remaining = tracker.estimated_cycles_until_budget(BUDGET_SAMPLE)
        # (100000 - 20000) / 4000 = 20 remaining cycles
        expected_remaining = (BUDGET_SAMPLE - 20000) // DGM_TOKENS_DEFAULT
        assert remaining == expected_remaining

    def test_estimated_cycles_zero_when_over_budget(self):
        """Test that estimated cycles is 0 when budget is exceeded."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(50000)
        budget = 40000
        remaining = tracker.estimated_cycles_until_budget(budget)
        assert remaining == 0

    def test_get_summary(self):
        """Test summary generation."""
        tracker = BudgetTracker()
        tracker.record_dgm_tokens(DGM_TOKENS_DEFAULT)
        tracker.record_seal_tokens(SEAL_TOKENS_PER_CYCLE)
        tracker.record_cycle_completion()
        tracker.record_fine_tuning_checkpoint(SEAL_TOKENS_PER_EPOCH)

        summary = tracker.get_summary(cost_per_1k_tokens=COST_PER_1K_DEFAULT)

        total_expected = CYCLE_TOTAL_TOKENS + SEAL_TOKENS_PER_EPOCH
        assert summary["total_tokens"] == total_expected
        assert summary["cycle_count"] == 1
        assert summary["fine_tuning_count"] == 1
        assert "total_cost" in summary
        expected_total_cost = (total_expected * COST_PER_1K_DEFAULT) / 1000
        assert summary["total_cost"] == pytest.approx(expected_total_cost)

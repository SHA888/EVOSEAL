"""Tests for the estimate-cost CLI command."""

import pytest
from typer.testing import CliRunner

from evoseal.cli.commands import estimate_cost


@pytest.fixture
def cli_runner():
    """Create a Typer CLI test runner."""
    return CliRunner()


class TestEstimateCostCommand:
    """Test suite for the estimate-cost command."""

    def test_estimate_cost_basic(self, cli_runner):
        """Test basic estimate-cost command with default parameters."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "10"])
        assert result.exit_code == 0
        assert "tokens" in result.stdout.lower()
        assert "cost" in result.stdout.lower()

    def test_estimate_cost_with_custom_dgm_tokens(self, cli_runner):
        """Test estimate-cost with custom DGM tokens per call."""
        result = cli_runner.invoke(
            estimate_cost.app,
            [
                "--iterations",
                "5",
                "--dgm-tokens-per-call",
                "5000",
            ],
        )
        assert result.exit_code == 0

    def test_estimate_cost_with_cost_per_1k(self, cli_runner):
        """Test estimate-cost with custom cost per 1k tokens."""
        result = cli_runner.invoke(
            estimate_cost.app,
            [
                "--iterations",
                "10",
                "--cost-per-1k-tokens",
                "0.01",
            ],
        )
        assert result.exit_code == 0
        assert "cost" in result.stdout.lower()

    def test_estimate_cost_zero_iterations(self, cli_runner):
        """Test estimate-cost with zero iterations."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "0"])
        assert result.exit_code == 0
        # Should show 0 cost for 0 iterations
        assert "0" in result.stdout or "total" in result.stdout.lower()

    def test_estimate_cost_large_iterations(self, cli_runner):
        """Test estimate-cost with a large number of iterations."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "1000"])
        assert result.exit_code == 0

    def test_estimate_cost_help(self, cli_runner):
        """Test that help is available for estimate-cost command."""
        result = cli_runner.invoke(estimate_cost.app, ["--help"])
        assert result.exit_code == 0
        assert "iterations" in result.stdout.lower()

    def test_estimate_cost_invalid_iterations(self, cli_runner):
        """Test estimate-cost with invalid iterations parameter."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "invalid"])
        # Typer should handle invalid int and exit with non-zero
        assert result.exit_code != 0

    def test_estimate_cost_output_format(self, cli_runner):
        """Test that estimate-cost outputs expected fields."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "5"])
        assert result.exit_code == 0
        output = result.stdout.lower()

        # Should contain key metrics
        assert any(keyword in output for keyword in ["token", "cost", "iteration", "cycle"])

    def test_estimate_cost_with_all_options(self, cli_runner):
        """Test estimate-cost with all customizable options."""
        result = cli_runner.invoke(
            estimate_cost.app,
            [
                "--iterations",
                "20",
                "--dgm-tokens-per-call",
                "4500",
                "--seal-tokens-per-cycle",
                "150",
                "--cost-per-1k-tokens",
                "0.008",
            ],
        )
        assert result.exit_code == 0

    def test_estimate_cost_includes_breakdown(self, cli_runner):
        """Test that estimate-cost includes cost breakdown (DGM + SEAL)."""
        result = cli_runner.invoke(estimate_cost.app, ["--iterations", "5"])
        assert result.exit_code == 0
        output = result.stdout.lower()

        # Should mention component costs
        assert any(keyword in output for keyword in ["dgm", "seal", "breakdown"])

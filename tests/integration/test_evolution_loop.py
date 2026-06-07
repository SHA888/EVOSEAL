"""End-to-end integration test for the EVOSEAL evolution loop (Plans.md 2.6).

This test exercises the complete evolution cycle:
  1. Generate variants (via mocked DGM)
  2. Evaluate variants (via mocked OpenEvolve)
  3. Select winner
  4. Simulate self-modification
  5. Verify regression checks

All components run in mock mode (EVOSEAL_MOCK_MODE=true) with no external API calls.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest

from evoseal.core.controller import Controller
from evoseal.core.evaluator import Evaluator
from evoseal.core.testrunner import TestRunner
from evoseal.integration import ComponentType, create_integration_orchestrator
from evoseal.testing.mock_components import (
    create_mock_dgm_adapter,
    create_mock_openevolve_adapter,
    create_mock_seal_adapter,
    is_mock_mode,
)

pytestmark = [pytest.mark.integration]

# Constants for test assertions
MIN_VARIANTS = 2
TARGET_SCORE = 0.9


@pytest.fixture
def mock_mode_env(monkeypatch):
    """Enable mock mode for all tests."""
    monkeypatch.setenv("EVOSEAL_MOCK_MODE", "true")
    yield
    # Clean up
    monkeypatch.delenv("EVOSEAL_MOCK_MODE", raising=False)


@pytest.fixture
def mock_seed(monkeypatch):
    """Set a deterministic seed for reproducible mock results."""
    seed = 42
    monkeypatch.setenv("EVOSEAL_MOCK_SEED", str(seed))
    yield seed
    monkeypatch.delenv("EVOSEAL_MOCK_SEED", raising=False)


class TestEvolutionLoopE2E:
    """End-to-end tests for the evolution pipeline."""

    @pytest.mark.asyncio
    async def test_mock_mode_enabled(self, mock_mode_env):
        """Verify that mock mode can be enabled."""
        assert is_mock_mode()

    @pytest.mark.asyncio
    async def test_create_mock_adapters(self, mock_mode_env, mock_seed):
        """Verify that mock adapters can be created."""
        dgm = create_mock_dgm_adapter(seed=mock_seed)
        oe = create_mock_openevolve_adapter(seed=mock_seed)
        seal = create_mock_seal_adapter(seed=mock_seed)

        # Verify adapters are initialized
        assert await dgm.initialize()
        assert await oe.initialize()
        assert await seal.initialize()

        # Verify they can start
        assert await dgm.start()
        assert await oe.start()
        assert await seal.start()

    @pytest.mark.asyncio
    async def test_generate_variants(self, mock_mode_env, mock_seed):
        """Test variant generation via mocked DGM."""
        dgm = create_mock_dgm_adapter(seed=mock_seed)
        await dgm.initialize()
        await dgm.start()

        # Request variant generation for generation 0
        result = await dgm.execute("advance_generation", {"generation": 0})
        assert result.success
        assert "run_ids" in result.data
        assert len(result.data["run_ids"]) >= MIN_VARIANTS

        await dgm.stop()

    @pytest.mark.asyncio
    async def test_evaluate_variants(self, mock_mode_env, mock_seed):
        """Test variant evaluation via mocked OpenEvolve."""
        oe = create_mock_openevolve_adapter(seed=mock_seed)
        await oe.initialize()
        await oe.start()

        # Evaluate variants
        result = await oe.execute("evolve", {"iterations": 1})
        assert result.success
        assert "program_id" in result.data
        assert "score" in result.data
        assert 0 <= result.data["score"] <= 1

        await oe.stop()

    @pytest.mark.asyncio
    async def test_select_winner_from_variants(self, mock_mode_env, mock_seed):
        """Test winner selection from evaluated variants."""
        oe = create_mock_openevolve_adapter(seed=mock_seed)
        await oe.initialize()
        await oe.start()

        # Generate evaluation results for 2 variants
        variant_1 = await oe.execute("evolve", {"iterations": 1})
        variant_2 = await oe.execute("evolve", {"iterations": 2})

        assert variant_1.success
        assert variant_2.success

        # Select winner (highest score)
        variants = [
            {"id": "var_1", "score": variant_1.data["score"]},
            {"id": "var_2", "score": variant_2.data["score"]},
        ]
        winner = max(variants, key=lambda v: v["score"])

        assert winner is not None
        assert "score" in winner
        assert winner["score"] > 0

        await oe.stop()

    @pytest.mark.asyncio
    async def test_simulate_self_modification(self, mock_mode_env, mock_seed):
        """Test simulated self-modification of winning variant."""
        seal = create_mock_seal_adapter(seed=mock_seed)
        await seal.initialize()
        await seal.start()

        # Simulate code improvement via SEAL
        original_code = "def my_function():\n    return 42"
        result = await seal.execute("improve_code", {"code": original_code})

        assert result.success
        assert "code" in result.data
        assert result.data["code"] != original_code
        assert "mock improve_code" in result.data["code"]

        await seal.stop()

    @pytest.mark.asyncio
    async def test_full_evolution_cycle(self, mock_mode_env, mock_seed):
        """Test complete evolution cycle: generate → evaluate → select → self-modify.

        This is the main integration test that validates the full workflow.
        """
        # Step 1: Initialize mocked components
        dgm = create_mock_dgm_adapter(seed=mock_seed)
        oe = create_mock_openevolve_adapter(seed=mock_seed)
        seal = create_mock_seal_adapter(seed=mock_seed)

        await dgm.initialize()
        await oe.initialize()
        await seal.initialize()

        await dgm.start()
        await oe.start()
        await seal.start()

        # Step 2: Generate variants (generation 0)
        gen_result = await dgm.execute("advance_generation", {"generation": 0})
        assert gen_result.success
        run_ids = gen_result.data["run_ids"]
        assert len(run_ids) >= MIN_VARIANTS, f"DGM should generate at least {MIN_VARIANTS} variants"

        # Step 3: Evaluate each variant
        evaluated_variants = []
        for idx, run_id in enumerate(run_ids):
            eval_result = await oe.execute("evolve", {"iterations": idx})
            assert eval_result.success
            evaluated_variants.append(
                {
                    "run_id": run_id,
                    "program_id": eval_result.data["program_id"],
                    "score": eval_result.data["score"],
                }
            )

        # Step 4: Select winner
        winner = max(evaluated_variants, key=lambda v: v["score"])
        assert winner is not None
        assert "program_id" in winner
        assert winner["score"] > 0

        # Step 5: Simulate self-modification on winning variant
        improve_result = await seal.execute(
            "improve_code",
            {"code": f"# Original from {winner['program_id']}\npass"},
        )
        assert improve_result.success
        improved_code = improve_result.data["code"]
        assert "mock improve_code" in improved_code

        # Step 6: Regression check (simulate by re-evaluating)
        regression_result = await oe.execute("evolve", {"iterations": 99})
        assert regression_result.success

        # Verify overall flow metrics
        dgm_metrics = await dgm.get_metrics()
        assert dgm_metrics["operations_executed"] >= 1

        oe_metrics = await oe.get_metrics()
        assert oe_metrics["operations_executed"] >= len(run_ids) + 1  # +1 for regression

        seal_metrics = await seal.get_metrics()
        assert seal_metrics["operations_executed"] >= 1

        # Cleanup
        await dgm.stop()
        await oe.stop()
        await seal.stop()

    @pytest.mark.asyncio
    async def test_deterministic_output_same_seed(self, mock_mode_env, mock_seed):
        """Verify that mocks produce deterministic output for the same seed."""
        # First run
        dgm1 = create_mock_dgm_adapter(seed=mock_seed)
        await dgm1.initialize()
        await dgm1.start()
        result1 = await dgm1.execute("advance_generation", {"generation": 0})
        await dgm1.stop()

        # Second run with same seed
        dgm2 = create_mock_dgm_adapter(seed=mock_seed)
        await dgm2.initialize()
        await dgm2.start()
        result2 = await dgm2.execute("advance_generation", {"generation": 0})
        await dgm2.stop()

        # Verify determinism
        assert result1.data["run_ids"] == result2.data["run_ids"]
        assert result1.data["best_fitness"] == result2.data["best_fitness"]

    @pytest.mark.asyncio
    async def test_no_api_calls_in_mock_mode(self, mock_mode_env, mock_seed, monkeypatch):
        """Verify no external API calls are made when using mocks."""

        class BlockingSession:
            async def __aenter__(self):
                raise RuntimeError("aiohttp.ClientSession() instantiated in mock mode!")

            async def __aexit__(self, *args):
                pass

        import aiohttp

        monkeypatch.setattr(aiohttp, "ClientSession", BlockingSession)

        # Run evolution loop - should not trigger HTTP calls
        dgm = create_mock_dgm_adapter(seed=mock_seed)
        await dgm.initialize()
        await dgm.start()

        result = await dgm.execute("advance_generation", {"generation": 0})
        assert result.success

        await dgm.stop()


class TestEvolutionLoopWithController:
    """Tests using the Controller for orchestration."""

    @pytest.mark.asyncio
    async def test_controller_with_mocks(self, mock_mode_env, mock_seed):
        """Test Controller orchestration with mocked components."""
        # Create mocked test runner and evaluator
        test_runner = MagicMock(spec=TestRunner)
        test_runner.run_tests = MagicMock(return_value={"passed": 5, "failed": 0})

        evaluator = MagicMock(spec=Evaluator)
        evaluator.evaluate = MagicMock(
            return_value=[
                {"variant": "v1", "score": 0.8},
                {"variant": "v2", "score": 0.9},
            ]
        )

        # Create controller
        controller = Controller(test_runner, evaluator)
        controller.initialize({"max_generations": 1})

        # Run generation
        controller.run_generation()

        # Verify workflow
        assert controller.current_generation == 1
        assert "generations" in controller.state
        assert len(controller.state["generations"]) == 1

        gen_data = controller.state["generations"][0]
        assert "test_results" in gen_data
        assert "eval_results" in gen_data
        assert "selected" in gen_data

    @pytest.mark.asyncio
    async def test_candidate_selection(self, mock_mode_env):
        """Test candidate selection logic."""
        test_runner = MagicMock(spec=TestRunner)
        evaluator = MagicMock(spec=Evaluator)
        controller = Controller(test_runner, evaluator)

        eval_results = [
            {"variant": "v1", "score": 0.7},
            {"variant": "v2", "score": TARGET_SCORE},
            {"variant": "v3", "score": 0.8},
        ]

        selected = controller.select_candidates(eval_results)

        # Verify selection (top N candidates ranked by score)
        assert len(selected) > 0
        assert selected[0]["variant"] == "v2"  # Highest score
        assert selected[0]["score"] == TARGET_SCORE


# Async test execution
@pytest.mark.asyncio
async def test_evolution_cycle_smoke(mock_mode_env, mock_seed):
    """Smoke test: basic execution of evolution cycle."""
    dgm = create_mock_dgm_adapter(seed=mock_seed)
    oe = create_mock_openevolve_adapter(seed=mock_seed)

    await dgm.initialize()
    await oe.initialize()

    assert await dgm.start()
    assert await oe.start()

    # Generate and evaluate
    gen = await dgm.execute("advance_generation", {"generation": 0})
    assert gen.success

    eval_result = await oe.execute("evolve", {"iterations": 1})
    assert eval_result.success

    await dgm.stop()
    await oe.stop()

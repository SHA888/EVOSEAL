"""
Integration tests for OpenEvolve controller and core components.

These tests verify the end-to-end functionality of the OpenEvolve system,
including the interaction between different components.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

import pytest
from typer.testing import CliRunner

# Constants for test values
HIGH_SCORE_THRESHOLD = 0.9
LOW_SCORE_THRESHOLD = 0.1

# Add the project root to the Python path
project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Add the OpenEvolve module to the Python path
openevolve_path = str(Path(project_root) / "openevolve")
if openevolve_path not in sys.path:
    sys.path.insert(0, openevolve_path)

# Import EVOSEAL CLI
from evoseal.cli.main import app

# Try to import OpenEvolve components
OPENEVOLVE_AVAILABLE = False
try:
    sys.path.insert(0, os.path.abspath("."))  # Add project root to path
    try:
        # Add the project root and openevolve directory to the Python path
        project_root = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        openevolve_dir = os.path.join(project_root, "openevolve")

        # Add to sys.path if not already there
        for path in [project_root, openevolve_dir]:
            if path not in sys.path:
                sys.path.insert(0, path)

        # Import the openevolve package
        import openevolve
        from openevolve.config import (
            Config,
            LLMConfig,
            LLMModelConfig,
            PromptConfig,
            load_config,
        )

        # Now import the specific modules we need
        from openevolve.controller import OpenEvolve
        from openevolve.database import Program, ProgramDatabase
        from openevolve.evaluation_result import EvaluationResult
        from openevolve.evaluator import Evaluator
        from openevolve.llm.ensemble import LLMEnsemble
        from openevolve.prompt.sampler import PromptSampler

        # Mock setup_logging since it's not available in the utils package
        def setup_logging(*args, **kwargs):
            import logging

            logging.basicConfig(level=logging.INFO)

    except ImportError as e:
        print(f"Warning: Could not import OpenEvolve components: {e}")
        print(f"Python path: {sys.path}")
        print(f"Current directory: {os.getcwd()}")
        print(f"Project root: {project_root}")
        openevolve_path = os.path.join(project_root, "openevolve")
        print(f"OpenEvolve path: {openevolve_path}")
        if os.path.exists(openevolve_path):
            print(f"Files in OpenEvolve directory: {os.listdir(openevolve_path)}")
            openevolve_inner_path = os.path.join(openevolve_path, "openevolve")
            if os.path.exists(openevolve_inner_path):
                print(
                    f"Files in inner OpenEvolve directory: {os.listdir(openevolve_inner_path)}"
                )
        raise e
    OPENEVOLVE_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import OpenEvolve components: {e}")
    print(f"Python path: {sys.path}")
    print(f"Current directory: {os.getcwd()}")
    raise e

# Skip all tests if OpenEvolve is not available
pytestmark = pytest.mark.skipif(
    not OPENEVOLVE_AVAILABLE, reason="OpenEvolve module not available"
)

# Test configuration
TEST_CONFIG = {
    "population_size": 5,
    "max_generations": 2,
    "mutation_rate": 0.1,
    "crossover_rate": 0.8,
    "elitism": 1,
    "evaluation_metrics": ["accuracy", "latency"],
    "fitness_weights": {"accuracy": 0.7, "latency": 0.3},
}


class MockEvaluator(Evaluator):
    """Mock evaluator for testing purposes."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.evaluation_count = 0

    async def evaluate_program(self, code, program_id=None):
        """Mock evaluation that returns a fixed score."""
        self.evaluation_count += 1
        return {
            "fitness": 0.9,
            "accuracy": 0.9,
            "latency": 0.1,
            "evaluation_count": self.evaluation_count,
        }

    def get_pending_artifacts(self, program_id):
        """Return empty artifacts for testing."""
        return {}


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create a test configuration."""
    # Create a minimal config
    config = Config()

    # Set up test directories
    work_dir = tmp_path / "work"
    output_dir = tmp_path / "output"
    work_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)

    # Update config with test values
    config.work_dir = str(work_dir)
    config.output_dir = str(output_dir)
    config.population_size = TEST_CONFIG["population_size"]
    config.max_generations = TEST_CONFIG["max_generations"]
    config.mutation_rate = TEST_CONFIG["mutation_rate"]
    config.crossover_rate = TEST_CONFIG["crossover_rate"]
    config.elitism = TEST_CONFIG["elitism"]

    # Set up LLM config
    config.llm = LLMConfig(
        name="mock_model",
        api_base="http://mock-api",
        api_key="mock_key",
        weight=1.0,
        temperature=0.0,  # Make it deterministic
        max_tokens=10,  # Keep it small for tests
        system_message="You are a helpful assistant",
    )

    # Set up prompt config with test templates
    config.prompt = PromptConfig(
        system_message="Test system message",
        evaluator_system_message="Test evaluator message",
    )

    # Configure evaluator settings
    config.evaluator.timeout = 30  # Shorter timeout for tests
    config.evaluator.max_retries = 1  # Fewer retries for tests
    config.evaluator.parallel_evaluations = 1  # Run evaluations sequentially

    return config


@pytest.fixture
def test_controller(test_config: Config, tmp_path: Path) -> OpenEvolve:
    """Create a test controller with a mock evaluator and temporary directories."""
    # Create a test program file
    program_path = tmp_path / "test_program.py"
    program_path.write_text(
        """
    def main():
        return "Hello, World!"
    """
    )

    # Create an evaluation file
    eval_path = tmp_path / "evaluate.py"
    eval_path.write_text(
        """
def evaluate(program_path):
    return {"accuracy": 0.9, "latency": 0.1, "fitness": 0.9, "passed": True}
"""
    )

    # Create the controller
    controller = OpenEvolve(
        initial_program_path=str(program_path),
        evaluation_file=str(eval_path),
        config=test_config,
    )

    # Create a mock evaluator
    class MockEvaluator(Evaluator):
        """Mock evaluator for testing purposes."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.evaluation_count = 0

        async def evaluate_program(self, code, program_id=None):
            """Mock evaluation that returns a fixed score."""
            self.evaluation_count += 1
            return {
                "fitness": 0.9,
                "accuracy": 0.9,
                "latency": 0.1,
                "evaluation_count": self.evaluation_count,
            }

        def get_pending_artifacts(self, program_id):
            """Return empty artifacts for testing."""
            return {}

    # Replace the evaluator with our mock
    controller.evaluator = MockEvaluator(
        evaluation_file=str(eval_path),
        config=test_config.evaluator,
        database=controller.database,
    )

    return controller


def test_controller_initialization(test_controller: OpenEvolve):
    """Test that the controller initializes correctly."""
    assert test_controller is not None
    assert hasattr(test_controller, "config")
    assert hasattr(test_controller, "evaluator")
    assert hasattr(test_controller, "llm_ensemble")
    assert hasattr(test_controller, "prompt_sampler")
    assert hasattr(test_controller, "database")
    assert hasattr(test_controller, "initial_program_code")
    assert hasattr(test_controller, "language")


def test_controller_evaluation(test_controller: OpenEvolve):
    """Test that the controller can evaluate a program."""
    # Skip this test if we can't import the required modules
    if not OPENEVOLVE_AVAILABLE:
        pytest.skip("OpenEvolve not available")

    # Create a test program ID
    from uuid import uuid4

    program_id = str(uuid4())

    # Create a test program using the Program class directly
    program = Program(
        id=program_id,
        code="def main(): return 42\n",
        parent_id=None,
        generation=0,
        metadata={"test": True},
    )

    # Add the program to the database
    added_id = test_controller.database.add(program)
    assert added_id == program_id

    # Get the program back to ensure it was saved
    saved_program = test_controller.database.get(program_id)
    assert saved_program is not None

    # Set up mock evaluator
    class MockEvaluator(Evaluator):
        def evaluate(self, program):
            return {
                "fitness": 0.9,  # Fixed fitness for testing
                "metrics": {"fitness": 0.9, "accuracy": 0.9, "latency": 0.1},
                "passed": True,
            }

    # Replace the evaluator with our mock
    test_controller.evaluator = MockEvaluator(
        evaluation_file=test_controller.evaluator.evaluation_file,
        config=test_controller.config.evaluator,
        database=test_controller.database,
    )

    # Evaluate the program using the async method
    import asyncio

    loop = asyncio.get_event_loop()
    metrics = loop.run_until_complete(
        test_controller.evaluator.evaluate_program(saved_program.code, program_id)
    )

    # Check the evaluation result
    assert metrics is not None
    assert isinstance(metrics, dict)
    assert "fitness" in metrics
    assert "accuracy" in metrics
    assert "latency" in metrics

    # Update the program's metrics in the database
    saved_program.metrics = metrics
    test_controller.database.add(saved_program)

    # Refresh the program from the database to check updates
    updated_program = test_controller.database.get(program_id)
    assert updated_program is not None
    # Verify the metrics were updated correctly
    assert updated_program.metrics.get("fitness") == HIGH_SCORE_THRESHOLD
    assert updated_program.metrics.get("accuracy") == HIGH_SCORE_THRESHOLD
    assert updated_program.metrics.get("latency") == LOW_SCORE_THRESHOLD


def test_controller_evolution_step(test_controller: OpenEvolve):
    """Test a single evolution step."""
    # Skip this test if we can't import the required modules
    if not OPENEVOLVE_AVAILABLE:
        pytest.skip("OpenEvolve not available")

    # Ensure we have at least one program in the database
    from uuid import uuid4

    program_id = str(uuid4())
    program = Program(
        id=program_id,
        code="def main(): return 42\n",
        parent_id=None,
        generation=0,
        metadata={"test": True},
    )
    added_id = test_controller.database.add(program)
    assert added_id == program_id

    # Set up mock evaluator
    class MockEvaluator(Evaluator):
        def evaluate(self, program):
            return {
                "fitness": 0.9,  # Fixed fitness for testing
                "metrics": {"fitness": 0.9, "accuracy": 0.9, "latency": 0.1},
                "passed": True,
            }

    # Replace the evaluator with our mock
    test_controller.evaluator = MockEvaluator(
        evaluation_file=test_controller.evaluator.evaluation_file,
        config=test_controller.config.evaluator,
        database=test_controller.database,
    )

    # Get the initial best program
    initial_best = test_controller.database.get_best_program()

    # Run one evolution step
    try:
        # Use asyncio to run the async method
        import asyncio

        loop = asyncio.get_event_loop()
        improved = loop.run_until_complete(test_controller.run(iterations=1))

        # Check that we got a result
        assert improved is not None

        # Get the new best program
        new_best = test_controller.database.get_best_program()

        # Check that the best program was updated
        if initial_best is not None:
            assert new_best.metrics.get("fitness", 0) >= initial_best.metrics.get(
                "fitness", 0
            )
        else:
            assert new_best is not None
    except RuntimeError as e:
        if "no running event loop" in str(e):
            # Handle case where there's no event loop
            import asyncio

            asyncio.set_event_loop(asyncio.new_event_loop())
            loop = asyncio.get_event_loop()
            improved = loop.run_until_complete(test_controller.run(iterations=1))

            # Check that we got a result
            assert improved is not None

            # Get the new best program
            new_best = test_controller.database.get_best_program()

            # Check that the best program was updated
            if initial_best is not None:
                assert new_best.metrics.get("fitness", 0) >= initial_best.metrics.get(
                    "fitness", 0
                )
            else:
                assert new_best is not None


def test_controller_full_run(test_controller: OpenEvolve):
    """Test a full run of the controller with multiple generations."""
    # Skip this test if we can't import the required modules
    if not OPENEVOLVE_AVAILABLE:
        pytest.skip("OpenEvolve not available")

    # Ensure we have at least one program in the database
    from uuid import uuid4

    program_id = str(uuid4())
    program = Program(
        id=program_id,
        code="def main(): return 42\n",
        parent_id=None,
        generation=0,
        metadata={"test": True},
        metrics={"fitness": 0.8},  # Initial fitness
    )
    added_id = test_controller.database.add(program)
    assert added_id == program_id

    # Set up mock evaluator
    class MockEvaluator(Evaluator):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.evaluation_count = 0

        async def evaluate_program(self, code, program_id=None):
            self.evaluation_count += 1
            return {
                "fitness": 0.9,
                "accuracy": 0.9,
                "latency": 0.1,
                "evaluation_count": self.evaluation_count,
            }

        def get_pending_artifacts(self, program_id):
            return {}

    # Replace the evaluator with our mock
    mock_evaluator = MockEvaluator(
        config=test_controller.config.evaluator,
        evaluation_file=test_controller.evaluator.evaluation_file,
        llm_ensemble=None,
        prompt_sampler=test_controller.evaluator_prompt_sampler,
        database=test_controller.database,
    )
    test_controller.evaluator = mock_evaluator

    # Also patch the LLM ensemble to prevent real API calls
    class MockLLMEnsemble:
        def __init__(self):
            self.call_count = 0

        async def generate_with_context(self, *args, **kwargs):
            self.call_count += 1
            # Return a properly formatted diff in SEARCH/REPLACE format
            return """Here's an improved version of your code:

            <<<<<<< SEARCH
            def main(): return 42
            =======
            def main():
                # Improved version with better formatting
                return 42
            >>>>>>> REPLACE

            The changes include:
            - Better code formatting
            - Added a comment
            - Improved readability
            """

    # Replace both LLM ensembles with our mock
    mock_llm = MockLLMEnsemble()
    test_controller.llm_ensemble = mock_llm
    test_controller.llm_evaluator_ensemble = mock_llm

    # Reduce the number of iterations for testing
    iterations = 2

    # Run the evolution with proper event loop handling
    import asyncio

    # Create a new event loop for this test
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Run the controller
        best_program = loop.run_until_complete(
            test_controller.run(iterations=iterations)
        )

        # Check that we got a result
        assert best_program is not None
        assert "fitness" in best_program.metrics
        assert hasattr(best_program, "metrics")

        # Check that the database was updated
        db_best = test_controller.database.get_best_program()
        assert db_best is not None

        # Check that the output directory exists
        output_dir = Path(test_controller.output_dir)
        assert output_dir.exists()

        # Check that we have the expected output files
        assert (
            output_dir / "best" / f"best_program{test_controller.file_extension}"
        ).exists()
        assert (output_dir / "best" / "best_program_info.json").exists()

        # Check that the results file contains the expected data
        results_file = output_dir / "results.json"
        if results_file.exists():
            with open(results_file) as f:
                results = json.load(f)
                assert isinstance(results, dict), "Results should be a dictionary"
                assert "best_program" in results
                assert "history" in results
                assert (
                    len(results["history"]) >= 1
                )  # At least one generation should be recorded
    finally:
        # Clean up the event loop
        loop.close()

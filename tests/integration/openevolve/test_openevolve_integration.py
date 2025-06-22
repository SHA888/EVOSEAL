"""
Integration tests for OpenEvolve core components.

These tests verify the end-to-end functionality of the OpenEvolve system,
including the interaction between different components.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from evoseal.cli.main import app

# Constants for test values
GENERATIONS = 5
POPULATION_SIZE = 5
MUTATION_RATE = 0.1
CROSSOVER_RATE = 0.8
ELITISM = 1

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "data"
TEST_CONFIG = {
    "openevolve": {
        "population_size": 10,
        "max_generations": 3,
        "mutation_rate": 0.1,
        "crossover_rate": 0.8,
        "elitism": 1,
    },
    "evaluation": {
        "metrics": ["accuracy", "latency"],
        "fitness_weights": {"accuracy": 0.7, "latency": 0.3},
    },
}


@pytest.fixture(scope="module")
def test_project(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Create a test project directory with a simple evolution task."""
    project_dir = tmp_path_factory.mktemp("test_project")

    # Create a simple Python module to evolve
    src_dir = project_dir / "src"
    src_dir.mkdir()

    # Create a simple fitness function
    (src_dir / "fitness.py").write_text(
        """
        def evaluate(individual, **kwargs):
            # Simple fitness function for testing
            return {
                "accuracy": 0.9,  # Mock accuracy
                "latency": 0.1,  # Mock latency in seconds
            }
        """
    )

    # Create a simple individual generator
    (src_dir / "individual.py").write_text(
        """
        def create_individual():
            # Return a simple individual representation
            return {"model": "simple", "params": {"learning_rate": 0.01}}

        def mutate(individual, rate=0.1):
            # Simple mutation
            import random
            if random.random() < rate:
                individual["params"]["learning_rate"] *= 1.1
            return individual

        def crossover(parent1, parent2):
            # Simple crossover
            return {
                "model": parent1["model"],
                "params": {
                    "learning_rate": (parent1["params"]["learning_rate"] +
                                     parent2["params"]["learning_rate"]) / 2
                }
            }
        """
    )

    # Create a requirements file
    (project_dir / "requirements.txt").write_text("numpy>=1.20.0\n")

    return project_dir


def test_end_to_end_evolution(test_project: Path):
    """Test the complete evolution process from initialization to final generation."""
    runner = CliRunner()

    # Initialize the project
    result = runner.invoke(app, ["init", "--project-dir", str(test_project)])
    assert result.exit_code == 0, f"Init failed: {result.output}"

    # Run the evolution
    result = runner.invoke(
        app,
        [
            "evolve",
            "--project-dir",
            str(test_project),
            "--generations",
            str(GENERATIONS),
        ],
    )
    assert result.exit_code == 0, f"Evolve failed: {result.output}"

    # Verify the output directory was created
    output_dir = test_project / "output"
    assert output_dir.exists(), "Output directory not created"

    # Verify the results file was created
    results_file = output_dir / "results.json"
    assert results_file.exists(), "Results file not created"

    # Load and verify the results
    with open(results_file) as f:
        results = json.load(f)
        assert "best_individual" in results, "Best individual not in results"
        assert "final_generation" in results, "Final generation not in results"
        assert (
            results["final_generation"] == GENERATIONS
        ), "Incorrect number of generations"

    # Test direct component usage
    try:
        # Add the OpenEvolve module to the path
        import os
        import sys

        openevolve_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "openevolve")
        )
        if openevolve_path not in sys.path:
            sys.path.insert(0, openevolve_path)

        from openevolve.core.evolution import EvolutionEngine
        from openevolve.core.population import Population

        # Verify we can create a population
        population = Population(size=POPULATION_SIZE)
        assert (
            len(population.individuals) == POPULATION_SIZE
        ), "Population size mismatch"

        # Verify we can create an evolution engine
        # Test population size constant
        test_population_size = 10
        engine = EvolutionEngine(
            population_size=test_population_size,
            mutation_rate=MUTATION_RATE,
            crossover_rate=CROSSOVER_RATE,
            elitism=ELITISM,
        )
        assert (
            engine.population_size == test_population_size
        ), "Engine population size mismatch"

    except ImportError as e:
        pytest.skip(f"Could not import OpenEvolve components: {e}")


def test_error_handling(test_project: Path):
    """Test error conditions and edge cases in the evolution process."""
    # Test with invalid configuration
    invalid_config = TEST_CONFIG.copy()
    invalid_config["openevolve"]["population_size"] = 0  # Invalid population size

    config_path = test_project / ".evoseal" / "config.yaml"
    with open(config_path, "w") as f:
        import yaml

        yaml.dump(invalid_config, f)

    # Test with invalid configuration by directly testing the components
    try:
        # Add the OpenEvolve module to the path
        import os
        import sys

        openevolve_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "openevolve")
        )
        if openevolve_path not in sys.path:
            sys.path.insert(0, openevolve_path)

        from openevolve.core.evolution import EvolutionEngine
        from openevolve.core.exceptions import EvolutionError

        # Test with invalid population size
        with pytest.raises(ValueError) as exc_info:
            _ = EvolutionEngine(population_size=0)
        assert "population_size" in str(exc_info.value).lower()

        # Test with invalid mutation rate
        with pytest.raises(ValueError) as exc_info:
            _ = EvolutionEngine(population_size=10, mutation_rate=1.5)
        assert "mutation_rate" in str(exc_info.value).lower()

    except ImportError as e:
        pytest.skip(f"Could not import OpenEvolve components: {e}")


@pytest.mark.parametrize(
    "metric,weight",
    [
        ("accuracy", 0.8),
        ("latency", 0.2),
    ],
)
def test_fitness_calculation(test_project: Path, metric: str, weight: float):
    """Test that fitness calculation respects the configured weights."""
    # Update config with custom weights
    custom_config = TEST_CONFIG.copy()
    custom_config["evaluation"]["fitness_weights"] = {metric: weight}

    config_path = test_project / ".evoseal" / "config.yaml"
    with open(config_path, "w") as f:
        import yaml

        yaml.dump(custom_config, f)

    try:
        # Add the OpenEvolve module to the path
        import os
        import sys

        openevolve_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "openevolve")
        )
        if openevolve_path not in sys.path:
            sys.path.insert(0, openevolve_path)

        from openevolve.core.fitness import FitnessEvaluator
        from openevolve.core.individual import Individual

        # Create a test individual with fitness
        individual = Individual()
        individual.fitness = {metric: 0.9}  # Mock fitness value

        # Create a fitness evaluator with the test weights
        evaluator = FitnessEvaluator(weights={metric: weight})

        # Calculate the score
        score = evaluator.evaluate(individual)

        # Verify the score is calculated correctly
        expected_score = individual.fitness[metric] * weight
        assert score == pytest.approx(
            expected_score, abs=1e-6
        ), f"Fitness score not correctly weighted for {metric}"

    except ImportError as e:
        pytest.skip(f"Could not import OpenEvolve components: {e}")

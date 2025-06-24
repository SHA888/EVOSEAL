"""
Controller class for orchestrating the OpenEvolve evolutionary process.

Manages initialization, generations, coordination between TestRunner and Evaluator,
candidate selection, and provides CLI/system interfaces.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from evoseal.core.evaluator import Evaluator
    from evoseal.core.testrunner import TestRunner


class Controller:
    def __init__(
        self,
        test_runner: TestRunner,
        evaluator: Evaluator,
        logger: logging.Logger | None = None,
    ) -> None:
        self.test_runner = test_runner
        self.evaluator = evaluator
        self.logger = logger or logging.getLogger(__name__)
        self.current_generation = 0
        self.state: dict[str, Any] = {}

    def initialize(self, config: dict[str, Any]) -> None:
        """Initialize the evolutionary process with the given configuration."""
        self.logger.info("Initializing evolutionary process with config: %s", config)
        self.state = {"config": config, "generations": []}
        self.current_generation = 0

    def run_generation(self) -> None:
        """Run a single generation: evaluate, test, and select candidates."""
        self.logger.info("Running generation %d", self.current_generation)
        # Example: orchestrate test runner and evaluator
        # Use the current working directory as the base path for tests
        test_path = "."  # This should be the path to the test directory
        test_results = self.test_runner.run_tests(test_path)
        eval_results = self.evaluator.evaluate(test_results)
        selected = self.select_candidates(eval_results)
        self.state["generations"].append(
            {
                "generation": self.current_generation,
                "test_results": test_results,
                "eval_results": eval_results,
                "selected": selected,
            }
        )
        self.current_generation += 1

    def select_candidates(self, eval_results: list[Any]) -> list[Any]:
        """Select candidates for the next generation based on evaluation results."""
        self.logger.info("Selecting candidates from evaluation results")
        # Placeholder: select top N candidates
        return sorted(eval_results, key=lambda r: r.get("score", 0), reverse=True)[:5]

    def get_state(self) -> dict:
        """Return the current state of the evolutionary process."""
        return self.state

    def cli_interface(self, command: str, *args: Any, **kwargs: Any) -> Any:
        """CLI/system interface for interacting with the controller."""
        self.logger.info("Received CLI command: %s", command)
        if command == "status":
            return self.get_state()
        elif command == "run_generation":
            self.run_generation()
            return {"msg": "Generation complete", "generation": self.current_generation}
        else:
            return {"error": "Unknown command"}

    # Add more methods as needed for error handling, advanced coordination, etc.

"""
EVOSEAL Quickstart Example

This script demonstrates the basic usage of EVOSEAL to evolve a simple Python function.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file before any other imports
load_dotenv()


def main() -> None:
    # Import here to ensure environment variables are loaded first
    from evoseal import EVOSEAL  # type: ignore[attr-defined]

    # Initialize EVOSEAL with default settings
    evo = EVOSEAL()

    # Define the task
    task = """
    Create an efficient Python function that implements the Fibonacci sequence.
    The function should take an integer n and return the nth Fibonacci number.
    The implementation should be optimized for both time and space complexity.
    """

    print("Starting evolution process...")
    print(f"Task: {task.strip()}")

    # Run the evolution process
    result = evo.evolve(task=task, max_iterations=20, population_size=10, verbose=True)

    # Print results
    print("\nEvolution complete!")
    print(f"Best solution found after {result.iterations} iterations:")
    print("-" * 50)
    print(result.best_solution)
    print("-" * 50)
    print(f"Fitness score: {result.fitness:.4f}")

    # Save the best solution to a file
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / "fibonacci_solution.py"

    with open(output_file, "w") as f:
        f.write(result.best_solution)

    print(f"\nSolution saved to: {output_file}")


if __name__ == "__main__":
    # Check for required environment variables
    required_vars = ["OPENAI_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]

    if missing_vars:
        print("Error: The following required environment variables are not set:")
        for var in missing_vars:
            print(f"- {var}")
        print("\nPlease create a .env file with these variables or set them in your environment.")
        sys.exit(1)

    try:
        main()
    except KeyboardInterrupt:
        print("\nEvolution interrupted by user.")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")

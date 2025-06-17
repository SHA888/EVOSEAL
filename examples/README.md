# EVOSEAL Examples

This directory contains example scripts and notebooks demonstrating how to use EVOSEAL for various tasks.

## Quick Start

1. **Set up your environment** (if you haven't already):
   ```bash
   # From the project root
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r examples/requirements.txt
   ```

2. **Run an example**:
   ```bash
   python examples/quickstart.py
   ```

## Available Examples

### Basic Examples

- **quickstart.py** - A simple example showing how to use EVOSEAL to evolve a Python function
  ```bash
  python examples/quickstart.py
  ```

### Advanced Examples

*More examples coming soon!*

## Creating Your Own Examples

To create your own example:

1. Create a new Python file in this directory
2. Import EVOSEAL and any required dependencies
3. Define your task and evolution parameters
4. Run the evolution process
5. Save and analyze the results

Here's a minimal template to get you started:

```python
from evoseal import EVOSEAL

def main():
    # Initialize EVOSEAL
    evoseal = EVOSEAL()
    
    # Define your task
    task = """
    Your task description goes here.
    Be as specific as possible about what you want to evolve.
    """
    
    # Run the evolution
    result = evoseal.evolve(
        task=task,
        max_iterations=30,
        population_size=15,
        verbose=True
    )
    
    # Print results
    print("\nBest solution:")
    print("-" * 50)
    print(result.best_solution)
    print("-" * 50)
    print(f"Fitness: {result.fitness:.4f}")

if __name__ == "__main__":
    main()
```

## Contributing Examples

We welcome contributions of new examples! When contributing an example, please:

1. Keep the code simple and well-documented
2. Include comments explaining key steps
3. Add a brief description to this README
4. Test your example before submitting a pull request

## Need Help?

If you have questions or need help with the examples, please [open an issue](https://github.com/SHA888/EVOSEAL/issues) or join our community forum.

# Quick Start Guide

This guide will help you get started with EVOSEAL quickly.

## Prerequisites

- Python 3.10 or higher
- Git
- pip (Python package manager)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/SHA888/EVOSEAL.git
   cd EVOSEAL
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```

## Basic Usage

1. **Configure Environment Variables**
   Copy the example environment file and update it with your settings:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

2. **Run the Basic Example**
   ```python
   from evoseal import EVOSEAL

   # Initialize EVOSEAL
   evoseal = EVOSEAL()

   # Define your task
   task = "Create a function that sorts a list of dictionaries by a specific key"

   # Run evolution
   result = evoseal.evolve(task, max_iterations=10)

   # View results
   print(f"Best solution: {result.best_solution}")
   print(f"Fitness score: {result.fitness}")
   ```

## Advanced Usage

### Custom Fitness Function

```python
def custom_fitness(solution):
    # Implement your custom fitness logic
    score = 0
    # ... evaluation logic ...
    return score

evoseal = EVOSEAL(fitness_function=custom_fitness)
```

### Using Different Models

```python
from evoseal.models import OpenAIModel, AnthropicModel

# Use OpenAI
gpt4 = OpenAIModel(model="gpt-4")

# Or Anthropic
claude = AnthropicModel(model="claude-3-opus")

evoseal = EVOSEAL(model=claude)
```

## Command Line Interface

EVOSEAL also provides a CLI for quick tasks:

```bash
# Run evolution from command line
evoseal evolve --task "Your task description" --iterations 10

# View help
evoseal --help
```

## Next Steps

- Explore the [User Manual](user/manual.md) for detailed usage instructions
- Check out the [API Reference](api/index.md) for advanced features
- Read the [Architecture Overview](architecture/overview.md) to understand how EVOSEAL works

## Getting Help

For questions or issues, please [open an issue](https://github.com/SHA888/EVOSEAL/issues) on GitHub.

# EVOSEAL User Manual

Welcome to the EVOSEAL User Manual. This document provides comprehensive information about using EVOSEAL effectively.

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Basic Usage](#basic-usage)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)
- [FAQs](#frequently-asked-questions)

## Installation

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation Steps

1. **Clone the Repository**
   ```bash
   git clone https://github.com/SHA888/EVOSEAL.git
   cd EVOSEAL
   ```

2. **Set Up Virtual Environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```ini
# Required
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional
LOG_LEVEL=INFO
CACHE_DIR=./.cache
```

### Configuration Files

EVOSEAL supports multiple configuration files for different environments:
- `config/development.json` - Development settings
- `config/testing.json` - Testing settings
- `config/production.json` - Production settings

## Basic Usage

### Initialization

```python
from evoseal import EVOSEAL

# Initialize with default settings
evoseal = EVOSEAL()
```

### Running Evolution

```python
# Define your task
task = "Create a Python function that implements quicksort"

# Run evolution
result = evoseal.evolve(
    task=task,
    max_iterations=50,
    population_size=10
)

# Access results
print(f"Best solution: {result.best_solution}")
print(f"Fitness score: {result.fitness}")
print(f"Iterations completed: {result.iterations}")
```

## Advanced Features

### Custom Fitness Functions

```python
def custom_fitness(solution):
    """Evaluate a solution based on specific criteria."""
    score = 0
    
    # Example: Reward shorter solutions
    score += max(0, 10 - len(solution) / 100)
    
    # Add your custom evaluation logic here
    
    return score

# Initialize with custom fitness
custom_evoseal = EVOSEAL(fitness_function=custom_fitness)
```

### Model Selection

```python
from evoseal.models import OpenAIModel, AnthropicModel

# Use specific models
gpt4 = OpenAIModel(model="gpt-4")
claude = AnthropicModel(model="claude-3-opus")

# Initialize with custom model
evoseal = EVOSEAL(model=gpt4)
```

### Checkpointing

```python
# Save checkpoint
evoseal.save_checkpoint("checkpoint.pkl")

# Load checkpoint
evoseal.load_checkpoint("checkpoint.pkl")
```

## Troubleshooting

### Common Issues

1. **API Key Errors**
   - Ensure your API keys are set in the `.env` file
   - Verify the keys have the correct permissions

2. **Installation Issues**
   - Make sure you're using Python 3.10 or higher
   - Try recreating your virtual environment

3. **Performance Problems**
   - Reduce population size or number of iterations
   - Use smaller models for faster iteration

## Frequently Asked Questions

### How do I improve evolution results?
- Provide clear, specific tasks
- Experiment with different population sizes
- Adjust the number of iterations
- Fine-tune the fitness function

### Can I use my own models?
Yes! EVOSEAL supports custom model implementations. See the API reference for details.

### How do I contribute?
Please see our [Contribution Guidelines](https://github.com/SHA888/EVOSEAL/CONTRIBUTING.md).

## Support

For additional help, please [open an issue](https://github.com/SHA888/EVOSEAL/issues) on GitHub.
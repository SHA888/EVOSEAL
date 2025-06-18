# EVOSEAL API Reference

This document provides detailed documentation for the EVOSEAL public API.

## Table of Contents

- [Core Classes](#core-classes)
  - [EVOSEAL](#evoseal)
  - [EvolutionConfig](#evolutionconfig)
  - [EvolutionResult](#evolutionresult)
- [Models](#models)
  - [BaseModel](#basemodel)
  - [OpenAIModel](#openaimodel)
  - [AnthropicModel](#anthropicmodel)
- [Evolution Strategies](#evolution-strategies)
  - [BaseStrategy](#basestrategy)
  - [GeneticStrategy](#geneticstrategy)
  - [GradientStrategy](#gradientstrategy)
- [Evaluation](#evaluation)
  - [Evaluator](#evaluator)
  - [FitnessFunction](#fitnessfunction)
- [Utils](#utils)
  - [Logger](#logger)
  - [Metrics](#metrics)
  - [Checkpointer](#checkpointer)
- [Exceptions](#exceptions)
- [Type Definitions](#type-definitions)

## Core Classes

### EVOSEAL

The main class for interacting with the EVOSEAL system.

```python
class EVOSEAL:
    def __init__(self, model: BaseModel, config: Optional[EvolutionConfig] = None):
        """Initialize EVOSEAL with a model and optional configuration."""

    async def evolve(
        self,
        task: str,
        constraints: Optional[Dict[str, Any]] = None,
        **kwargs
    ) -> EvolutionResult:
        """Evolve a solution for the given task."""

    def save_checkpoint(self, path: Union[str, Path]) -> None:
        """Save the current state to a checkpoint file."""

    @classmethod
    def from_checkpoint(cls, path: Union[str, Path]) -> 'EVOSEAL':
        """Load EVOSEAL instance from a checkpoint file."""
```

### EvolutionConfig

Configuration for the evolution process.

```python
class EvolutionConfig(BaseModel):
    population_size: int = 50
    max_generations: int = 100
    mutation_rate: float = 0.1
    crossover_rate: float = 0.8
    elite_size: int = 5
    early_stopping: Optional[int] = 10
    verbose: bool = True
```

### EvolutionResult

Result of an evolution run.

```python
class EvolutionResult(BaseModel):
    best_solution: str
    fitness: float
    generation: int
    history: List[Dict[str, Any]]
    metrics: Dict[str, Any]

    def save(self, path: Union[str, Path]) -> None:
        """Save the result to a file."""

    @classmethod
    def load(cls, path: Union[str, Path]) -> 'EvolutionResult':
        """Load a result from a file."""
```

## Models

### BaseModel

Abstract base class for all models.

```python
class BaseModel(ABC):
    @abstractmethod
    async def generate(
        self,
        prompt: str,
        **kwargs
    ) -> str:
        """Generate text from a prompt."""

    @abstractmethod
    def get_embeddings(
        self,
        text: str
    ) -> List[float]:
        """Get embeddings for the given text."""
```

### OpenAIModel

Wrapper for OpenAI models.

```python
class OpenAIModel(BaseModel):
    def __init__(
        self,
        model_name: str = "gpt-4",
        api_key: Optional[str] = None,
        **kwargs
    ):
        """Initialize with model name and API key."""
```

### AnthropicModel

Wrapper for Anthropic models.

```python
class AnthropicModel(BaseModel):
    def __init__(
        self,
        model_name: str = "claude-3-opus",
        api_key: Optional[str] = None,
        **kwargs
    ):
        """Initialize with model name and API key."""
```

## Evolution Strategies

### BaseStrategy

Abstract base class for evolution strategies.

```python
class BaseStrategy(ABC):
    @abstractmethod
    async def evolve(
        self,
        population: List[Individual],
        evaluator: Evaluator,
        config: EvolutionConfig
    ) -> List[Individual]:
        """Evolve the population."""
```

### GeneticStrategy

Genetic programming strategy.

```python
class GeneticStrategy(BaseStrategy):
    def __init__(
        self,
        mutation_operators: List[Callable],
        crossover_operators: List[Callable],
        selection_method: str = "tournament"
    ):
        """Initialize with genetic operators."""
```

### GradientStrategy

Gradient-based strategy.

```python
class GradientStrategy(BaseStrategy):
    def __init__(
        self,
        learning_rate: float = 0.01,
        optimizer: str = "adam"
    ):
        """Initialize with optimization parameters."""
```

## Evaluation

### Evaluator

Evaluates individuals.

```python
class Evaluator:
    def __init__(
        self,
        fitness_functions: List[FitnessFunction],
        constraints: Optional[List[Callable]] = None
    ):
        """Initialize with fitness functions and constraints."""

    async def evaluate(
        self,
        individual: Individual
    ) -> Dict[str, float]:
        """Evaluate an individual."""
```

### FitnessFunction

Base class for fitness functions.

```python
class FitnessFunction(ABC):
    @abstractmethod
    async def __call__(
        self,
        individual: Individual,
        **kwargs
    ) -> float:
        """Calculate fitness for an individual."""
```

## Utils

### Logger

Logging utilities.

```python
class Logger:
    @staticmethod
    def info(msg: str, **kwargs) -> None:
        """Log an info message."""

    @staticmethod
    def warning(msg: str, **kwargs) -> None:
        """Log a warning message."""

    @staticmethod
    def error(msg: str, **kwargs) -> None:
        """Log an error message."""
```

### Metrics

Tracking and reporting metrics.

```python
class Metrics:
    def __init__(self):
        self.data: Dict[str, List[float]] = {}

    def record(self, name: str, value: float) -> None:
        """Record a metric value."""

    def get_summary(self) -> Dict[str, Dict[str, float]]:
        """Get summary statistics for all metrics."""
```

### Checkpointer

Checkpointing utilities.

```python
class Checkpointer:
    @staticmethod
    def save(
        obj: Any,
        path: Union[str, Path],
        **kwargs
    ) -> None:
        """Save an object to disk."""

    @staticmethod
    def load(
        path: Union[str, Path],
        **kwargs
    ) -> Any:
        """Load an object from disk."""
```

## Exceptions

```python
class EvolutionError(Exception):
    """Base class for evolution errors."""

class ModelError(Exception):
    """Error raised for model-related issues."""

class EvaluationError(Exception):
    """Error raised during evaluation."""

class CheckpointError(Exception):
    """Error raised for checkpointing issues."""
```

## Type Definitions

```python
# Individual in the population
Individual = Dict[str, Any]

# Population is a list of individuals
Population = List[Individual]

# Fitness is a dictionary of metric names to values
Fitness = Dict[str, float]

# Callback function type
Callback = Callable[[Dict[str, Any]], None]
```

## Usage Examples

### Basic Usage

```python
from evoseal import EVOSEAL, OpenAIModel

# Initialize with a model
model = OpenAIModel(api_key="your-api-key")
evoseal = EVOSEAL(model=model)

# Run evolution
result = await evoseal.evolve(
    task="Create a function that reverses a string",
    constraints={"language": "python"}
)

print(f"Best solution: {result.best_solution}")
```

### Custom Fitness Function

```python
from evoseal import FitnessFunction

class LengthFitness(FitnessFunction):
    async def __call__(self, individual, **kwargs):
        return len(individual["code"])

# Use in EVOSEAL
evoseal = EVOSEAL(model)
result = await evoseal.evolve(
    task="...",
    fitness_functions=[LengthFitness()]
)
```

### Custom Evolution Strategy

```python
from evoseal.strategies import BaseStrategy

class MyStrategy(BaseStrategy):
    async def evolve(self, population, evaluator, config):
        # Custom evolution logic
        return new_population

# Use in EVOSEAL
evoseal = EVOSEAL(model, strategy=MyStrategy())
```

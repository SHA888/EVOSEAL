# API Reference

This document provides detailed information about the EVOSEAL API.

## Core Classes

### EVOSEAL

The main class for interacting with the EVOSEAL system.

```python
class EVOSEAL:
    def __init__(self, 
                 model: Optional[BaseModel] = None,
                 fitness_function: Optional[Callable] = None,
                 config: Optional[Dict] = None):
        """
        Initialize the EVOSEAL system.
        
        Args:
            model: The language model to use (default: OpenAI's GPT-4)
            fitness_function: Custom fitness function for solution evaluation
            config: Configuration dictionary
        """
        
    def evolve(self, 
               task: str, 
               max_iterations: int = 100,
               population_size: int = 20,
               **kwargs) -> EvolutionResult:
        """
        Run the evolutionary algorithm.
        
        Args:
            task: Description of the task to solve
            max_iterations: Maximum number of iterations
            population_size: Number of solutions in each generation
            **kwargs: Additional parameters for the evolution process
            
        Returns:
            EvolutionResult containing the best solution and metrics
        """
        
    def save_checkpoint(self, filepath: str) -> None:
        """Save the current state to a checkpoint file."""
        
    @classmethod
    def load_checkpoint(cls, filepath: str) -> 'EVOSEAL':
        """Load a previously saved checkpoint."""
```

## Models

### BaseModel

Abstract base class for all language models.

```python
class BaseModel(ABC):
    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text from a prompt."""
        
    @abstractmethod
    def get_embeddings(self, text: str) -> List[float]:
        """Get embeddings for the given text."""
```

### OpenAIModel

Wrapper for OpenAI models.

```python
class OpenAIModel(BaseModel):
    def __init__(self, model: str = "gpt-4", **kwargs):
        """
        Initialize with a specific OpenAI model.
        
        Args:
            model: Model name (e.g., 'gpt-4', 'gpt-3.5-turbo')
            **kwargs: Additional parameters for the OpenAI API
        """
```

### AnthropicModel

Wrapper for Anthropic models.

```python
class AnthropicModel(BaseModel):
    def __init__(self, model: str = "claude-3-opus", **kwargs):
        """
        Initialize with a specific Anthropic model.
        
        Args:
            model: Model name (e.g., 'claude-3-opus', 'claude-3-sonnet')
            **kwargs: Additional parameters for the Anthropic API
        """
```

## Data Types

### EvolutionResult

```python
@dataclass
class EvolutionResult:
    best_solution: str
    fitness: float
    iterations: int
    history: List[Dict[str, Any]]
    metadata: Dict[str, Any]
```

## Utilities

### Fitness Functions

```python
def default_fitness(solution: str, **kwargs) -> float:
    """
    Default fitness function that evaluates solution quality.
    
    Args:
        solution: The solution to evaluate
        **kwargs: Additional parameters
        
    Returns:
        Fitness score (higher is better)
    """
```

### Checkpointing

```python
def save_checkpoint(evoseal: EVOSEAL, filepath: str) -> None:
    """Save EVOSEAL instance to a file."""
    
def load_checkpoint(filepath: str) -> EVOSEAL:
    """Load EVOSEAL instance from a file."""
```

## Examples

### Basic Usage

```python
from evoseal import EVOSEAL

# Initialize with default settings
evoseal = EVOSEAL()

# Run evolution
result = evoseal.evolve(
    task="Create a Python function that implements binary search",
    max_iterations=30,
    population_size=15
)

# Access results
print(f"Best solution: {result.best_solution}")
print(f"Fitness: {result.fitness}")
```

### Custom Model and Fitness

```python
from evoseal import EVOSEAL, OpenAIModel

def custom_fitness(solution, **kwargs):
    # Your custom fitness logic here
    return score

# Initialize with custom model and fitness
model = OpenAIModel(model="gpt-4")
evoseal = EVOSEAL(
    model=model,
    fitness_function=custom_fitness
)
```
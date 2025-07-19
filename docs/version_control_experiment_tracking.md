# Version Control and Experiment Tracking

This document describes the comprehensive version control and experiment tracking system implemented in EVOSEAL, which enables reproducible experiments, code versioning, and detailed analysis of evolution runs.

## Table of Contents

1. [Overview](#overview)
2. [Core Components](#core-components)
3. [Experiment Models](#experiment-models)
4. [Version Control Integration](#version-control-integration)
5. [Usage Examples](#usage-examples)
6. [API Reference](#api-reference)
7. [Best Practices](#best-practices)

## Overview

The EVOSEAL version control and experiment tracking system provides:

- **Experiment Management**: Create, track, and manage evolution experiments
- **Version Control Integration**: Automatic git integration for code versioning
- **Variant Tracking**: Track code variants and their evolution lineage
- **Metrics Collection**: Comprehensive metrics and performance tracking
- **Artifact Management**: Store and manage experiment artifacts
- **Reproducibility**: Ensure experiments can be reproduced exactly
- **Comparison Tools**: Compare experiments and analyze results
- **Checkpoint System**: Create and restore experiment checkpoints

## Core Components

### 1. ExperimentDatabase

Stores and manages experiment data using SQLite:

```python
from evoseal.core.experiment_database import ExperimentDatabase

# Create database
db = ExperimentDatabase("experiments.db")

# Save experiment
db.save_experiment(experiment)

# Query experiments
experiments = db.list_experiments(
    status=ExperimentStatus.COMPLETED,
    experiment_type=ExperimentType.EVOLUTION,
    limit=10
)
```

### 2. VersionDatabase

Tracks code variants and their relationships:

```python
from evoseal.core.version_database import VersionDatabase

# Create version database
version_db = VersionDatabase()

# Add variant
version_db.add_variant(
    variant_id="v1",
    source="def solution(): return 42",
    test_results={"passed": True},
    eval_score=0.95,
    experiment_id="exp_123"
)

# Get best variants
best_variants = version_db.get_best_variants(
    experiment_id="exp_123",
    limit=5
)
```

### 3. VersionTracker

Integrates version control with experiment tracking:

```python
from evoseal.core.version_tracker import VersionTracker

# Create version tracker
tracker = VersionTracker(work_dir="./evoseal_workspace")

# Create experiment with version info
experiment = tracker.create_experiment_with_version(
    name="Evolution Run 1",
    config=experiment_config,
    repository_name="my_repo",
    branch="main"
)

# Start experiment
tracker.start_experiment(experiment.id)

# Create checkpoint
checkpoint_id = tracker.create_checkpoint(
    experiment.id,
    checkpoint_name="mid_evolution"
)
```

### 4. ExperimentIntegration

High-level integration with evolution pipeline:

```python
from evoseal.core.experiment_integration import ExperimentIntegration

# Create integration
integration = ExperimentIntegration(version_tracker)

# Create and start experiment
experiment = integration.create_evolution_experiment(
    name="My Evolution Run",
    config=config_dict,
    repository_name="my_repo"
)

integration.start_evolution_experiment()

# Track iteration
integration.track_iteration_complete(
    iteration=5,
    fitness_scores=[0.1, 0.3, 0.8, 0.6],
    best_fitness=0.8
)

# Complete experiment
integration.complete_evolution_experiment()
```

## Experiment Models

### ExperimentConfig

Configuration for an experiment:

```python
from evoseal.models.experiment import ExperimentConfig, ExperimentType

config = ExperimentConfig(
    experiment_type=ExperimentType.EVOLUTION,
    seed=42,
    max_iterations=100,
    population_size=50,
    mutation_rate=0.1,
    crossover_rate=0.8,
    selection_pressure=2.0,
    dgm_config={"param1": "value1"},
    openevolve_config={"param2": "value2"},
    seal_config={"param3": "value3"}
)
```

### Experiment

Main experiment model:

```python
from evoseal.models.experiment import Experiment, ExperimentStatus

experiment = Experiment(
    name="My Experiment",
    description="Testing evolution parameters",
    config=config,
    tags=["evolution", "test"],
    created_by="researcher"
)

# Add metrics
experiment.add_metric("fitness", 0.85, MetricType.ACCURACY)
experiment.add_metric("execution_time", 120.5, MetricType.EXECUTION_TIME)

# Add artifacts
artifact = experiment.add_artifact(
    name="final_model",
    artifact_type="model",
    file_path="/path/to/model.pkl"
)

# Control experiment lifecycle
experiment.start()
experiment.complete()
```

### ExperimentMetric

Track metrics during experiments:

```python
from evoseal.models.experiment import ExperimentMetric, MetricType

metric = ExperimentMetric(
    name="best_fitness",
    value=0.92,
    metric_type=MetricType.ACCURACY,
    iteration=10,
    step=500
)
```

## Version Control Integration

### Git Integration

Automatic git integration tracks code changes:

```python
# Repository manager handles git operations
repo_manager = RepositoryManager(work_dir)

# Clone repository
repo_path = repo_manager.clone_repository(
    "https://github.com/user/repo.git",
    "my_repo"
)

# Create experiment with git info
experiment = version_tracker.create_experiment_with_version(
    name="Experiment with Git",
    config=config,
    repository_name="my_repo",
    branch="feature/new-algorithm"
)

# Automatic commit before starting
version_tracker.start_experiment(
    experiment.id,
    auto_commit=True,
    commit_message="Starting experiment"
)

# Automatic tagging on completion
version_tracker.complete_experiment(
    experiment.id,
    create_tag=True
)
```

### Code Versioning

Track code variants with full lineage:

```python
# Track variant creation
integration.track_variant_creation(
    variant_id="variant_gen5_ind3",
    source=generated_code,
    test_results=test_results,
    eval_score=fitness_score,
    parent_ids=["variant_gen4_ind1", "variant_gen4_ind7"],
    generation=5,
    mutation_type="crossover"
)

# Get variant lineage
lineage = version_db.get_lineage("variant_gen5_ind3")
print(f"Parents: {lineage}")

# Get evolution history
history = version_db.get_evolution_history()
```

## Usage Examples

### Basic Experiment Tracking

```python
import asyncio
from evoseal.core.experiment_integration import create_experiment_integration

async def run_tracked_evolution():
    # Create integration
    integration = create_experiment_integration("./workspace")

    # Create experiment
    config = {
        "experiment_type": "evolution",
        "population_size": 30,
        "max_iterations": 50,
        "mutation_rate": 0.1
    }

    experiment = integration.create_evolution_experiment(
        name="Tracked Evolution Run",
        config=config,
        description="Evolution with full tracking"
    )

    # Start experiment
    integration.start_evolution_experiment()

    # Simulate evolution loop
    for iteration in range(1, 51):
        integration.track_iteration_start(iteration)

        # Your evolution logic here
        fitness_scores = simulate_evolution_iteration()
        best_fitness = max(fitness_scores)

        integration.track_iteration_complete(
            iteration=iteration,
            fitness_scores=fitness_scores,
            best_fitness=best_fitness
        )

        # Track performance
        integration.track_performance_metrics(
            execution_time=measure_time(),
            memory_usage=measure_memory()
        )

    # Complete experiment
    integration.complete_evolution_experiment()

# Run the experiment
asyncio.run(run_tracked_evolution())
```

### Experiment Comparison

```python
# Compare multiple experiments
experiment_ids = ["exp1", "exp2", "exp3"]
comparison = version_tracker.compare_experiments(experiment_ids)

print("Configuration differences:")
for param, values in comparison['configurations']['different_parameters'].items():
    print(f"  {param}: {values}")

print("Metric comparison:")
for metric, values in comparison['metrics'].items():
    print(f"  {metric}: {values}")
```

### Checkpoint Management

```python
# Create checkpoint during experiment
checkpoint_id = integration.create_checkpoint("mid_evolution")

# Later, restore from checkpoint
restored_experiment = version_tracker.restore_checkpoint(checkpoint_id)
```

### Data Export/Import

```python
# Export variants
version_db.export_variants(
    experiment_id="exp_123",
    file_path="variants_backup.json"
)

# Import variants
new_db = VersionDatabase()
imported_count = new_db.import_variants("variants_backup.json")
```

## API Reference

### ExperimentDatabase

#### Methods

- `save_experiment(experiment)`: Save experiment to database
- `get_experiment(experiment_id)`: Retrieve experiment by ID
- `list_experiments(**filters)`: List experiments with filtering
- `delete_experiment(experiment_id)`: Delete experiment
- `get_experiment_count(**filters)`: Count experiments

### VersionDatabase

#### Methods

- `add_variant(variant_id, source, test_results, eval_score, **kwargs)`: Add code variant
- `get_variant(variant_id)`: Get variant by ID
- `get_best_variants(experiment_id, limit)`: Get best variants
- `get_variant_statistics(experiment_id)`: Get variant statistics
- `export_variants(experiment_id, file_path)`: Export variants
- `import_variants(json_data)`: Import variants

### VersionTracker

#### Methods

- `create_experiment_with_version(**kwargs)`: Create experiment with git info
- `start_experiment(experiment_id, auto_commit)`: Start experiment
- `complete_experiment(experiment_id, auto_commit, create_tag)`: Complete experiment
- `create_checkpoint(experiment_id, checkpoint_name)`: Create checkpoint
- `restore_checkpoint(checkpoint_id)`: Restore from checkpoint
- `compare_experiments(experiment_ids)`: Compare experiments

### ExperimentIntegration

#### Methods

- `create_evolution_experiment(**kwargs)`: Create evolution experiment
- `start_evolution_experiment()`: Start current experiment
- `complete_evolution_experiment()`: Complete current experiment
- `track_iteration_start(iteration)`: Track iteration start
- `track_iteration_complete(iteration, **metrics)`: Track iteration completion
- `track_variant_creation(**kwargs)`: Track variant creation
- `track_performance_metrics(**metrics)`: Track performance metrics

## Best Practices

### 1. Experiment Organization

```python
# Use descriptive names and tags
experiment = integration.create_evolution_experiment(
    name="DGM_Optimization_v2.1_20240101",
    description="Testing new mutation operators with DGM",
    tags=["dgm", "mutation", "optimization", "v2.1"],
    created_by="researcher_id"
)
```

### 2. Consistent Metrics

```python
# Use consistent metric names across experiments
integration.track_iteration_complete(
    iteration=i,
    fitness_scores=scores,
    best_fitness=max(scores),
    avg_fitness=sum(scores)/len(scores),
    diversity_score=calculate_diversity(population),
    convergence_rate=calculate_convergence(scores)
)
```

### 3. Regular Checkpoints

```python
# Create checkpoints at regular intervals
if iteration % 10 == 0:
    checkpoint_id = integration.create_checkpoint(f"iteration_{iteration}")
    logger.info(f"Created checkpoint: {checkpoint_id}")
```

### 4. Artifact Management

```python
# Store important artifacts
integration.add_artifact(
    name="best_individual",
    artifact_type="code",
    content=best_code,
    fitness_score=best_fitness
)

integration.add_artifact(
    name="evolution_plot",
    artifact_type="visualization",
    file_path="fitness_evolution.png"
)
```

### 5. Error Handling

```python
try:
    # Evolution logic
    result = run_evolution()
    integration.complete_evolution_experiment(result)
except Exception as e:
    # Properly handle failures
    integration.fail_evolution_experiment(e)
    logger.error(f"Experiment failed: {e}")
    raise
```

### 6. Configuration Management

```python
# Use structured configurations
config = ExperimentConfig(
    experiment_type=ExperimentType.EVOLUTION,
    seed=42,  # For reproducibility
    max_iterations=100,
    population_size=50,
    # Component-specific configs
    dgm_config={
        "output_dir": "./dgm_output",
        "prevrun_dir": "./dgm_previous"
    },
    openevolve_config={
        "timeout": 300,
        "parallel_jobs": 4
    },
    seal_config={
        "provider": "openai",
        "model": "gpt-4"
    }
)
```

### 7. Database Maintenance

```python
# Regular cleanup of old experiments
old_experiments = db.list_experiments(
    status=ExperimentStatus.FAILED,
    limit=100,
    order_by="created_at",
    order_desc=False
)

for exp in old_experiments[:50]:  # Keep only recent 50 failed
    db.delete_experiment(exp.id)
```

This comprehensive system enables full reproducibility and detailed analysis of evolution experiments in EVOSEAL, supporting both research and production use cases.

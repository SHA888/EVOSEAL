#!/usr/bin/env python3
"""
Example demonstrating version control and experiment tracking in EVOSEAL.

This example shows how to:
1. Create and manage experiments with version control
2. Track code variants and their evolution
3. Record metrics and artifacts
4. Compare experiments and analyze results
5. Create checkpoints and restore from them
"""

import asyncio
import json
import random
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

# EVOSEAL imports
from evoseal.core.experiment_database import ExperimentDatabase
from evoseal.core.experiment_integration import ExperimentIntegration
from evoseal.core.repository import RepositoryManager
from evoseal.core.version_database import VersionDatabase
from evoseal.core.version_tracker import VersionTracker
from evoseal.models.experiment import (
    ExperimentConfig,
    ExperimentResult,
    ExperimentStatus,
    ExperimentType,
    MetricType,
)


class MockEvolutionPipeline:
    """Mock evolution pipeline for demonstration purposes."""

    def __init__(self, integration: ExperimentIntegration):
        self.integration = integration
        self.population_size = 20
        self.max_iterations = 10

    async def run_evolution(self, config: Dict) -> Dict:
        """Run a mock evolution process."""
        print("🚀 Starting evolution run...")

        # Create experiment
        experiment = self.integration.create_evolution_experiment(
            name=f"Evolution Run {datetime.now().strftime('%Y%m%d_%H%M%S')}",
            config=config,
            repository_name="test_repo",
            description="Mock evolution run for demonstration",
            tags=["demo", "mock", "evolution"],
            created_by="demo_user",
        )

        # Start experiment
        experiment = self.integration.start_evolution_experiment()
        print(f"📊 Started experiment: {experiment.name} (ID: {experiment.id[:8]}...)")

        try:
            # Simulate evolution iterations
            best_fitness = 0.0
            population_fitness = [random.uniform(0.1, 0.5) for _ in range(self.population_size)]

            for iteration in range(1, self.max_iterations + 1):
                print(f"  🔄 Iteration {iteration}/{self.max_iterations}")

                # Track iteration start
                self.integration.track_iteration_start(iteration)

                # Simulate evolution operations
                await asyncio.sleep(0.1)  # Simulate computation time

                # Generate new population with mutations
                new_fitness = []
                for i, fitness in enumerate(population_fitness):
                    # Simulate mutation and selection
                    mutation_strength = random.uniform(-0.1, 0.2)
                    new_fitness_val = max(0.0, fitness + mutation_strength)
                    new_fitness.append(new_fitness_val)

                    # Create variant for some individuals
                    if random.random() < 0.3:  # 30% chance to create variant
                        variant_id = f"variant_{iteration}_{i}"
                        source_code = (
                            f"def solution_{iteration}_{i}():\n    return {new_fitness_val:.3f}"
                        )

                        self.integration.track_variant_creation(
                            variant_id=variant_id,
                            source=source_code,
                            test_results={"passed": random.choice([True, False])},
                            eval_score=new_fitness_val,
                            parent_ids=[f"variant_{iteration-1}_{i}"] if iteration > 1 else None,
                            generation=iteration,
                            individual_index=i,
                        )

                population_fitness = new_fitness
                current_best = max(population_fitness)
                best_fitness = max(best_fitness, current_best)

                # Track iteration completion
                self.integration.track_iteration_complete(
                    iteration=iteration,
                    fitness_scores=population_fitness,
                    best_fitness=current_best,
                    diversity=len(set(f"{f:.2f}" for f in population_fitness)),
                    convergence_rate=abs(current_best - best_fitness) / max(best_fitness, 0.001),
                )

                # Track performance metrics
                self.integration.track_performance_metrics(
                    execution_time=random.uniform(0.5, 2.0),
                    memory_usage=random.uniform(50, 200),
                    cpu_usage=random.uniform(20, 80),
                )

                # Create checkpoint every 3 iterations
                if iteration % 3 == 0:
                    checkpoint_id = self.integration.create_checkpoint(f"iteration_{iteration}")
                    print(f"    💾 Created checkpoint: {checkpoint_id}")

                print(
                    f"    📈 Best fitness: {current_best:.4f}, Avg: {sum(population_fitness)/len(population_fitness):.4f}"
                )

            # Add final artifacts
            self.integration.add_artifact(
                name="final_population",
                artifact_type="data",
                content=json.dumps(population_fitness, indent=2),
                iteration=self.max_iterations,
            )

            self.integration.add_artifact(
                name="evolution_log",
                artifact_type="log",
                content=f"Evolution completed successfully with best fitness: {best_fitness:.4f}",
                final_fitness=best_fitness,
            )

            # Create final result
            result = ExperimentResult(
                final_metrics={
                    "best_fitness": best_fitness,
                    "final_diversity": len(set(f"{f:.2f}" for f in population_fitness)),
                },
                best_fitness=best_fitness,
                generations_completed=self.max_iterations,
                total_evaluations=self.max_iterations * self.population_size,
                convergence_iteration=self.max_iterations if best_fitness > 0.8 else None,
            )

            # Complete experiment
            experiment = self.integration.complete_evolution_experiment(result)
            print(f"✅ Completed experiment: {experiment.name}")

            return {
                "experiment_id": experiment.id,
                "best_fitness": best_fitness,
                "final_population": population_fitness,
                "status": "completed",
            }

        except Exception as e:
            # Handle failure
            experiment = self.integration.fail_evolution_experiment(e)
            print(f"❌ Failed experiment: {experiment.name} - {e}")
            raise


async def demonstrate_version_control_tracking():
    """Demonstrate version control and experiment tracking features."""

    print("🧪 EVOSEAL Version Control & Experiment Tracking Demo")
    print("=" * 60)

    # Create temporary directory for demo
    with tempfile.TemporaryDirectory() as temp_dir:
        work_dir = Path(temp_dir)
        print(f"📁 Working directory: {work_dir}")

        # Initialize version tracker and integration
        version_tracker = VersionTracker(work_dir)
        integration = ExperimentIntegration(version_tracker)

        # Create a mock git repository
        repo_manager = version_tracker.repo_manager
        repo_path = work_dir / "repositories" / "test_repo"
        repo_path.mkdir(parents=True, exist_ok=True)

        # Initialize git repo (mock)
        try:
            from git import Repo

            repo = Repo.init(repo_path)

            # Create initial commit
            test_file = repo_path / "test.py"
            test_file.write_text("# Initial test file\ndef hello():\n    return 'Hello, EVOSEAL!'")
            repo.index.add([str(test_file)])
            repo.index.commit("Initial commit")

            print("📦 Created mock git repository")
        except ImportError:
            print("⚠️  GitPython not available, skipping git integration")

        # Create mock evolution pipeline
        pipeline = MockEvolutionPipeline(integration)

        # Run multiple experiments
        experiments = []

        print("\n🔬 Running Experiments")
        print("-" * 30)

        for i in range(3):
            print(f"\n🧪 Experiment {i+1}/3")

            # Different configurations for each experiment
            configs = [
                {
                    "experiment_type": "evolution",
                    "population_size": 20,
                    "max_iterations": 10,
                    "mutation_rate": 0.1,
                    "crossover_rate": 0.8,
                    "selection_pressure": 2.0,
                },
                {
                    "experiment_type": "optimization",
                    "population_size": 30,
                    "max_iterations": 8,
                    "mutation_rate": 0.15,
                    "crossover_rate": 0.7,
                    "selection_pressure": 2.5,
                },
                {
                    "experiment_type": "comparison",
                    "population_size": 25,
                    "max_iterations": 12,
                    "mutation_rate": 0.05,
                    "crossover_rate": 0.9,
                    "selection_pressure": 1.8,
                },
            ]

            result = await pipeline.run_evolution(configs[i])
            experiments.append(result["experiment_id"])

            # Small delay between experiments
            await asyncio.sleep(0.2)

        print("\n📊 Analyzing Results")
        print("-" * 30)

        # Get experiment summaries
        for i, exp_id in enumerate(experiments):
            summary = integration.get_experiment_summary(exp_id)
            print(f"\n🧪 Experiment {i+1}: {summary['name']}")
            print(f"   Status: {summary['status']}")
            print(
                f"   Duration: {summary['duration']:.2f}s"
                if summary['duration']
                else "   Duration: N/A"
            )
            print(f"   Best Fitness: {summary['latest_metrics'].get('best_fitness', 'N/A')}")
            print(f"   Variants: {summary['variant_statistics']['total_variants']}")
            print(f"   Artifacts: {summary['artifact_count']}")

        # Compare experiments
        print(f"\n🔍 Comparing Experiments")
        print("-" * 30)

        comparison = version_tracker.compare_experiments(experiments)
        print(f"Experiments compared: {len(comparison['experiments'])}")
        print(
            f"Configuration differences: {len(comparison['configurations']['different_parameters'])}"
        )
        print(f"Version consistency: {'Yes' if comparison['versions']['same_commit'] else 'No'}")

        # Show configuration differences
        if comparison['configurations']['different_parameters']:
            print("\nConfiguration differences:")
            for param, values in comparison['configurations']['different_parameters'].items():
                print(f"  {param}: {values}")

        # Analyze variant statistics
        print(f"\n📈 Variant Analysis")
        print("-" * 30)

        for i, exp_id in enumerate(experiments):
            stats = version_tracker.version_db.get_variant_statistics(exp_id)
            print(f"\nExperiment {i+1} variants:")
            print(f"  Total: {stats['total_variants']}")
            if stats['total_variants'] > 0:
                print(f"  Best score: {stats['best_score']:.4f}")
                print(f"  Average score: {stats['average_score']:.4f}")
                print(f"  Score distribution: {stats['score_distribution']}")

        # Demonstrate checkpoint restoration
        print(f"\n💾 Checkpoint Management")
        print("-" * 30)

        # List checkpoints
        checkpoints_dir = work_dir / "checkpoints"
        if checkpoints_dir.exists():
            checkpoints = list(checkpoints_dir.iterdir())
            print(f"Available checkpoints: {len(checkpoints)}")

            if checkpoints:
                # Restore from first checkpoint
                checkpoint_id = checkpoints[0].name
                print(f"Restoring from checkpoint: {checkpoint_id}")

                try:
                    restored_exp = version_tracker.restore_checkpoint(checkpoint_id)
                    print(f"✅ Restored experiment: {restored_exp.name}")
                except Exception as e:
                    print(f"❌ Failed to restore checkpoint: {e}")

        # Export/Import demonstration
        print(f"\n📤 Data Export/Import")
        print("-" * 30)

        # Export variants for first experiment
        if experiments:
            export_file = work_dir / "variants_export.json"
            version_tracker.version_db.export_variants(
                experiment_id=experiments[0], file_path=export_file
            )
            print(f"✅ Exported variants to: {export_file}")

            # Import to new database (demonstration)
            new_db = VersionDatabase()
            imported_count = new_db.import_variants(export_file)
            print(f"✅ Imported {imported_count} variants to new database")

        # Final statistics
        print(f"\n📊 Final Statistics")
        print("-" * 30)

        total_experiments = len(experiments)
        total_variants = sum(
            version_tracker.version_db.get_variant_statistics(exp_id)['total_variants']
            for exp_id in experiments
        )

        print(f"Total experiments: {total_experiments}")
        print(f"Total variants created: {total_variants}")
        print(f"Database size: {work_dir}")

        # Show experiment lineage for first experiment
        if experiments:
            lineage = version_tracker.get_experiment_lineage(experiments[0])
            print(f"\nExperiment lineage:")
            print(f"  Ancestors: {lineage['total_ancestors']}")
            print(f"  Descendants: {lineage['total_descendants']}")

        print(f"\n✅ Demo completed successfully!")
        print(f"📁 All data stored in: {work_dir}")


if __name__ == "__main__":
    # Run the demonstration
    asyncio.run(demonstrate_version_control_tracking())

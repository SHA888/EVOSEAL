"""Comprehensive example demonstrating EVOSEAL's error handling and resilience features.

This example shows how to use the enhanced error handling, recovery mechanisms,
circuit breakers, health monitoring, and logging systems in the EVOSEAL pipeline.
"""

import asyncio
import logging
import random
import time
from datetime import datetime
from pathlib import Path

# EVOSEAL imports
from evoseal.core.error_recovery import (
    ErrorPattern,
    RecoveryAction,
    RecoveryStrategy,
    error_recovery_manager,
    with_error_recovery,
)
from evoseal.core.errors import BaseError, ErrorCategory, ErrorSeverity
from evoseal.core.evolution_pipeline import EvolutionPipeline
from evoseal.core.logging_system import get_logger, logging_manager
from evoseal.core.resilience import (
    CircuitBreakerConfig,
    ComponentHealth,
    resilience_manager,
)
from evoseal.core.resilience_integration import (
    get_resilience_status,
    initialize_resilience_system,
    resilience_orchestrator,
)
from evoseal.models.evolution_config import EvolutionConfig

# Set up logging
logger = get_logger("resilience_example")


class MockComponent:
    """Mock component that simulates various failure scenarios."""

    def __init__(self, name: str, failure_rate: float = 0.1):
        self.name = name
        self.failure_rate = failure_rate
        self.call_count = 0
        self.failure_count = 0

    async def operation(self, data: str = "test") -> str:
        """Mock operation that may fail."""
        self.call_count += 1

        # Simulate random failures
        if random.random() < self.failure_rate:
            self.failure_count += 1
            error_types = [
                ConnectionError("Network connection failed"),
                TimeoutError("Operation timed out"),
                MemoryError("Out of memory"),
                ValueError("Invalid input data"),
            ]
            raise random.choice(error_types)

        # Simulate processing time
        await asyncio.sleep(0.1)
        return f"{self.name} processed: {data}"


class ResilienceDemo:
    """Demonstrates resilience features."""

    def __init__(self):
        self.components = {
            "stable": MockComponent("stable", failure_rate=0.05),
            "unreliable": MockComponent("unreliable", failure_rate=0.3),
            "critical": MockComponent("critical", failure_rate=0.15),
        }

    async def setup_resilience_mechanisms(self):
        """Set up resilience mechanisms for the demo."""
        logger.info("Setting up resilience mechanisms")

        # Initialize resilience system
        await initialize_resilience_system()

        # Register circuit breakers for components
        for name in self.components.keys():
            resilience_manager.register_circuit_breaker(
                name,
                CircuitBreakerConfig(
                    failure_threshold=3,
                    recovery_timeout=10,  # Short timeout for demo
                    success_threshold=2,
                    timeout=5.0,
                ),
            )

        # Register custom recovery strategies
        error_recovery_manager.classifier.register_pattern(
            ErrorPattern(
                error_type="ConnectionError",
                component="unreliable",
                recovery_strategy=RecoveryStrategy(
                    max_retries=5,
                    retry_delay=1.0,
                    recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK],
                ),
            )
        )

        # Register fallback handlers
        error_recovery_manager.fallback_manager.register_fallback(
            "unreliable", "operation", self._unreliable_fallback
        )
        error_recovery_manager.fallback_manager.register_fallback(
            "critical", "operation", self._critical_fallback
        )

        # Register recovery strategies
        resilience_manager.register_recovery_strategy(
            "demo", self._demo_recovery_strategy
        )

        logger.info("Resilience mechanisms configured")

    async def _unreliable_fallback(self, *args, context=None, **kwargs):
        """Fallback for unreliable component."""
        logger.info("Using fallback for unreliable component")
        return "FALLBACK: Cached result from unreliable component"

    async def _critical_fallback(self, *args, context=None, **kwargs):
        """Fallback for critical component."""
        logger.info("Using fallback for critical component")
        return "FALLBACK: Emergency response from critical component"

    async def _demo_recovery_strategy(
        self, component: str, operation: str, error: Exception
    ):
        """Custom recovery strategy for demo."""
        logger.info(f"Executing custom recovery for {component}:{operation}")
        await asyncio.sleep(0.5)  # Simulate recovery time
        logger.info(f"Recovery completed for {component}")

    @with_error_recovery("demo", "run_with_resilience")
    async def run_component_with_resilience(
        self, component_name: str, data: str
    ) -> str:
        """Run a component operation with full resilience support."""
        component = self.components[component_name]

        return await resilience_manager.execute_with_resilience(
            component_name, "operation", component.operation, data
        )

    async def demonstrate_circuit_breaker(self):
        """Demonstrate circuit breaker functionality."""
        logger.info("=== Circuit Breaker Demo ===")

        # Make multiple calls to trigger circuit breaker
        for i in range(10):
            try:
                result = await self.run_component_with_resilience(
                    "unreliable", f"request_{i}"
                )
                logger.info(f"Call {i+1}: {result}")
            except Exception as e:
                logger.warning(f"Call {i+1} failed: {e}")

            await asyncio.sleep(0.5)

        # Show circuit breaker status
        status = resilience_manager.get_resilience_status()
        cb_status = status["circuit_breakers"].get("unreliable", {})
        logger.info(f"Circuit breaker status: {cb_status}")

    async def demonstrate_health_monitoring(self):
        """Demonstrate health monitoring."""
        logger.info("=== Health Monitoring Demo ===")

        # Generate some operations to create health data
        for component_name in self.components.keys():
            for i in range(5):
                try:
                    await self.run_component_with_resilience(
                        component_name, f"health_check_{i}"
                    )
                except Exception:  # nosec B110
                    pass  # Expected failures for demo purposes

        # Show health metrics
        for component_name in self.components.keys():
            health = resilience_manager.health_monitor.get_component_health(
                component_name
            )
            if health:
                logger.info(
                    f"{component_name} health: {health.health_status.value} "
                    f"(success rate: {health.success_rate:.2%})"
                )

    async def demonstrate_error_recovery(self):
        """Demonstrate error recovery mechanisms."""
        logger.info("=== Error Recovery Demo ===")

        # Test different recovery scenarios
        scenarios = [
            ("stable", "Should succeed"),
            ("unreliable", "May fail but should recover"),
            ("critical", "Critical component test"),
        ]

        for component_name, description in scenarios:
            logger.info(f"Testing {component_name}: {description}")
            try:
                result = await self.run_component_with_resilience(
                    component_name, "recovery_test"
                )
                logger.info(f"Result: {result}")
            except Exception as e:
                logger.error(f"Final failure: {e}")

            await asyncio.sleep(1)

    async def demonstrate_logging_features(self):
        """Demonstrate enhanced logging features."""
        logger.info("=== Enhanced Logging Demo ===")

        # Log different types of events
        logger.log_pipeline_stage("demo_stage", "started", iteration=1)

        logger.log_component_operation(
            component="demo_component",
            operation="test_operation",
            status="success",
            duration=1.5,
        )

        logger.log_performance_metric(
            metric_name="throughput",
            value=150.5,
            unit="ops/sec",
            component="demo_component",
        )

        # Simulate an error for logging
        try:
            raise ValueError("Demo error for logging")
        except Exception as e:
            logger.log_error_with_context(
                error=e,
                component="demo_component",
                operation="error_demo",
                context_data="additional context",
            )

        # Show logging metrics
        metrics = logger.get_metrics()
        if metrics:
            logger.info(
                f"Logging metrics: {metrics.total_logs} total logs, "
                f"{metrics.error_rate:.2%} error rate"
            )

    async def demonstrate_comprehensive_resilience(self):
        """Demonstrate comprehensive resilience in a pipeline scenario."""
        logger.info("=== Comprehensive Resilience Demo ===")

        # Simulate a pipeline with multiple components
        pipeline_steps = [
            ("stable", "Initialize"),
            ("unreliable", "Process data"),
            ("critical", "Validate results"),
            ("stable", "Finalize"),
        ]

        results = []
        for step_num, (component_name, step_description) in enumerate(
            pipeline_steps, 1
        ):
            logger.log_pipeline_stage(
                f"step_{step_num}",
                "started",
                iteration=1,
                step_description=step_description,
            )

            try:
                start_time = time.time()
                result = await self.run_component_with_resilience(
                    component_name, f"pipeline_step_{step_num}"
                )
                duration = time.time() - start_time

                results.append(result)

                logger.log_pipeline_stage(
                    f"step_{step_num}", "completed", iteration=1, duration=duration
                )
                logger.log_component_operation(
                    component=component_name,
                    operation=f"step_{step_num}",
                    status="success",
                    duration=duration,
                )

            except Exception as e:
                logger.log_pipeline_stage(
                    f"step_{step_num}", "failed", iteration=1, error=str(e)
                )
                logger.log_error_with_context(
                    error=e,
                    component=component_name,
                    operation=f"pipeline_step_{step_num}",
                    step_number=step_num,
                )
                # Continue with next step (graceful degradation)
                results.append(f"FAILED: {str(e)}")

        logger.info(f"Pipeline completed with {len(results)} steps")
        return results

    def show_final_statistics(self):
        """Show final statistics and status."""
        logger.info("=== Final Statistics ===")

        # Component statistics
        for name, component in self.components.items():
            success_rate = (component.call_count - component.failure_count) / max(
                component.call_count, 1
            )
            logger.info(
                f"{name}: {component.call_count} calls, "
                f"{component.failure_count} failures, "
                f"{success_rate:.2%} success rate"
            )

        # Recovery statistics
        recovery_stats = error_recovery_manager.get_recovery_statistics()
        if recovery_stats:
            logger.info(f"Recovery attempts: {recovery_stats.get('total_attempts', 0)}")
            logger.info(
                f"Recovery success rate: {recovery_stats.get('success_rate', 0):.2%}"
            )

        # Resilience status
        resilience_status = get_resilience_status()
        logger.info("Resilience system status available")

        # Logging summary
        if logger.aggregator:
            table = logger.display_log_summary()
            print("\nLog Summary:")
            print(table)


async def run_evolution_pipeline_with_resilience():
    """Demonstrate resilience in actual evolution pipeline."""
    logger.info("=== Evolution Pipeline Resilience Demo ===")

    try:
        # Create pipeline with resilience
        config = EvolutionConfig(
            # Add any specific configuration
        )

        pipeline = EvolutionPipeline(config)

        # Initialize components (this will use resilience mechanisms)
        success = await pipeline.initialize_components()
        logger.info(f"Pipeline initialization: {'success' if success else 'failed'}")

        if success:
            # Run a single iteration to demonstrate resilience
            logger.info("Running evolution iteration with resilience")
            result = await pipeline._run_single_iteration(1)
            logger.info(f"Iteration result: {result.get('success', False)}")

            # Show resilience status
            if "resilience_status" in result:
                logger.info("Resilience mechanisms active during iteration")

    except Exception as e:
        logger.log_error_with_context(
            error=e,
            component="evolution_pipeline",
            operation="demo_run",
        )


async def main():
    """Main demo function."""
    print("🛡️  EVOSEAL Error Handling and Resilience Demo")
    print("=" * 60)

    demo = ResilienceDemo()

    try:
        # Set up resilience mechanisms
        await demo.setup_resilience_mechanisms()

        # Run demonstrations
        await demo.demonstrate_circuit_breaker()
        await asyncio.sleep(2)

        await demo.demonstrate_health_monitoring()
        await asyncio.sleep(2)

        await demo.demonstrate_error_recovery()
        await asyncio.sleep(2)

        await demo.demonstrate_logging_features()
        await asyncio.sleep(2)

        await demo.demonstrate_comprehensive_resilience()
        await asyncio.sleep(2)

        # Demonstrate with actual pipeline
        await run_evolution_pipeline_with_resilience()

        # Show final statistics
        demo.show_final_statistics()

        print("\n✅ Demo completed successfully!")
        print("\nKey features demonstrated:")
        print("- Circuit breakers for failure isolation")
        print("- Automatic error recovery with multiple strategies")
        print("- Health monitoring and alerting")
        print("- Enhanced structured logging with metrics")
        print("- Graceful degradation and fallback mechanisms")
        print("- Comprehensive resilience integration")

    except Exception as e:
        logger.log_error_with_context(
            error=e,
            component="demo",
            operation="main",
        )
        print(f"\n❌ Demo failed: {e}")

    finally:
        # Cleanup
        try:
            await resilience_orchestrator.shutdown()
            logging_manager.shutdown()
        except Exception as e:
            print(f"Cleanup error: {e}")


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())

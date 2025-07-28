"""Simple test of EVOSEAL's error handling and resilience features."""

import asyncio
import logging
import secrets
import time
from datetime import datetime

# EVOSEAL imports
from evoseal.core.error_recovery import (
    ErrorPattern,
    RecoveryAction,
    RecoveryStrategy,
    error_recovery_manager,
    with_error_recovery,
)
from evoseal.core.errors import BaseError, ErrorCategory, ErrorSeverity
from evoseal.core.logging_system import get_logger, logging_manager
from evoseal.core.resilience import CircuitBreakerConfig, ComponentHealth, resilience_manager
from evoseal.core.resilience_integration import (
    get_resilience_status,
    initialize_resilience_system,
    resilience_orchestrator,
)

# Set up logging
logger = get_logger("resilience_test")


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

        # Simulate random failures using cryptographically secure random number generator
        secure_random = secrets.SystemRandom()
        if secure_random.random() < self.failure_rate:
            self.failure_count += 1
            error_types = [
                ConnectionError("Network connection failed"),
                TimeoutError("Operation timed out"),
                ValueError("Invalid input data"),
            ]
            raise random.choice(error_types)

        # Simulate processing time
        await asyncio.sleep(0.1)
        return f"{self.name} processed: {data}"


class SimpleResilienceTest:
    """Simple resilience test without full pipeline."""

    def __init__(self):
        self.components = {
            "stable": MockComponent("stable", failure_rate=0.05),
            "unreliable": MockComponent("unreliable", failure_rate=0.3),
        }

    async def setup_resilience_mechanisms(self):
        """Set up resilience mechanisms for the test."""
        logger.info("Setting up resilience mechanisms")

        # Start resilience monitoring
        await resilience_manager.start_monitoring()

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

        logger.info("Resilience mechanisms configured")

    async def _unreliable_fallback(self, *args, context=None, **kwargs):
        """Fallback for unreliable component."""
        logger.info("Using fallback for unreliable component")
        return "FALLBACK: Cached result from unreliable component"

    @with_error_recovery("demo", "run_with_resilience")
    async def run_component_with_resilience(self, component_name: str, data: str) -> str:
        """Run a component operation with full resilience support."""
        component = self.components[component_name]

        return await resilience_manager.execute_with_resilience(
            component_name, "operation", component.operation, data
        )

    async def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        logger.info("=== Circuit Breaker Test ===")

        # Make multiple calls to trigger circuit breaker
        for i in range(8):
            try:
                result = await self.run_component_with_resilience("unreliable", f"request_{i}")
                logger.info(f"Call {i+1}: SUCCESS - {result}")
            except Exception as e:
                logger.warning(f"Call {i+1}: FAILED - {e}")

            await asyncio.sleep(0.5)

        # Show circuit breaker status
        status = resilience_manager.get_resilience_status()
        cb_status = status["circuit_breakers"].get("unreliable", {})
        logger.info(f"Circuit breaker status: {cb_status}")

    async def test_error_recovery(self):
        """Test error recovery mechanisms."""
        logger.info("=== Error Recovery Test ===")

        # Test different recovery scenarios
        scenarios = [
            ("stable", "Should succeed"),
            ("unreliable", "May fail but should recover"),
        ]

        for component_name, description in scenarios:
            logger.info(f"Testing {component_name}: {description}")
            try:
                result = await self.run_component_with_resilience(component_name, "recovery_test")
                logger.info(f"Result: {result}")
            except Exception as e:
                logger.error(f"Final failure: {e}")

            await asyncio.sleep(1)

    async def test_logging_features(self):
        """Test enhanced logging features."""
        logger.info("=== Enhanced Logging Test ===")

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
            logger.info(f"Recovery success rate: {recovery_stats.get('success_rate', 0):.2%}")

        # Resilience status
        resilience_status = get_resilience_status()
        logger.info("Resilience system status available")


async def main():
    """Main test function."""
    print("🛡️  EVOSEAL Error Handling and Resilience Test")
    print("=" * 60)

    test = SimpleResilienceTest()

    try:
        # Set up resilience mechanisms
        await test.setup_resilience_mechanisms()

        # Run tests
        await test.test_circuit_breaker()
        await asyncio.sleep(2)

        await test.test_error_recovery()
        await asyncio.sleep(2)

        await test.test_logging_features()
        await asyncio.sleep(2)

        # Show final statistics
        test.show_final_statistics()

        print("\n✅ Test completed successfully!")
        print("\nKey features tested:")
        print("- Circuit breakers for failure isolation")
        print("- Automatic error recovery with multiple strategies")
        print("- Enhanced structured logging with metrics")
        print("- Graceful degradation and fallback mechanisms")

    except Exception as e:
        logger.log_error_with_context(
            error=e,
            component="test",
            operation="main",
        )
        print(f"\n❌ Test failed: {e}")

    finally:
        # Cleanup
        try:
            await resilience_manager.stop_monitoring()
            logging_manager.shutdown()
        except Exception as e:
            print(f"Cleanup error: {e}")


if __name__ == "__main__":
    # Run the test
    asyncio.run(main())

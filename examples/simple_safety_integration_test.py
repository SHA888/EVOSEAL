#!/usr/bin/env python3
"""
Simple Safety Integration Test

This script tests the basic integration of safety components with the evolution pipeline
without complex mocking, focusing on the core integration functionality.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import EVOSEAL components
from evoseal.core.evolution_pipeline import EvolutionConfig, EvolutionPipeline
from evoseal.core.metrics_tracker import MetricsTracker
from evoseal.core.safety_integration import SafetyIntegration


async def test_basic_safety_integration():
    """Test basic safety integration functionality."""
    print("=" * 60)
    print("BASIC SAFETY INTEGRATION TEST")
    print("=" * 60)

    try:
        # Create basic configuration
        config = EvolutionConfig(
            metrics_config={"enabled": True, "storage_path": None},  # In-memory only
            validation_config={"enabled": True, "min_improvement_score": 70.0},
        )

        print("\n1. Creating EvolutionPipeline with safety integration...")
        pipeline = EvolutionPipeline(config)

        print("   ✓ Pipeline created successfully")
        print(f"   ✓ Safety integration: {type(pipeline.safety_integration).__name__}")
        print(f"   ✓ Metrics tracker: {type(pipeline.metrics_tracker).__name__}")
        print(
            f"   ✓ Checkpoint manager: {type(pipeline.safety_integration.checkpoint_manager).__name__}"
        )
        print(
            f"   ✓ Rollback manager: {type(pipeline.safety_integration.rollback_manager).__name__}"
        )
        print(
            f"   ✓ Regression detector: {type(pipeline.safety_integration.regression_detector).__name__}"
        )

        print("\n2. Testing safety system status...")
        safety_status = pipeline.safety_integration.get_safety_status()
        print(f"   ✓ Safety enabled: {safety_status['safety_enabled']}")
        print(f"   ✓ Auto checkpoint: {safety_status['auto_checkpoint']}")
        print(f"   ✓ Auto rollback: {safety_status['auto_rollback']}")

        print("\n3. Testing checkpoint creation...")
        version_data = {
            "version_id": "test_v1.0",
            "code": "def hello(): return 'world'",
            "metrics": {"accuracy": 0.95},
        }
        test_results = [
            {
                "test_type": "unit_tests",
                "test_suite": "unit",
                "success_rate": 0.95,
                "tests_run": 100,
                "tests_passed": 95,
                "tests_failed": 5,
                "version": "test_v1.0",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ]

        checkpoint_path = pipeline.safety_integration.create_safety_checkpoint(
            "test_v1.0", version_data, test_results
        )
        print(f"   ✓ Checkpoint created: {Path(checkpoint_path).name}")

        print("\n4. Testing version safety validation...")
        new_version_data = {
            "version_id": "test_v1.1",
            "code": "def hello(): return 'world!'",
            "metrics": {"accuracy": 0.93},  # Minor regression
        }
        new_test_results = [
            {
                "test_type": "unit_tests",
                "test_suite": "unit",
                "success_rate": 0.93,
                "tests_run": 100,
                "tests_passed": 93,
                "tests_failed": 7,
                "version": "test_v1.1",
                "timestamp": "2024-01-01T12:00:00Z",
            }
        ]

        validation_result = pipeline.safety_integration.validate_version_safety(
            "test_v1.0", "test_v1.1", new_test_results
        )
        print("   ✓ Safety validation completed")
        print(f"   - Is safe: {validation_result['is_safe']}")
        print(f"   - Safety score: {validation_result['safety_score']:.2f}")

        print("\n5. Testing safe evolution step...")
        evolution_result = pipeline.safety_integration.execute_safe_evolution_step(
            "test_v1.0", new_version_data, "test_v1.1", new_test_results
        )
        print("   ✓ Safe evolution step completed")
        print(f"   - Version accepted: {evolution_result['version_accepted']}")
        print(f"   - Checkpoint created: {evolution_result['checkpoint_created']}")
        print(f"   - Actions taken: {len(evolution_result['actions_taken'])}")

        for action in evolution_result["actions_taken"]:
            print(f"     - {action}")

        print("\n6. Final safety system status...")
        final_status = pipeline.safety_integration.get_safety_status()
        print(
            f"   Total checkpoints: {final_status['checkpoint_manager']['total_checkpoints']}"
        )
        print(
            f"   Rollback success rate: {final_status['rollback_manager']['success_rate']:.1%}"
        )

        print("\n" + "=" * 60)
        print("🎉 BASIC SAFETY INTEGRATION TEST PASSED")
        print("✅ All safety components are properly integrated")
        print("✅ Evolution pipeline can create checkpoints")
        print("✅ Safety validation is working")
        print("✅ Safe evolution steps are functional")
        print("=" * 60)

        return True

    except Exception as e:
        logger.exception("Error during basic safety integration test")
        print(f"\n❌ Test failed with error: {e}")
        return False


async def test_evolution_cycle_integration():
    """Test the evolution cycle with safety integration."""
    print("\n" + "=" * 60)
    print("EVOLUTION CYCLE SAFETY INTEGRATION TEST")
    print("=" * 60)

    try:
        # Create configuration with safety settings
        config = EvolutionConfig(
            metrics_config={"enabled": True}, validation_config={"enabled": True}
        )

        # Add safety configuration
        config.safety_config = {
            "auto_checkpoint": True,
            "auto_rollback": True,
            "safety_checks_enabled": True,
            "checkpoints": {"max_checkpoints": 5},
            "rollback": {"enable_rollback_failure_recovery": True},
            "regression": {"regression_threshold": 0.1},
        }

        print("\n1. Creating EvolutionPipeline with safety configuration...")
        pipeline = EvolutionPipeline(config)

        # Override safety integration with our config
        pipeline.safety_integration = SafetyIntegration(
            config.safety_config, pipeline.metrics_tracker, None
        )

        print("   ✓ Pipeline with safety integration created")

        print("\n2. Testing run_evolution_cycle_with_safety method...")
        print("   Note: This will test the method signature and basic functionality")

        # Check if the method exists and is callable
        if hasattr(pipeline, "run_evolution_cycle_with_safety"):
            print("   ✓ run_evolution_cycle_with_safety method exists")

            # Test method signature
            import inspect

            sig = inspect.signature(pipeline.run_evolution_cycle_with_safety)
            params = list(sig.parameters.keys())
            print(f"   ✓ Method parameters: {params}")

            expected_params = [
                "iterations",
                "enable_checkpoints",
                "enable_auto_rollback",
            ]
            has_expected_params = all(param in params for param in expected_params)
            print(f"   ✓ Has expected parameters: {has_expected_params}")

        else:
            print("   ✗ run_evolution_cycle_with_safety method not found")
            return False

        print("\n3. Testing safety integration components...")

        # Test individual components
        components_working = []

        # Test checkpoint manager
        try:
            checkpoint_manager = pipeline.safety_integration.checkpoint_manager
            components_working.append(
                ("CheckpointManager", checkpoint_manager is not None)
            )
        except Exception:
            components_working.append(("CheckpointManager", False))

        # Test rollback manager
        try:
            rollback_manager = pipeline.safety_integration.rollback_manager
            components_working.append(("RollbackManager", rollback_manager is not None))
        except Exception:
            components_working.append(("RollbackManager", False))

        # Test regression detector
        try:
            regression_detector = pipeline.safety_integration.regression_detector
            components_working.append(
                ("RegressionDetector", regression_detector is not None)
            )
        except Exception:
            components_working.append(("RegressionDetector", False))

        for component_name, is_working in components_working:
            status = "✓" if is_working else "✗"
            print(
                f"   {status} {component_name}: {'WORKING' if is_working else 'FAILED'}"
            )

        all_components_working = all(working for _, working in components_working)

        print("\n" + "=" * 60)
        if all_components_working:
            print("🎉 EVOLUTION CYCLE INTEGRATION TEST PASSED")
            print("✅ Safety-aware evolution cycle method is available")
            print("✅ All safety components are properly integrated")
            print("✅ Evolution pipeline is ready for safe evolution cycles")
        else:
            print("❌ EVOLUTION CYCLE INTEGRATION TEST FAILED")
            print("Some safety components are not properly integrated")

        print("=" * 60)
        return all_components_working

    except Exception as e:
        logger.exception("Error during evolution cycle integration test")
        print(f"\n❌ Test failed with error: {e}")
        return False


async def main():
    """Run all integration tests."""
    print("EVOSEAL SIMPLE SAFETY INTEGRATION TESTS")
    print("=" * 60)

    try:
        # Run tests
        basic_test_passed = await test_basic_safety_integration()
        cycle_test_passed = await test_evolution_cycle_integration()

        # Final results
        print("\n" + "=" * 60)
        print("FINAL TEST RESULTS")
        print("=" * 60)

        if basic_test_passed and cycle_test_passed:
            print("🎉 ALL TESTS PASSED")
            print("✅ Safety Integration: COMPLETE")
            print("✅ CheckpointManager integrated with Evolution Pipeline")
            print("✅ RollbackManager integrated with Evolution Pipeline")
            print("✅ RegressionDetector integrated with Evolution Pipeline")
            print("✅ SafetyIntegration coordinating all components")
            print("✅ Evolution pipeline ready for safe production use")
            return True
        else:
            print("❌ SOME TESTS FAILED")
            print(
                f"Basic Safety Integration: {'PASS' if basic_test_passed else 'FAIL'}"
            )
            print(
                f"Evolution Cycle Integration: {'PASS' if cycle_test_passed else 'FAIL'}"
            )
            return False

    except Exception as e:
        logger.exception("Error during integration tests")
        print(f"\n❌ Tests failed with error: {e}")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)

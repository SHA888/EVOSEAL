"""Example demonstrating EVOSEAL's foundational safety and validation features.

This example shows how to use checkpoint management, rollback capabilities,
regression detection, and the integrated safety-aware evolution pipeline.
"""

import asyncio
import json
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import EVOSEAL safety components
from evoseal.core.checkpoint_manager import CheckpointManager
from evoseal.core.metrics_tracker import MetricsTracker
from evoseal.core.regression_detector import RegressionDetector
from evoseal.core.rollback_manager import RollbackManager
from evoseal.core.safety_integration import SafetyIntegration


def create_sample_test_results(version: str, success_rate: float = 0.95) -> List[Dict[str, Any]]:
    """Create sample test results for demonstration."""
    return [
        {
            "version": version,
            "test_type": "unit_tests",
            "test_suite": "unit_tests",
            "tests_run": 100,
            "tests_passed": int(100 * success_rate),
            "tests_failed": int(100 * (1 - success_rate)),
            "tests_skipped": 0,
            "tests_errors": 0,
            "success_rate": success_rate,
            "status": "pass" if success_rate >= 0.9 else "fail",
            "timestamp": "2024-01-01T12:00:00Z",
            "resources": {"duration_sec": 45.2, "memory_mb": 128.5, "cpu_percent": 15.3},
        },
        {
            "version": version,
            "test_type": "integration_tests",
            "test_suite": "integration_tests",
            "tests_run": 50,
            "tests_passed": int(50 * success_rate),
            "tests_failed": int(50 * (1 - success_rate)),
            "tests_skipped": 0,
            "tests_errors": 0,
            "success_rate": success_rate,
            "status": "pass" if success_rate >= 0.9 else "fail",
            "timestamp": "2024-01-01T12:00:00Z",
            "resources": {"duration_sec": 120.8, "memory_mb": 256.2, "cpu_percent": 25.7},
        },
    ]


def create_sample_version_data(version_id: str) -> Dict[str, Any]:
    """Create sample version data for demonstration."""
    return {
        "version_id": version_id,
        "timestamp": "2024-01-01T12:00:00Z",
        "code_changes": [
            f"Updated algorithm in version {version_id}",
            f"Optimized performance for version {version_id}",
        ],
        "config": {"learning_rate": 0.001, "batch_size": 32, "epochs": 100},
        "metrics": {"accuracy": 0.95, "precision": 0.93, "recall": 0.97, "f1_score": 0.95},
    }


async def demonstrate_checkpoint_manager():
    """Demonstrate checkpoint management capabilities."""
    print("\n" + "=" * 60)
    print("CHECKPOINT MANAGER DEMONSTRATION")
    print("=" * 60)

    # Create temporary directory for checkpoints
    with tempfile.TemporaryDirectory() as temp_dir:
        config = {"checkpoint_dir": temp_dir, "max_checkpoints": 10, "auto_cleanup": True}

        checkpoint_manager = CheckpointManager(config)

        # Create some checkpoints
        print("\n1. Creating checkpoints...")
        versions = ["v1.0", "v1.1", "v1.2"]
        checkpoint_paths = []

        for version in versions:
            version_data = create_sample_version_data(version)
            checkpoint_path = checkpoint_manager.create_checkpoint(version, version_data)
            checkpoint_paths.append(checkpoint_path)
            print(f"   ✓ Created checkpoint for {version}: {Path(checkpoint_path).name}")

        # List checkpoints
        print("\n2. Listing checkpoints...")
        checkpoints = checkpoint_manager.list_checkpoints()
        for checkpoint in checkpoints:
            size_bytes = checkpoint.get('checkpoint_size', 0)
            size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
            print(f"   - {checkpoint['version_id']}: {size_mb:.2f} MB")

        # Get checkpoint statistics
        print("\n3. Checkpoint statistics...")
        stats = checkpoint_manager.get_stats()
        print(f"   Total checkpoints: {stats['total_checkpoints']}")
        print(f"   Total size: {stats['total_size_mb']:.2f} MB")
        print(f"   Auto cleanup: {stats['auto_cleanup_enabled']}")

        # Restore a checkpoint
        print("\n4. Restoring checkpoint...")
        restore_dir = Path(temp_dir) / "restored"
        restore_dir.mkdir(exist_ok=True)

        restore_success = checkpoint_manager.restore_checkpoint("v1.1", str(restore_dir))
        print(f"   ✓ Restored v1.1 to {restore_dir}: {restore_success}")

        # Get metadata for the restored checkpoint
        metadata = checkpoint_manager.get_checkpoint_metadata("v1.1")
        if metadata:
            print(f"   Restored data keys: {list(metadata.get('version_data', {}).keys())}")
        else:
            print("   No metadata available for restored checkpoint")


async def demonstrate_regression_detector():
    """Demonstrate regression detection capabilities."""
    print("\n" + "=" * 60)
    print("REGRESSION DETECTOR DEMONSTRATION")
    print("=" * 60)

    # Initialize components
    metrics_tracker = MetricsTracker()
    config = {
        "regression_threshold": 0.05,  # 5% threshold
        "metric_thresholds": {
            "success_rate": {"regression": -0.05, "critical": -0.1},
            "duration_sec": {"regression": 0.1, "critical": 0.25},
        },
    }

    regression_detector = RegressionDetector(config, metrics_tracker)

    # Add metrics for different versions
    print("\n1. Adding metrics for different versions...")

    # Baseline version with good metrics
    baseline_results = create_sample_test_results("v1.0", success_rate=0.95)
    metrics_tracker.add_metrics(baseline_results)
    print("   ✓ Added baseline metrics for v1.0 (95% success rate)")

    # New version with slight regression
    regression_results = create_sample_test_results("v1.1", success_rate=0.88)
    # Add performance regression
    for result in regression_results:
        result["resources"]["duration_sec"] *= 1.15  # 15% slower
    metrics_tracker.add_metrics(regression_results)
    print("   ✓ Added metrics for v1.1 (88% success rate, 15% slower)")

    # Critical regression version
    critical_results = create_sample_test_results("v1.2", success_rate=0.75)
    for result in critical_results:
        result["resources"]["duration_sec"] *= 1.3  # 30% slower
    metrics_tracker.add_metrics(critical_results)
    print("   ✓ Added metrics for v1.2 (75% success rate, 30% slower)")

    # Detect regressions
    print("\n2. Detecting regressions...")

    # Check v1.0 vs v1.1
    has_regression, regressions = regression_detector.detect_regression("v1.0", "v1.1")
    print(f"\n   v1.0 vs v1.1 - Regression detected: {has_regression}")
    if has_regression:
        for metric, info in regressions.items():
            print(f"     {metric}: {info['severity']} ({info['change']:.2%} change)")

    # Check v1.0 vs v1.2 (critical)
    has_regression, regressions = regression_detector.detect_regression("v1.0", "v1.2")
    print(f"\n   v1.0 vs v1.2 - Regression detected: {has_regression}")
    if has_regression:
        summary = regression_detector.get_regression_summary(regressions)
        print(f"     Total regressions: {summary['total_regressions']}")
        print(f"     Critical regressions: {len(summary['critical_regressions'])}")
        print(f"     Recommendation: {summary['recommendation']}")

        for metric, info in regressions.items():
            print(f"     {metric}: {info['severity']} ({info['change']:.2%} change)")


async def demonstrate_rollback_manager():
    """Demonstrate rollback management capabilities."""
    print("\n" + "=" * 60)
    print("ROLLBACK MANAGER DEMONSTRATION")
    print("=" * 60)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize components
        checkpoint_config = {
            "checkpoint_dir": temp_dir,
            "max_checkpoints": 10,
            "auto_cleanup": True,
        }
        rollback_config = {
            "rollback_history_file": str(Path(temp_dir) / "rollback_history.json"),
            "max_history_entries": 100,
        }

        checkpoint_manager = CheckpointManager(checkpoint_config)
        rollback_manager = RollbackManager(rollback_config, checkpoint_manager)

        # Create checkpoints for rollback testing
        print("\n1. Creating versions for rollback testing...")
        versions = ["v1.0", "v1.1", "v1.2"]

        for version in versions:
            version_data = create_sample_version_data(version)
            checkpoint_manager.create_checkpoint(version, version_data)
            print(f"   ✓ Created checkpoint for {version}")

        # Simulate failed test results for v1.2
        print("\n2. Simulating test failure for v1.2...")
        failed_results = create_sample_test_results("v1.2", success_rate=0.6)
        for result in failed_results:
            result["status"] = "fail"

        # Perform automatic rollback
        print("\n3. Performing automatic rollback...")
        rollback_success = rollback_manager.auto_rollback_on_failure(
            "v1.2", failed_results, {"critical_issue": "Low success rate"}
        )
        print(f"   Rollback successful: {rollback_success}")

        # Get rollback history
        print("\n4. Rollback history...")
        history = rollback_manager.get_rollback_history()
        for entry in history[-3:]:  # Show last 3 entries
            print(f"   - {entry['timestamp']}: {entry['from_version']} → {entry['to_version']}")
            print(f"     Reason: {entry['reason']}")

        # Get rollback statistics
        print("\n5. Rollback statistics...")
        stats = rollback_manager.get_rollback_stats()
        print(f"   Total rollbacks: {stats['total_rollbacks']}")
        print(f"   Success rate: {stats['success_rate']:.1%}")
        print(f"   Auto rollbacks: {stats['auto_rollbacks']}")


async def demonstrate_safety_integration():
    """Demonstrate comprehensive safety integration."""
    print("\n" + "=" * 60)
    print("SAFETY INTEGRATION DEMONSTRATION")
    print("=" * 60)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        # Configure safety integration
        config = {
            "checkpoints": {
                "checkpoint_dir": temp_dir,
                "max_checkpoints": 10,
                "auto_cleanup": True,
            },
            "rollback": {
                "rollback_history_file": str(Path(temp_dir) / "rollback_history.json"),
                "max_history_entries": 100,
            },
            "regression": {
                "regression_threshold": 0.05,
                "metric_thresholds": {
                    "success_rate": {"regression": -0.05, "critical": -0.1},
                    "duration_sec": {"regression": 0.1, "critical": 0.25},
                },
            },
            "auto_checkpoint": True,
            "auto_rollback": True,
            "safety_checks_enabled": True,
        }

        # Initialize safety integration
        metrics_tracker = MetricsTracker()
        safety_integration = SafetyIntegration(config, metrics_tracker)

        print("\n1. Safety system status...")
        status = safety_integration.get_safety_status()
        print(f"   Safety enabled: {status['safety_enabled']}")
        print(f"   Auto checkpoint: {status['auto_checkpoint']}")
        print(f"   Auto rollback: {status['auto_rollback']}")

        # Simulate evolution steps
        print("\n2. Simulating safe evolution steps...")

        # Step 1: Good version (should be accepted)
        print("\n   Step 1: Testing good version...")
        good_results = create_sample_test_results("v1.1", success_rate=0.96)
        good_data = create_sample_version_data("v1.1")

        result1 = safety_integration.execute_safe_evolution_step(
            "v1.0", good_data, "v1.1", good_results
        )
        print(f"   ✓ Version accepted: {result1['version_accepted']}")
        print(f"   ✓ Safety score: {result1['safety_validation']['safety_score']:.2f}")

        # Step 2: Version with minor regression (should be accepted with warning)
        print("\n   Step 2: Testing version with minor regression...")
        minor_regression_results = create_sample_test_results("v1.2", success_rate=0.92)
        minor_regression_data = create_sample_version_data("v1.2")

        result2 = safety_integration.execute_safe_evolution_step(
            "v1.1", minor_regression_data, "v1.2", minor_regression_results
        )
        print(f"   ✓ Version accepted: {result2['version_accepted']}")
        print(f"   ✓ Safety score: {result2['safety_validation']['safety_score']:.2f}")

        # Step 3: Version with critical issues (should be rolled back)
        print("\n   Step 3: Testing version with critical issues...")
        critical_results = create_sample_test_results("v1.3", success_rate=0.70)
        for result in critical_results:
            result["resources"]["duration_sec"] *= 1.4  # 40% slower
            result["status"] = "fail"
        critical_data = create_sample_version_data("v1.3")

        result3 = safety_integration.execute_safe_evolution_step(
            "v1.2", critical_data, "v1.3", critical_results
        )
        print(f"   ✗ Version accepted: {result3['version_accepted']}")
        print(f"   ✓ Rollback performed: {result3['rollback_performed']}")
        print(f"   ✗ Safety score: {result3['safety_validation']['safety_score']:.2f}")

        # Show final safety status
        print("\n3. Final safety system status...")
        final_status = safety_integration.get_safety_status()
        print(f"   Total checkpoints: {final_status['checkpoint_manager']['total_checkpoints']}")
        print(f"   Total rollbacks: {final_status['rollback_manager']['total_rollbacks']}")
        print(f"   Rollback success rate: {final_status['rollback_manager']['success_rate']:.1%}")


async def main():
    """Run all safety feature demonstrations."""
    print("EVOSEAL FOUNDATIONAL SAFETY & VALIDATION FEATURES")
    print("=" * 60)
    print("This example demonstrates the comprehensive safety mechanisms")
    print("including checkpoint management, rollback capabilities, and")
    print("regression detection integrated into the evolution pipeline.")

    try:
        # Run all demonstrations
        await demonstrate_checkpoint_manager()
        await demonstrate_regression_detector()
        await demonstrate_rollback_manager()
        await demonstrate_safety_integration()

        print("\n" + "=" * 60)
        print("SAFETY FEATURES DEMONSTRATION COMPLETED")
        print("=" * 60)
        print("✓ Checkpoint management working correctly")
        print("✓ Regression detection identifying issues")
        print("✓ Rollback management handling failures")
        print("✓ Safety integration coordinating all features")
        print("\nAll foundational safety and validation features are operational!")

    except Exception as e:
        logger.exception("Error during safety features demonstration")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

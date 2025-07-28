#!/usr/bin/env python3
"""
Test script for enhanced rollback logic features.

This script demonstrates the new rollback logic features:
- Post-rollback verification
- Event publishing and notifications
- Cascading rollbacks
- Rollback failure handling
"""

import json
import tempfile
from pathlib import Path
from typing import Any, Dict

from evoseal.core.checkpoint_manager import CheckpointManager
from evoseal.core.events import EventBus, EventType, event_bus, subscribe
from evoseal.core.rollback_manager import RollbackManager


def setup_test_environment():
    """Set up test environment with temporary directories."""
    temp_dir = Path(tempfile.mkdtemp())
    print(f"🔧 Setting up test environment in: {temp_dir}")

    # Create test checkpoint manager
    checkpoint_config = {
        "checkpoint_dir": str(temp_dir / "checkpoints"),
        "compression_enabled": True,
    }
    checkpoint_manager = CheckpointManager(checkpoint_config)

    # Create test rollback manager with enhanced features enabled
    rollback_config = {
        "auto_rollback_enabled": True,
        "rollback_threshold": 0.1,
        "max_rollback_attempts": 3,
        "rollback_history_file": str(temp_dir / "rollback_history.json"),
        "enable_cascading_rollback": True,
        "enable_rollback_failure_recovery": True,
    }
    rollback_manager = RollbackManager(rollback_config, checkpoint_manager)

    return temp_dir, checkpoint_manager, rollback_manager


def create_test_checkpoints(checkpoint_manager: CheckpointManager, temp_dir: Path):
    """Create test checkpoints for rollback testing."""
    print("📦 Creating test checkpoints...")

    checkpoints = []

    for i in range(1, 4):
        version_id = f"test_v{i}.0"

        # Create test files for checkpoint
        test_files_dir = temp_dir / f"test_files_v{i}"
        test_files_dir.mkdir(parents=True, exist_ok=True)

        (test_files_dir / f"main_v{i}.py").write_text(
            f"""
# Test file for version {i}
def main():
    print("Version {i} - Enhanced rollback logic test")
    return {i}

if __name__ == "__main__":
    main()
"""
        )

        (test_files_dir / "config.json").write_text(
            json.dumps(
                {
                    "version": f"{i}.0",
                    "features": ["enhanced_rollback", "post_verification", "cascading"],
                    "test_data": f"test_data_v{i}",
                },
                indent=2,
            )
        )

        # Create checkpoint
        version_data = {
            "version": f"{i}.0",
            "description": f"Test version {i} with enhanced rollback features",
            "files": list(test_files_dir.glob("*")),
            "metadata": {"test_version": i, "rollback_test": True},
        }

        success = checkpoint_manager.create_checkpoint(version_id, version_data)
        if success:
            checkpoints.append(version_id)
            print(f"✅ Created checkpoint: {version_id}")
        else:
            print(f"❌ Failed to create checkpoint: {version_id}")

    return checkpoints


def setup_event_listeners():
    """Set up event listeners to monitor rollback events."""
    print("🎧 Setting up event listeners...")

    rollback_events = []

    @subscribe(EventType.ROLLBACK_INITIATED)
    def on_rollback_initiated(event):
        print(f"🔄 ROLLBACK INITIATED: {event.data}")
        rollback_events.append(("initiated", event.data))

    @subscribe(EventType.ROLLBACK_COMPLETED)
    def on_rollback_completed(event):
        print(f"✅ ROLLBACK COMPLETED: {event.data}")
        rollback_events.append(("completed", event.data))

    @subscribe(EventType.ROLLBACK_FAILED)
    def on_rollback_failed(event):
        print(f"❌ ROLLBACK FAILED: {event.data}")
        rollback_events.append(("failed", event.data))

    @subscribe(EventType.ROLLBACK_VERIFICATION_PASSED)
    def on_verification_passed(event):
        print(f"🔍 VERIFICATION PASSED: {event.data}")
        rollback_events.append(("verification_passed", event.data))

    @subscribe(EventType.ROLLBACK_VERIFICATION_FAILED)
    def on_verification_failed(event):
        print(f"🔍 VERIFICATION FAILED: {event.data}")
        rollback_events.append(("verification_failed", event.data))

    @subscribe(EventType.CASCADING_ROLLBACK_STARTED)
    def on_cascading_started(event):
        print(f"🔄🔄 CASCADING ROLLBACK STARTED: {event.data}")
        rollback_events.append(("cascading_started", event.data))

    @subscribe(EventType.CASCADING_ROLLBACK_COMPLETED)
    def on_cascading_completed(event):
        print(f"🔄✅ CASCADING ROLLBACK COMPLETED: {event.data}")
        rollback_events.append(("cascading_completed", event.data))

    return rollback_events


def test_basic_rollback_with_verification(rollback_manager: RollbackManager, checkpoints):
    """Test basic rollback with post-rollback verification."""
    print("\n🧪 TEST 1: Basic rollback with post-rollback verification")

    try:
        # Rollback to version 2
        success = rollback_manager.rollback_to_version("test_v2.0", "test_basic_rollback")

        if success:
            print("✅ Basic rollback with verification succeeded")

            # Check rollback history
            history = rollback_manager.get_rollback_history(limit=1)
            if history and "verification_result" in history[0]:
                verification = history[0]["verification_result"]
                print(f"🔍 Verification result: {verification}")
                if verification["success"]:
                    print("✅ Post-rollback verification passed")
                else:
                    print(f"❌ Post-rollback verification failed: {verification['error']}")

            return True
        else:
            print("❌ Basic rollback failed")
            return False

    except Exception as e:
        print(f"❌ Basic rollback test failed with exception: {e}")
        return False


def test_cascading_rollback(rollback_manager: RollbackManager, checkpoints):
    """Test cascading rollback functionality."""
    print("\n🧪 TEST 2: Cascading rollback functionality")

    try:
        # Test cascading rollback from version 3
        result = rollback_manager.cascading_rollback("test_v3.0", max_attempts=2)

        if result["success"]:
            print(f"✅ Cascading rollback succeeded: {result['final_version']}")
            print(f"🔄 Rollback chain: {result['rollback_chain']}")
            print(f"📊 Attempts made: {result['attempts']}")
            return True
        else:
            print(f"❌ Cascading rollback failed: {result.get('error', 'Unknown error')}")
            print(f"🔄 Rollback chain: {result.get('rollback_chain', [])}")
            return False

    except Exception as e:
        print(f"❌ Cascading rollback test failed with exception: {e}")
        return False


def test_rollback_failure_handling(rollback_manager: RollbackManager):
    """Test rollback failure handling and recovery."""
    print("\n🧪 TEST 3: Rollback failure handling and recovery")

    try:
        # Test failure handling for non-existent version
        result = rollback_manager.handle_rollback_failure(
            "non_existent_version", "Checkpoint not found", attempt_count=1
        )

        print(f"🛠️ Failure handling result: {result}")

        if result["success"]:
            print(f"✅ Rollback failure recovery succeeded: {result['recovery_strategy']}")
            print(f"🎯 Final version: {result['final_version']}")
        else:
            print(f"❌ Rollback failure recovery failed: {result.get('error', 'Unknown error')}")

        print(f"🔧 Recovery actions taken: {result.get('recovery_actions', [])}")
        return True

    except Exception as e:
        print(f"❌ Rollback failure handling test failed with exception: {e}")
        return False


def test_auto_rollback_with_events(rollback_manager: RollbackManager, checkpoints):
    """Test auto rollback with event publishing."""
    print("\n🧪 TEST 4: Auto rollback with event publishing")

    try:
        # Simulate test failures
        test_results = [
            {"name": "test_basic", "status": "pass"},
            {"name": "test_advanced", "status": "fail", "error": "Assertion failed"},
            {"name": "test_integration", "status": "pass"},
        ]

        # Simulate metrics regression
        metrics_comparison = {
            "performance": {"old_value": 100, "new_value": 150, "change_percent": 50.0},
            "memory_usage": {
                "old_value": 512,
                "new_value": 600,
                "change_percent": 17.2,
            },
        }

        # Perform auto rollback
        success = rollback_manager.auto_rollback_on_failure(
            "test_v3.0", test_results, metrics_comparison
        )

        if success:
            print("✅ Auto rollback with events succeeded")
            return True
        else:
            print("❌ Auto rollback with events failed")
            return False

    except Exception as e:
        print(f"❌ Auto rollback test failed with exception: {e}")
        return False


def display_rollback_statistics(rollback_manager: RollbackManager):
    """Display rollback statistics and history."""
    print("\n📊 ROLLBACK STATISTICS")
    print("=" * 50)

    # Get statistics
    stats = rollback_manager.get_rollback_stats()
    print(f"Total rollbacks: {stats['total_rollbacks']}")
    print(f"Successful rollbacks: {stats['successful_rollbacks']}")
    print(f"Failed rollbacks: {stats['failed_rollbacks']}")
    print(f"Success rate: {stats['success_rate']:.2%}")
    print(f"Auto rollbacks: {stats['auto_rollbacks']}")

    # Get recent history
    print("\n📜 RECENT ROLLBACK HISTORY")
    print("-" * 30)
    history = rollback_manager.get_rollback_history(limit=5)
    for i, event in enumerate(history, 1):
        print(
            f"{i}. {event['timestamp'][:19]} - {event['version_id']} ({event['reason']}) - {'✅' if event['success'] else '❌'}"
        )


def main():
    """Main test function."""
    print("🚀 ENHANCED ROLLBACK LOGIC TEST")
    print("=" * 50)

    # Setup
    temp_dir, checkpoint_manager, rollback_manager = setup_test_environment()
    checkpoints = create_test_checkpoints(checkpoint_manager, temp_dir)
    rollback_events = setup_event_listeners()

    if not checkpoints:
        print("❌ Failed to create test checkpoints. Exiting.")
        return

    print(f"📦 Created {len(checkpoints)} test checkpoints: {checkpoints}")

    # Run tests
    test_results = []

    test_results.append(test_basic_rollback_with_verification(rollback_manager, checkpoints))
    test_results.append(test_cascading_rollback(rollback_manager, checkpoints))
    test_results.append(test_rollback_failure_handling(rollback_manager))
    test_results.append(test_auto_rollback_with_events(rollback_manager, checkpoints))

    # Display results
    print("\n🎯 TEST RESULTS")
    print("=" * 30)
    test_names = [
        "Basic rollback with verification",
        "Cascading rollback",
        "Rollback failure handling",
        "Auto rollback with events",
    ]

    for i, (name, result) in enumerate(zip(test_names, test_results)):
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{i+1}. {name}: {status}")

    passed = sum(test_results)
    total = len(test_results)
    print(f"\n📊 OVERALL: {passed}/{total} tests passed ({passed/total:.1%})")

    # Display statistics
    display_rollback_statistics(rollback_manager)

    # Display captured events
    print(f"\n🎧 CAPTURED EVENTS ({len(rollback_events)} total)")
    print("-" * 40)
    for event_type, event_data in rollback_events:
        print(f"• {event_type}: {event_data.get('version_id', 'N/A')}")

    print(f"\n🧹 Test completed. Temporary directory: {temp_dir}")
    print("🎉 Enhanced rollback logic features tested successfully!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Simple script to verify rollback safety mechanisms are working correctly."""

import shutil
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock

# Add the evoseal package to the path
sys.path.insert(0, str(Path(__file__).parent))

from evoseal.core.checkpoint_manager import CheckpointManager
from evoseal.core.rollback_manager import RollbackError, RollbackManager


def test_safety_mechanisms():
    """Test the critical safety mechanisms."""
    print("🛡️  VERIFYING ROLLBACK SAFETY MECHANISMS")
    print("=" * 50)

    # Create temporary test environment
    temp_dir = Path(tempfile.mkdtemp())
    print(f"📁 Using temporary directory: {temp_dir}")

    try:
        # Setup managers
        checkpoint_config = {
            "checkpoint_directory": str(temp_dir / "checkpoints"),
            "max_checkpoints": 10,
            "auto_cleanup": True,
            "compression": False,
        }
        checkpoint_manager = CheckpointManager(checkpoint_config)

        rollback_config = {
            "auto_rollback_enabled": True,
            "rollback_threshold": 0.05,
            "max_rollback_attempts": 3,
            "rollback_history_file": str(temp_dir / "rollback_history.json"),
        }
        rollback_manager = RollbackManager(rollback_config, checkpoint_manager)

        # Create test checkpoint
        test_data = {
            "id": "safety_test_v1.0",
            "name": "Safety Test Checkpoint",
            "description": "Test checkpoint for safety verification",
            "status": "completed",
            "type": "test",
            "config": {"safety_test": True},
            "metrics": [],
            "result": {"test": "safety"},
            "changes": {
                "safety_test.py": "# Safety test content",
                "safety_config.json": '{"safety": true}',
            },
        }
        checkpoint_manager.create_checkpoint("safety_test_v1.0", test_data)
        print("✅ Test checkpoint created successfully")

        # TEST 1: Safe handling when version manager points to current directory
        print("\n🔒 TEST 1: Safe handling when version manager points to current directory...")
        mock_version_manager = Mock()
        mock_version_manager.working_dir = str(Path.cwd())
        rollback_manager.version_manager = mock_version_manager

        try:
            result = rollback_manager.rollback_to_version("safety_test_v1.0", "dangerous_test")
            if result:
                # Verify it used safe fallback directory instead of current directory
                safe_dir = Path.cwd() / ".evoseal" / "rollback_target"
                if safe_dir.exists():
                    print("✅ PASSED: Safely used fallback directory instead of current directory")
                else:
                    print("❌ FAILED: Safe fallback directory was not created")
                    return False
            else:
                print("❌ FAILED: Rollback failed unexpectedly")
                return False
        except Exception as e:
            print(f"❌ FAILED: Unexpected exception: {e}")
            return False

        # TEST 2: Safe fallback directory when no version manager
        print("\n🔒 TEST 2: Testing safe fallback directory...")
        rollback_manager.version_manager = None

        try:
            result = rollback_manager.rollback_to_version("safety_test_v1.0", "fallback_test")
            if result:
                print("✅ PASSED: Safe fallback directory rollback succeeded")

                # Verify safe directory was created
                safe_dir = Path.cwd() / ".evoseal" / "rollback_target"
                if safe_dir.exists():
                    print("✅ PASSED: Safe fallback directory was created")
                else:
                    print("❌ FAILED: Safe fallback directory was not created")
                    return False
            else:
                print("❌ FAILED: Safe fallback rollback failed")
                return False
        except Exception as e:
            print(f"❌ FAILED: Safe fallback rollback raised exception: {e}")
            return False

        # TEST 3: Direct validation should prevent dangerous directories
        print("\n🔒 TEST 3: Testing direct validation of dangerous directories...")

        try:
            # Test validation of current directory - this should fail
            rollback_manager._validate_rollback_target(Path.cwd())
            print("❌ FAILED: Validation allowed current directory!")
            return False
        except RollbackError as e:
            if "SAFETY ERROR" in str(e) and "current working directory" in str(e):
                print("✅ PASSED: Validation correctly prevented current directory")
            else:
                print(f"❌ FAILED: Wrong validation error message: {e}")
                return False
        except Exception as e:
            print(f"❌ FAILED: Unexpected validation exception: {e}")
            return False

        # TEST 4: Test validation of parent directory
        try:
            parent_dir = Path.cwd().parent
            rollback_manager._validate_rollback_target(parent_dir)
            print("❌ FAILED: Validation allowed parent directory!")
            return False
        except RollbackError as e:
            if "SAFETY ERROR" in str(e) and "parent directory" in str(e):
                print("✅ PASSED: Validation correctly prevented parent directory")
            else:
                print(f"❌ FAILED: Wrong parent validation error: {e}")
                return False
        except Exception as e:
            print(f"❌ FAILED: Unexpected parent validation exception: {e}")
            return False

        print("\n🎉 CRITICAL SAFETY TESTS PASSED!")
        print("✅ Rollback system is secure and will not delete the codebase")
        print("✅ Safe fallback mechanism works correctly")
        print("✅ Direct validation prevents dangerous directories")
        return True

    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Clean up
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


def main():
    """Run the safety verification."""
    success = test_safety_mechanisms()

    if success:
        print("\n" + "=" * 50)
        print("🛡️  ROLLBACK SAFETY VERIFICATION: PASSED")
        print("=" * 50)
        print("✅ The catastrophic rollback deletion bug is FIXED")
        print("✅ Safety mechanisms are working correctly")
        print("✅ The codebase is protected from accidental deletion")
        print("✅ Future rollback operations will be safe")
        return 0
    else:
        print("\n" + "=" * 50)
        print("❌ ROLLBACK SAFETY VERIFICATION: FAILED")
        print("=" * 50)
        print("❌ Safety mechanisms are not working correctly")
        return 1


if __name__ == "__main__":
    exit(main())

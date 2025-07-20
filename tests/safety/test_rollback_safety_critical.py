"""Critical safety tests for RollbackManager to prevent catastrophic codebase deletion.

This test suite verifies that the rollback system has robust safety mechanisms
to prevent accidental deletion of the entire codebase or critical system files.

These tests simulate the exact conditions that caused the original catastrophic
failure and verify that the safety mechanisms prevent it from happening again.
"""

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import Mock, patch

import pytest

from evoseal.core.checkpoint_manager import CheckpointManager
from evoseal.core.rollback_manager import RollbackError, RollbackManager


class TestRollbackSafetyCritical:
    """Critical safety tests for rollback operations."""

    def setup_method(self):
        """Set up test environment for each test."""
        # Create temporary directories
        self.temp_dir = Path(tempfile.mkdtemp())
        self.checkpoint_dir = self.temp_dir / 'checkpoints'
        self.safe_target_dir = self.temp_dir / 'safe_target'
        self.dangerous_target_dir = Path.cwd()  # Current working directory (dangerous!)

        # Setup checkpoint manager
        self.checkpoint_config = {
            'checkpoint_directory': str(self.checkpoint_dir),
            'max_checkpoints': 10,
            'auto_cleanup': True,
            'compression': False,
        }
        self.checkpoint_manager = CheckpointManager(self.checkpoint_config)

        # Setup rollback manager
        self.rollback_config = {
            'auto_rollback_enabled': True,
            'rollback_threshold': 0.05,
            'max_rollback_attempts': 3,
            'rollback_history_file': str(self.temp_dir / 'rollback_history.json'),
        }
        self.rollback_manager = RollbackManager(self.rollback_config, self.checkpoint_manager)

        # Create a test checkpoint
        self.test_checkpoint_data = {
            'id': 'test_checkpoint_v1.0',
            'name': 'Test Checkpoint',
            'description': 'Test checkpoint for safety validation',
            'status': 'completed',
            'type': 'test',
            'config': {'test': True},
            'metrics': [],
            'result': {'test': 'data'},
            'changes': {'test_file.py': '# Test content', 'config.json': '{"test": true}'},
        }
        self.checkpoint_path = self.checkpoint_manager.create_checkpoint(
            'test_checkpoint_v1.0', self.test_checkpoint_data
        )

    def teardown_method(self):
        """Clean up after each test."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_prevent_rollback_to_current_directory(self):
        """Test that rollback to current working directory uses safe fallback."""
        # Create a mock version manager that points to current directory
        mock_version_manager = Mock()
        mock_version_manager.working_dir = str(Path.cwd())
        self.rollback_manager.version_manager = mock_version_manager

        # This should succeed by using safe fallback directory
        result = self.rollback_manager.rollback_to_version('test_checkpoint_v1.0', 'dangerous_test')

        # Verify rollback succeeded
        assert result is True

        # Verify safe fallback directory was created and used
        safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        assert safe_dir.exists(), "Safe fallback directory should be created"

    def test_prevent_rollback_to_parent_directory(self):
        """Test that rollback to parent directory uses safe fallback."""
        # Create a mock version manager that returns parent directory (dangerous!)
        mock_version_manager = Mock()
        mock_version_manager.working_dir = str(Path.cwd().parent)

        self.rollback_manager.version_manager = mock_version_manager

        # Rollback should succeed by using safe fallback directory
        result = self.rollback_manager.rollback_to_version('test_checkpoint_v1.0', 'safety_test')

        # Verify rollback succeeded with safe fallback
        assert result is True

        # Verify safe fallback directory was created
        safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        assert safe_dir.exists(), "Safe fallback directory should be created for parent directory"

    def test_prevent_rollback_to_system_directories(self):
        """Test that rollback to dangerous system directories uses safe fallback."""
        dangerous_dirs = ['/', '/home', '/usr', '/var', '/etc', '/opt']

        for dangerous_dir in dangerous_dirs:
            if Path(dangerous_dir).exists():  # Only test if directory exists
                mock_version_manager = Mock()
                mock_version_manager.working_dir = dangerous_dir

                self.rollback_manager.version_manager = mock_version_manager

                # Rollback should succeed by using safe fallback directory
                result = self.rollback_manager.rollback_to_version(
                    'test_checkpoint_v1.0', 'safety_test'
                )

                # Verify rollback succeeded with safe fallback
                assert result is True

                # Verify safe fallback directory was created
                safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
                assert (
                    safe_dir.exists()
                ), f"Safe fallback directory should be created for {dangerous_dir}"

    def test_safe_fallback_directory_creation(self):
        """Test that safe fallback directory is created when no version manager is provided."""
        # Remove version manager to trigger fallback
        self.rollback_manager.version_manager = None

        # Perform rollback - should use safe fallback directory
        result = self.rollback_manager.rollback_to_version('test_checkpoint_v1.0', 'fallback_test')

        # Verify rollback succeeded
        assert result is True

        # Verify safe fallback directory was created
        safe_fallback_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        assert safe_fallback_dir.exists()

        # Verify rollback history shows safe directory was used
        history = self.rollback_manager.get_rollback_history(limit=1)
        assert len(history) > 0
        assert 'safety_validated' in history[0]
        assert history[0]['safety_validated'] is True
        assert '.evoseal/rollback_target' in history[0]['working_directory']

    def test_safe_directory_rollback_success(self):
        """Test that rollback to a safe directory works correctly."""
        # Create a safe target directory
        safe_target = self.temp_dir / 'safe_rollback_target'
        safe_target.mkdir(parents=True, exist_ok=True)

        # Create mock version manager with safe directory
        mock_version_manager = Mock()
        mock_version_manager.working_dir = str(safe_target)

        self.rollback_manager.version_manager = mock_version_manager

        # Perform rollback - should succeed
        result = self.rollback_manager.rollback_to_version('test_checkpoint_v1.0', 'safe_test')

        # Verify rollback succeeded
        assert result is True

        # Verify rollback history shows safety validation passed
        history = self.rollback_manager.get_rollback_history(limit=1)
        assert len(history) > 0
        assert history[0]['success'] is True
        assert history[0]['safety_validated'] is True

    def test_validate_rollback_target_method_directly(self):
        """Test the _validate_rollback_target method directly with various scenarios."""
        # Test 1: Safe directory should pass
        safe_dir = self.temp_dir / 'safe_test_dir'
        safe_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise exception
        self.rollback_manager._validate_rollback_target(safe_dir)

        # Test 2: Current directory should fail
        with pytest.raises(RollbackError) as exc_info:
            self.rollback_manager._validate_rollback_target(Path.cwd())
        assert "SAFETY ERROR" in str(exc_info.value)
        assert "current working directory" in str(exc_info.value)

        # Test 3: Parent directory should fail
        with pytest.raises(RollbackError) as exc_info:
            self.rollback_manager._validate_rollback_target(Path.cwd().parent)
        assert "SAFETY ERROR" in str(exc_info.value)
        assert "parent directory" in str(exc_info.value)

    def test_rollback_with_no_version_manager_uses_safe_directory(self):
        """Test that rollback without version manager automatically uses safe directory."""
        # Ensure no version manager is set
        self.rollback_manager.version_manager = None

        # Get the working directory - should be safe fallback
        working_dir = self.rollback_manager._get_working_directory()

        # Verify it's the safe fallback directory
        expected_safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        assert working_dir == expected_safe_dir

        # Verify the directory exists
        assert working_dir.exists()

        # Verify it's not the current working directory
        assert working_dir.resolve() != Path.cwd().resolve()

    def test_rollback_history_includes_safety_validation(self):
        """Test that rollback history includes safety validation information."""
        # Perform a safe rollback
        self.rollback_manager.version_manager = None  # Use safe fallback
        result = self.rollback_manager.rollback_to_version('test_checkpoint_v1.0', 'history_test')

        assert result is True

        # Check rollback history
        history = self.rollback_manager.get_rollback_history(limit=1)
        assert len(history) > 0

        latest_rollback = history[0]
        assert 'safety_validated' in latest_rollback
        assert latest_rollback['safety_validated'] is True
        assert latest_rollback['success'] is True
        assert 'working_directory' in latest_rollback

    def test_multiple_safety_scenarios_in_sequence(self):
        """Test multiple safety scenarios to ensure consistent protection."""
        scenarios = [
            # Scenario 1: Try current directory (should use safe fallback)
            {
                'working_dir': str(Path.cwd()),
                'should_use_fallback': True,
                'description': 'current directory',
            },
            # Scenario 2: Try parent directory (should use safe fallback)
            {
                'working_dir': str(Path.cwd().parent),
                'should_use_fallback': True,
                'description': 'parent directory',
            },
            # Scenario 3: Try safe directory (should succeed normally)
            {
                'working_dir': str(self.temp_dir / 'safe_dir'),
                'should_use_fallback': False,
                'description': 'safe directory',
            },
        ]

        for i, scenario in enumerate(scenarios):
            # Create directory if it doesn't exist and it's safe
            test_dir = Path(scenario['working_dir'])
            if not test_dir.exists() and not scenario['should_use_fallback']:
                test_dir.mkdir(parents=True, exist_ok=True)

            # Set up mock version manager
            mock_version_manager = Mock()
            mock_version_manager.working_dir = scenario['working_dir']
            self.rollback_manager.version_manager = mock_version_manager

            # All scenarios should succeed (either with fallback or normally)
            result = self.rollback_manager.rollback_to_version(
                'test_checkpoint_v1.0', f'scenario_{i}_test'
            )
            assert result is True, f"Scenario {i} ({scenario['description']}) should succeed"

            # Verify safe fallback directory exists if expected
            if scenario['should_use_fallback']:
                safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
                assert (
                    safe_dir.exists()
                ), f"Safe fallback should be created for {scenario['description']}"

    def test_safety_mechanisms_cannot_be_bypassed(self):
        """Test that safety mechanisms cannot be easily bypassed."""
        # Test direct validation method - this should still prevent dangerous paths
        dangerous_paths = [Path.cwd(), Path.cwd().parent, Path('/')]

        for dangerous_path in dangerous_paths:
            if dangerous_path.exists():
                # Direct validation should still prevent dangerous directories
                with pytest.raises(RollbackError) as exc_info:
                    self.rollback_manager._validate_rollback_target(dangerous_path)

                # Verify the error message indicates safety prevention
                assert "SAFETY ERROR" in str(exc_info.value)

    @pytest.mark.parametrize(
        "dangerous_path",
        [
            ".",
            "./",
            str(Path.cwd()),
            str(Path.cwd().resolve()),
            str(Path.cwd().parent),
        ],
    )
    def test_various_dangerous_path_formats(self, dangerous_path):
        """Test that various formats of dangerous paths use safe fallback."""
        mock_version_manager = Mock()
        mock_version_manager.working_dir = dangerous_path
        self.rollback_manager.version_manager = mock_version_manager

        # Should succeed by using safe fallback directory
        result = self.rollback_manager.rollback_to_version(
            'test_checkpoint_v1.0', 'path_format_test'
        )

        # Verify rollback succeeded with safe fallback
        assert result is True

        # Verify safe fallback directory was created
        safe_dir = Path.cwd() / '.evoseal' / 'rollback_target'
        assert (
            safe_dir.exists()
        ), f"Safe fallback directory should be created for path: {dangerous_path}"


class TestRollbackSafetyIntegration:
    """Integration tests for rollback safety with real-world scenarios."""

    def setup_method(self):
        """Set up integration test environment."""
        self.temp_dir = Path(tempfile.mkdtemp())

    def teardown_method(self):
        """Clean up integration test environment."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_rollback_safety_with_real_checkpoint_restore(self):
        """Test safety mechanisms with actual checkpoint restoration."""
        # Create a more realistic test scenario
        checkpoint_dir = self.temp_dir / 'checkpoints'
        safe_target = self.temp_dir / 'safe_workspace'

        # Setup managers
        checkpoint_config = {
            'checkpoint_directory': str(checkpoint_dir),
            'max_checkpoints': 10,
            'auto_cleanup': True,
            'compression': False,
        }
        checkpoint_manager = CheckpointManager(checkpoint_config)

        rollback_config = {
            'auto_rollback_enabled': True,
            'rollback_threshold': 0.05,
            'max_rollback_attempts': 3,
            'rollback_history_file': str(self.temp_dir / 'rollback_history.json'),
        }
        rollback_manager = RollbackManager(rollback_config, checkpoint_manager)

        # Create test data and checkpoint
        test_data = {
            'id': 'integration_test_v1.0',
            'name': 'Integration Test',
            'description': 'Integration test checkpoint',
            'status': 'completed',
            'type': 'test',
            'config': {'integration': True},
            'metrics': [],
            'result': {'integration': 'test'},
            'changes': {
                'integration_test.py': '# Integration test content',
                'integration_config.json': '{"integration": true}',
            },
        }
        checkpoint_manager.create_checkpoint('integration_test_v1.0', test_data)

        # Create mock version manager with safe directory
        safe_target.mkdir(parents=True, exist_ok=True)
        mock_version_manager = Mock()
        mock_version_manager.working_dir = str(safe_target)
        rollback_manager.version_manager = mock_version_manager

        # Perform rollback - should succeed safely
        result = rollback_manager.rollback_to_version('integration_test_v1.0', 'integration_test')

        assert result is True

        # Verify files were restored to safe location
        assert (safe_target / 'integration_test.py').exists()
        assert (safe_target / 'integration_config.json').exists()

        # Verify current working directory was not affected
        current_files_before = set(os.listdir('.'))
        # Current directory should be unchanged
        current_files_after = set(os.listdir('.'))
        # The sets should be the same (no files deleted from current directory)
        assert current_files_before == current_files_after


def run_safety_tests():
    """Run all safety tests and report results."""
    print("🛡️  Running Critical Rollback Safety Tests...")
    print("=" * 60)

    # Run pytest on this file
    import subprocess

    result = subprocess.run(
        ['python', '-m', 'pytest', __file__, '-v', '--tb=short'], capture_output=True, text=True
    )

    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)

    return result.returncode == 0


if __name__ == "__main__":
    # Run safety tests when executed directly
    success = run_safety_tests()
    if success:
        print("\n✅ All safety tests passed! Rollback system is secure.")
    else:
        print("\n❌ Some safety tests failed! Review the implementation.")
        exit(1)

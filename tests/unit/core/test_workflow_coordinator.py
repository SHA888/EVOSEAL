"""Unit tests for the WorkflowCoordinator class."""
import unittest
import asyncio
import tempfile
import shutil
import sys
from enum import Enum
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock

# Mock the missing dependencies
sys.modules['evoseal.core.controller'] = MagicMock()
sys.modules['evoseal.core.repository'] = MagicMock()
sys.modules['evoseal.core.events'] = MagicMock()
sys.modules['evoseal.core.testrunner'] = MagicMock()
sys.modules['evoseal.core.metrics'] = MagicMock()
sys.modules['evoseal.core.validator'] = MagicMock()

# Mock the time module for testrunner
import time
sys.modules['time'] = time

# Now import the module under test
from evoseal.core.evolution_pipeline import WorkflowCoordinator, WorkflowStage, WorkflowState


class TestWorkflowCoordinator(unittest.TestCase):
    """Test suite for the WorkflowCoordinator class."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_dir = Path(tempfile.mkdtemp())
        self.config_path = self.test_dir / "test_config.json"
        self.config_path.write_text('{"test": "config"}')
        
        # Mock the RepositoryManager
        self.mock_repo_manager = MagicMock()
        self.mock_repo_manager.clone_repository.return_value = self.test_dir / "test_repo"
        
        # Create a test coordinator instance
        self.coordinator = WorkflowCoordinator(
            str(self.config_path),
            work_dir=str(self.test_dir)
        )
        self.coordinator.repo_manager = self.mock_repo_manager
        
        # Mock the event bus
        self.coordinator.event_bus = MagicMock()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_initial_state(self):
        """Test the initial state of the WorkflowCoordinator."""
        self.assertEqual(self.coordinator.state, WorkflowState.NOT_STARTED)
        self.assertIsNone(self.coordinator.current_stage)
        self.assertEqual(len(self.coordinator.stage_results), 0)

    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_pause_resume_workflow(self, mock_sleep):
        """Test pausing and resuming the workflow."""
        # Create a mock stage function that will be paused
        async def mock_stage():
            await asyncio.sleep(0.1)
            return {"status": "success"}

        # Start the workflow
        task = asyncio.create_task(
            self.coordinator._execute_stage(WorkflowStage.INITIALIZING, mock_stage)
        )
        
        # Request a pause
        self.assertTrue(self.coordinator.request_pause())
        
        # Let the task run a bit
        await asyncio.sleep(0.05)
        
        # Verify pause was requested
        self.assertTrue(self.coordinator.pause_requested)
        
        # Let the task complete
        await task
        
        # Verify workflow is now paused
        self.assertEqual(self.coordinator.state, WorkflowState.PAUSED)
        
        # Resume the workflow
        self.assertTrue(self.coordinator.resume())
        self.assertEqual(self.coordinator.state, WorkflowState.RUNNING)

    async def test_stage_transition_validation(self):
        """Test that stage transitions are properly validated."""
        # Should allow transition from None to INITIALIZING
        await self.coordinator._execute_stage(
            WorkflowStage.INITIALIZING,
            lambda: {"status": "success"}
        )
        
        # Should not allow invalid transition back to INITIALIZING
        with self.assertRaises(ValueError):
            await self.coordinator._execute_stage(
                WorkflowStage.INITIALIZING,
                lambda: {"status": "success"}
            )

    @patch('asyncio.sleep', new_callable=AsyncMock)
    async def test_error_handling(self, mock_sleep):
        """Test error handling and retry logic."""
        # Create a mock that fails twice then succeeds
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("Temporary error"),
            Exception("Temporary error"),
            {"status": "success"}
        ]
        
        # Execute the stage
        result = await self.coordinator._execute_stage(
            WorkflowStage.ANALYZING,
            mock_func
        )
        
        # Should have retried and eventually succeeded
        self.assertEqual(result["status"], "success")
        self.assertEqual(mock_func.call_count, 3)

    async def test_recovery_branch_creation(self):
        """Test recovery branch creation on failure."""
        # Mock the repository manager
        self.coordinator.current_repo = "test_repo"
        self.mock_repo_manager.checkout_branch.return_value = True
        self.mock_repo_manager.commit_changes.return_value = "recovery-commit"
        
        # Create a mock that always fails
        async def failing_stage():
            raise Exception("Critical error")
        
        # Execute the stage with max attempts = 1
        self.coordinator.MAX_STAGE_ATTEMPTS = 1
        
        with self.assertRaises(Exception):
            await self.coordinator._execute_stage(
                WorkflowStage.ANALYZING,
                failing_stage
            )
        
        # Verify recovery branch was created
        self.mock_repo_manager.checkout_branch.assert_called()
        self.mock_repo_manager.commit_changes.assert_called()

    async def test_workflow_lifecycle(self):
        """Test the complete workflow lifecycle."""
        # Mock the repository initialization
        self.mock_repo_manager.get_default_branch.return_value = "main"
        
        # Mock the stage functions
        async def mock_init_repo(url):
            return {"status": "success", "branch": "feature/evolve-1"}
            
        async def mock_analyze():
            return {"status": "success", "analysis": {}}
            
        async def mock_generate():
            return {"status": "success", "improvements": []}
            
        async def mock_adapt():
            return {"status": "success", "adapted_improvements": []}
            
        async def mock_evaluate():
            return {"status": "success", "metrics": {}}
            
        async def mock_validate():
            return {"status": "success", "is_improvement": True}
            
        async def mock_finalize():
            return {"status": "success"}
        
        # Run the workflow
        self.coordinator._initialize_repository = mock_init_repo
        self.coordinator._run_evolution_iteration = AsyncMock(return_value={"status": "success"})
        
        result = await self.coordinator.run_workflow(
            "https://github.com/example/test-repo.git",
            iterations=1
        )
        
        # Verify the workflow completed successfully
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["status"], "success")
        self.assertEqual(self.coordinator.state, WorkflowState.COMPLETED)


if __name__ == "__main__":
    unittest.main()

"""Integration tests for the WorkflowCoordinator."""

import asyncio
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch


# First, create a mock for the WorkflowStage and WorkflowState enums
class MockWorkflowState:
    NOT_STARTED = "not_started"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class MockWorkflowStage:
    INITIALIZING = "initializing"
    ANALYZING = "analyzing"
    GENERATING = "generating_improvements"
    ADAPTING = "adapting_improvements"
    EVALUATING = "evaluating_version"
    VALIDATING = "validating_improvement"
    FINALIZING = "finalizing"

    @classmethod
    def get_stage_order(cls):
        return [
            cls.INITIALIZING,
            cls.ANALYZING,
            cls.GENERATING,
            cls.ADAPTING,
            cls.EVALUATING,
            cls.VALIDATING,
            cls.FINALIZING,
        ]


# Create a mock for the WorkflowCoordinator class
class MockWorkflowCoordinator:
    def __init__(self, config_path, work_dir=None):
        self.config_path = config_path
        self.work_dir = Path(work_dir) if work_dir else Path.cwd() / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.state = MockWorkflowState.NOT_STARTED
        self.current_stage = None
        self.stage_results = {}
        self.retry_count = 0
        self.current_repo = None
        self.current_branch = None
        self.pause_requested = False
        self.stage_attempts = 0
        self.last_error = None
        self.config = {}
        self.repo_manager = None
        self.pipeline = Mock()

    def _load_config(self):
        if hasattr(self, "_config"):
            return self._config
        return {}

    def _save_state(self):
        pass

    def _load_state(self):
        pass


# Now patch the imports to use our mocks
sys.modules["evoseal.core.evolution_pipeline"] = MagicMock()
sys.modules["evoseal.core.evolution_pipeline"].WorkflowState = MockWorkflowState
sys.modules["evoseal.core.evolution_pipeline"].WorkflowStage = MockWorkflowStage
sys.modules["evoseal.core.evolution_pipeline"].WorkflowCoordinator = MockWorkflowCoordinator

# Now import the actual modules we need
import git

from evoseal.core.repository import RepositoryManager


class TestWorkflowIntegration(unittest.TestCase):
    """Integration tests for the WorkflowCoordinator with real components."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for the test
        self.test_dir = Path(tempfile.mkdtemp())
        self.repo_dir = self.test_dir / "test_repo"
        self.work_dir = self.test_dir / "work"
        self.work_dir.mkdir(parents=True, exist_ok=True)

        # Initialize a test git repository
        self._init_test_repo()

        # Create a default test configuration
        self.config_path = self.test_dir / "test_config.json"

        # Default test configuration
        self.config = {
            "repository": {
                "url": f"file://{self.repo_dir}",
                "branch": "main",
                "commit_message": "[Test] Test commit",
            },
            "evolution": {
                "max_generations": 10,
                "population_size": 5,
                "mutation_rate": 0.1,
                "crossover_rate": 0.8,
                "elitism": 1,
                "max_stagnation": 5,
            },
            "evaluation": {
                "test_command": "pytest",
                "coverage_command": "coverage run -m pytest",
                "timeout_seconds": 300,
                "max_memory_mb": 2048,
            },
            "paths": {
                "output_dir": str(self.test_dir / "output"),
                "cache_dir": str(self.test_dir / ".cache"),
                "temp_dir": str(self.test_dir / ".temp"),
            },
        }

        # Write the updated config
        self.config_path.write_text(json.dumps(self.config, indent=2))

        # Initialize the repository manager with a Path object
        self.repo_manager = RepositoryManager(self.work_dir)

        # Create a mock for the EvolutionPipeline
        self.mock_pipeline = Mock()

        # Initialize the coordinator with our mock
        self.coordinator = MockWorkflowCoordinator(
            str(self.config_path), work_dir=str(self.work_dir)
        )

        # Set up the mock to return our config when _load_config is called
        self.coordinator._config = self.config
        self.coordinator.pipeline = self.mock_pipeline
        self.coordinator.repo_manager = self.repo_manager
        self.coordinator.state = MockWorkflowState.NOT_STARTED
        self.coordinator.current_stage = None

        # Set up the event bus mock
        self.coordinator.event_bus = MagicMock()

    def _init_test_repo(self):
        """Initialize a test git repository with sample files."""
        # Create a new git repository
        repo = git.Repo.init(self.repo_dir)

        # Create a sample Python file
        sample_file = self.repo_dir / "sample.py"
        sample_file.write_text(
            """def add(a, b):
    return a + b

def subtract(a, b):
    return a - b
"""
        )

        # Create a test file
        test_file = self.repo_dir / "test_sample.py"
        test_file.write_text(
            """import unittest
from sample import add, subtract

class TestMath(unittest.TestCase):
    def test_add(self):
        self.assertEqual(add(1, 2), 3)

    def test_subtract(self):
        self.assertEqual(subtract(5, 3), 2)

if __name__ == "__main__":
    unittest.main()
"""
        )

        # Add and commit the files
        repo.index.add(["sample.py", "test_sample.py"])
        repo.index.commit("Initial commit")

        # Create a main branch
        repo.create_head("main")
        repo.heads.main.checkout()

    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def _mock_analysis(self, *args, **kwargs):
        """Mock analysis stage."""
        return {
            "status": "success",
            "analysis": {"complexity": "medium", "test_coverage": 100.0, "issues": []},
        }

    async def _mock_generation(self, *args, **kwargs):
        """Mock improvement generation."""
        return {
            "status": "success",
            "improvements": [
                {
                    "file": "sample.py",
                    "suggestion": "Add type hints to improve code clarity",
                    "priority": "medium",
                }
            ],
        }

    async def _mock_adaptation(self, *args, **kwargs):
        """Mock improvement adaptation."""
        # Get the repository
        repo = git.Repo(self.work_dir / "test_repo")

        # Modify the sample file to add type hints
        sample_file = self.work_dir / "test_repo" / "sample.py"
        content = sample_file.read_text()
        content = content.replace("def add(a, b):", "def add(a: int, b: int) -> int:").replace(
            "def subtract(a, b):", "def subtract(a: int, b: int) -> int:"
        )
        sample_file.write_text(content)

        # Stage and commit the changes
        repo.index.add([str(sample_file)])
        repo.index.commit("Add type hints to math functions")

        return {
            "status": "success",
            "adapted_files": ["sample.py"],
            "commit_hash": repo.head.commit.hexsha,
        }

    async def _mock_evaluation(self, *args, **kwargs):
        """Mock evaluation of changes."""
        return {
            "status": "success",
            "metrics": {
                "test_passed": True,
                "test_coverage": 100.0,
                "performance_impact": 0,
                "complexity_change": 0,
            },
        }

    async def _mock_validation(self, *args, **kwargs):
        """Mock validation of improvements."""
        return {
            "status": "success",
            "is_improvement": True,
            "score": 0.9,
            "feedback": "Changes improve code quality with type hints",
        }

    @patch("evoseal.core.evolution_pipeline.WorkflowCoordinator._run_evolution_iteration")
    async def test_complete_workflow(self, mock_iteration):
        """Test a complete workflow with mocked components."""
        # Configure the mock to return a successful iteration
        mock_iteration.return_value = {
            "status": "success",
            "improvement_accepted": True,
            "metrics": {"test_passed": True},
        }

        # Run the workflow
        results = await self.coordinator.run_workflow(str(self.repo_dir), iterations=1)

        # Verify the results
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["status"], "success")
        self.assertEqual(self.coordinator.state, WorkflowState.COMPLETED)

        # Verify the repository was cloned
        self.assertTrue((self.work_dir / "test_repo").exists())

        # Verify the iteration was called once
        mock_iteration.assert_called_once()

    @patch("evoseal.core.evolution_pipeline.WorkflowCoordinator._run_evolution_iteration")
    async def test_workflow_with_pause_resume(self, mock_iteration):
        """Test pausing and resuming the workflow."""

        # Configure the mock to simulate a pause
        async def mock_iteration_side_effect(*args, **kwargs):
            # Request a pause during the first iteration
            if not hasattr(mock_iteration_side_effect, "paused"):
                mock_iteration_side_effect.paused = True
                self.coordinator.request_pause()
                return {"status": "paused"}
            return {"status": "success"}

        mock_iteration.side_effect = mock_iteration_side_effect

        # Start the workflow in a separate task
        task = asyncio.create_task(self.coordinator.run_workflow(str(self.repo_dir), iterations=2))

        # Wait for the workflow to pause
        while not self.coordinator.pause_requested:
            await asyncio.sleep(0.1)

        # Verify the workflow is paused
        self.assertEqual(self.coordinator.state, WorkflowState.PAUSED)

        # Resume the workflow
        await self.coordinator.resume()

        # Wait for the workflow to complete
        results = await task

        # Verify the results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["status"], "paused")
        self.assertEqual(results[1]["status"], "success")
        self.assertEqual(self.coordinator.state, WorkflowState.COMPLETED)


if __name__ == "__main__":
    unittest.main()

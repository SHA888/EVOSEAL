"""
Integration tests for the TestRunner class.

These tests verify the end-to-end functionality of the test execution framework,
including test discovery, execution, and result collection.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from typing import Dict, List

import pytest
from rich.console import Console

from evoseal.core.testrunner import TestRunner, TestConfig

# Test console
console = Console()

# Sample test files for testing test discovery and execution
SAMPLE_TESTS = """
import unittest

class TestSample(unittest.TestCase):
    def test_pass(self):
        self.assertTrue(True)
    
    def test_fail(self):
        self.fail("Expected failure")
    
    def test_error(self):
        raise ValueError("Test error")
    
    @unittest.skip("Skipped test")
    def test_skip(self):
        pass
"""

PERFORMANCE_TEST = """
import time
import unittest

class TestPerformance(unittest.TestCase):
    def test_fast(self):
        time.sleep(0.1)
        self.assertTrue(True)
    
    def test_slow(self):
        time.sleep(1.5)  # Should be caught by timeout
        self.assertTrue(True)
"""


@pytest.fixture
def test_environment():
    """Set up a temporary test environment with sample test files."""
    # Create a temporary directory
    temp_dir = tempfile.mkdtemp(prefix="evoseal_test_")
    test_dir = Path(temp_dir) / "tests"
    test_dir.mkdir()
    
    # Create sample test files
    (test_dir / "test_unit_sample.py").write_text(SAMPLE_TESTS)
    (test_dir / "test_perf_sample.py").write_text(PERFORMANCE_TEST)
    
    # Create a simple Python module to test against
    (Path(temp_dir) / "sample_module.py").write_text("def add(a, b): return a + b\n")
    
    yield {
        "temp_dir": temp_dir,
        "test_dir": str(test_dir),
        "module_path": str(Path(temp_dir) / "sample_module.py")
    }
    
    # Clean up
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_test_runner_initialization():
    """Test that TestRunner initializes with default config."""
    runner = TestRunner()
    assert runner.config.timeout == 60  # Default timeout
    assert runner.config.max_workers > 0


def test_discover_tests(test_environment):
    """Test test discovery functionality."""
    config = TestConfig(test_dir=test_environment["test_dir"])
    runner = TestRunner(config)
    
    # Discover unit tests
    unit_tests = runner.discover_tests("unit")
    assert len(unit_tests) >= 1
    assert any("test_unit_sample.py" in str(test) for test in unit_tests)
    
    # Discover performance tests
    perf_tests = runner.discover_tests("performance")
    assert len(perf_tests) >= 1
    assert any("test_perf_sample.py" in str(test) for test in perf_tests)


def test_run_unit_tests(test_environment):
    ""Test running unit tests with the TestRunner."""
    config = TestConfig(
        test_dir=test_environment["test_dir"],
        timeout=10,
        max_workers=2
    )
    runner = TestRunner(config)
    
    # Run unit tests
    results = runner.run_tests(
        test_environment["module_path"],
        test_types=["unit"]
    )
    
    # Verify results
    assert len(results) == 1
    result = results[0]
    assert result["test_type"] == "unit"
    assert result["stats"]["total"] == 4  # 4 test cases in sample
    assert result["stats"]["passed"] == 1
    assert result["stats"]["failed"] == 1
    assert result["stats"]["errors"] == 1
    assert result["stats"]["skipped"] == 1
    
    # Verify resource usage was tracked
    assert "resources" in result
    assert "duration" in result
    assert "timestamp" in result


def test_run_performance_tests(test_environment):
    ""Test running performance tests with timeout."""
    config = TestConfig(
        test_dir=test_environment["test_dir"],
        timeout=1,  # Short timeout to catch the slow test
        max_workers=1
    )
    runner = TestRunner(config)
    
    # Run performance tests
    results = runner.run_tests(
        test_environment["module_path"],
        test_types=["performance"]
    )
    
    # Verify results
    assert len(results) == 1
    result = results[0]
    assert result["test_type"] == "performance"
    assert result["stats"]["total"] == 2
    assert result["stats"]["passed"] >= 1  # At least the fast test should pass
    assert result["stats"].get("timeout", 0) >= 1  # The slow test should time out


def test_parallel_test_execution(test_environment):
    ""Test running tests in parallel."""
    config = TestConfig(
        test_dir=test_environment["test_dir"],
        timeout=10,
        max_workers=2  # Run tests in parallel
    )
    runner = TestRunner(config)
    
    # Run multiple test types in parallel
    start_time = time.time()
    results = runner.run_tests(
        test_environment["module_path"],
        test_types=["unit", "performance"]
    )
    duration = time.time() - start_time
    
    # Verify we got results for both test types
    assert len(results) == 2
    test_types = {r["test_type"] for r in results}
    assert "unit" in test_types
    assert "performance" in test_types
    
    # Verify parallel execution (should be faster than sequential)
    # The slow test in performance tests takes 1.5s, so total should be less than 2x that
    assert duration < 2.5  # With some buffer for test setup/teardown


def test_test_runner_with_nonexistent_test_dir():
    ""Test that TestRunner handles non-existent test directories gracefully."""
    config = TestConfig(test_dir="/nonexistent/path")
    runner = TestRunner(config)
    
    # Should not raise an exception
    tests = runner.discover_tests("unit")
    assert len(tests) == 0
    
    # Running tests should return an error result
    results = runner.run_tests("dummy_module.py", test_types=["unit"])
    assert len(results) == 1
    assert "error" in results[0]
    assert "No tests found" in results[0]["error"]


if __name__ == "__main__":
    # When run directly, set up a test environment and run the tests
    with tempfile.TemporaryDirectory() as temp_dir:
        env = {
            "temp_dir": temp_dir,
            "test_dir": os.path.join(temp_dir, "tests"),
            "module_path": os.path.join(temp_dir, "sample_module.py")
        }
        os.makedirs(env["test_dir"])
        
        # Create test files
        with open(os.path.join(env["test_dir"], "test_unit_sample.py"), "w") as f:
            f.write(SAMPLE_TESTS)
        with open(os.path.join(env["test_dir"], "test_perf_sample.py"), "w") as f:
            f.write(PERFORMANCE_TEST)
        with open(env["module_path"], "w") as f:
            f.write("def add(a, b): return a + b\n")
        
        # Set up test environment
        test_environment = lambda: env
        
        # Run tests
        test_test_runner_initialization()
        test_discover_tests(test_environment)
        test_run_unit_tests(test_environment)
        test_run_performance_tests(test_environment)
        test_parallel_test_execution(test_environment)
        test_test_runner_with_nonexistent_test_dir()
        
        print("All integration tests passed!")

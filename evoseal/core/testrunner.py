"""
TestRunner class for executing tests against code variants in isolated environments.
Supports unit, integration, and performance tests, with timeout, resource monitoring,
and parallel execution.
"""

import concurrent.futures
import subprocess
import threading
import time
from typing import Any, Callable, Optional

DEFAULT_TIMEOUT = 60  # seconds


class TestRunner:
    """A class for running tests against code variants in isolated environments.
    
    This class provides functionality to run different types of tests (unit, integration,
    performance) against code variants with support for timeouts, resource monitoring,
    and parallel execution.
    """
    
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_workers: int = 4) -> None:
        """Initialize the TestRunner.
        
        Args:
            timeout: Maximum time in seconds to wait for tests to complete
            max_workers: Maximum number of parallel test executions
        """
        self.timeout = timeout
        self.max_workers = max_workers

    def run_tests(
        self, variant_path: str, test_types: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """Run specified test types against a code variant.
        
        Args:
            variant_path: Path to the code variant to test
            test_types: List of test types to run (e.g., ["unit", "integration"])
            
        Returns:
            List of test results, one per test type
        """
        test_types = test_types or ["unit"]
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=min(self.max_workers, len(test_types))
        ) as executor:
            future_to_test = {
                executor.submit(self._run_single_test, variant_path, test_type): test_type
                for test_type in test_types
            }
            
            for future in concurrent.futures.as_completed(future_to_test):
                test_type = future_to_test[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append({
                        "test_type": test_type,
                        "success": False,
                        "error": str(exc),
                        "output": "",
                        "duration": 0,
                    })
        
        return results
    
    def _run_single_test(self, variant_path: str, test_type: str) -> dict[str, Any]:
        """Run a single test type against a code variant.
        
        Args:
            variant_path: Path to the code variant to test
            test_type: Type of test to run (e.g., "unit", "integration")
            
        Returns:
            Dictionary containing test results
        """
        start_time = time.time()
        cmd = self._get_test_command(variant_path, test_type)
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
            )
            
            return {
                "test_type": test_type,
                "success": result.returncode == 0,
                "output": result.stdout + result.stderr,
                "duration": time.time() - start_time,
            }
            
        except subprocess.TimeoutExpired:
            return {
                "test_type": test_type,
                "success": False,
                "error": f"Test timed out after {self.timeout} seconds",
                "output": "",
                "duration": self.timeout,
            }
    
    @staticmethod
    def _get_test_command(variant_path: str, test_type: str) -> list[str]:
        """Get the command to run for a specific test type.
        
        Args:
            variant_path: Path to the code variant
            test_type: Type of test to run
            
        Returns:
            Command to execute as a list of strings
            
        Raises:
            ValueError: If the test type is not supported
        """
        if test_type == "unit":
            return ["pytest", variant_path, "--tb=short", "-q"]
        elif test_type == "integration":
            return ["pytest", variant_path, "-m", "integration", "--tb=short", "-q"]
        elif test_type == "performance":
            return ["pytest", variant_path, "--benchmark-only", "--tb=short", "-q"]
        else:
            raise ValueError(f"Unknown test type: {test_type}")

"""
TestRunner class for executing tests against code variants in isolated environments.
Supports unit, integration, and performance tests, with timeout, resource monitoring,
and parallel execution.
"""

import concurrent.futures

# nosec B404: Required for test execution in isolated environments
import subprocess  # nosec B404: Required for test execution in a controlled environment
import threading
import time
from typing import Any, Callable, Optional

DEFAULT_TIMEOUT = 60  # seconds


class TestRunner:
    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_workers: int = 4):
        self.timeout = timeout
        self.max_workers = max_workers

    def run_tests(
        self, variant_path: str, test_types: Optional[list[str]] = None
    ) -> list[dict[str, Any]]:
        """
        Run specified test types against the code variant at variant_path.
        Returns a list of dicts with results for each test type.
        """
        test_types = test_types or ["unit"]
        valid_types = {"unit", "integration", "performance"}
        for test_type in test_types:
            if test_type not in valid_types:
                raise ValueError(f"Unknown test type: {test_type}")
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {
                executor.submit(self._run_single_test, variant_path, test_type): test_type
                for test_type in test_types
            }
            for future in concurrent.futures.as_completed(futures):
                test_type = futures[future]
                try:
                    result = future.result(timeout=self.timeout)
                except Exception as e:
                    result = {
                        "test_type": test_type,
                        "status": "error",
                        "error": str(e),
                    }
                results.append(result)
        return results

    def _run_single_test(self, variant_path: str, test_type: str) -> dict[str, Any]:
        """
        Run a single test type (unit/integration/performance) in isolation.
        Returns a dict with status, output, and metrics.
        """
        cmd = self._build_test_command(variant_path, test_type)
        start_time = time.time()
        try:
            proc = subprocess.run(  # nosec B603: Input commands are controlled and validated, shell=False prevents shell injection
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                check=False,
                shell=False,  # Explicitly set to False for security
            )
            duration = time.time() - start_time
            return {
                "test_type": test_type,
                "status": "passed" if proc.returncode == 0 else "failed",
                "output": proc.stdout,
                "error": proc.stderr,
                "duration": duration,
                "returncode": proc.returncode,
            }
        except subprocess.TimeoutExpired:
            return {
                "test_type": test_type,
                "status": "timeout",
                "output": "",
                "error": f"Test {test_type} timed out after {self.timeout}s",
                "duration": self.timeout,
                "returncode": None,
            }
        except Exception as e:
            return {
                "test_type": test_type,
                "status": "error",
                "output": "",
                "error": str(e),
                "duration": None,
                "returncode": None,
            }

    def _build_test_command(self, variant_path: str, test_type: str) -> list[str]:
        """
        Build the shell command to run the specified test type on the variant.
        """
        if test_type == "unit":
            return ["pytest", variant_path, "--tb=short", "-q"]
        elif test_type == "integration":
            return ["pytest", variant_path, "-m", "integration", "--tb=short", "-q"]
        elif test_type == "performance":
            return ["pytest", variant_path, "--benchmark-only", "--tb=short", "-q"]
        else:
            raise ValueError(f"Unknown test type: {test_type}")

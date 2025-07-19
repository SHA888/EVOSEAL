"""
TestRunner class for executing tests against code variants in isolated environments.
Supports unit, integration, and performance tests, with timeout, resource monitoring,
and parallel execution.
"""

import concurrent.futures
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# nosec B404: Required for test execution in isolated environments
import psutil  # type: ignore
import pytest  # type: ignore
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# Default configuration
DEFAULT_TIMEOUT = 60  # seconds
DEFAULT_TEST_DIR = "tests"
DEFAULT_TEST_PATTERNS = {
    "unit": "test_*.py",
    "integration": "test_*_integration.py",
    "performance": "test_*_perf.py",
}

# Custom types
TestResult = Dict[str, Any]
TestResults = List[TestResult]

# Console for rich output
console = Console()


@dataclass
class TestConfig:
    """Configuration for test execution."""

    test_dir: str = DEFAULT_TEST_DIR
    test_patterns: Dict[str, str] = field(default_factory=lambda: dict(DEFAULT_TEST_PATTERNS))
    timeout: int = DEFAULT_TIMEOUT
    max_workers: int = 4
    capture_output: bool = True
    coverage: bool = False
    coverage_report: str = "html"  # or "term", "xml", ""
    random_seed: Optional[int] = None
    log_level: str = "INFO"
    extra_args: List[str] = field(default_factory=list)


@dataclass
class ResourceUsage:
    """Track resource usage during test execution."""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    io_read_mb: float = 0.0
    io_write_mb: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    process: Optional[psutil.Process] = None

    def start(self) -> None:
        """Start tracking resource usage."""
        self.start_time = time.time()
        self.process = psutil.Process()
        self.process.cpu_percent()  # Initialize CPU tracking
        io_counters = self.process.io_counters()
        self.io_read_mb = io_counters.read_bytes / (1024 * 1024)
        self.io_write_mb = io_counters.write_bytes / (1024 * 1024)

    def stop(self) -> Dict[str, float]:
        """Stop tracking and return resource usage."""
        if not self.process:
            return {}

        self.end_time = time.time()
        
        # Get CPU and memory usage
        cpu_percent = self.process.cpu_percent()
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB
        
        # Get I/O usage
        io_counters = self.process.io_counters()
        io_read_mb = (io_counters.read_bytes / (1024 * 1024)) - self.io_read_mb
        io_write_mb = (io_counters.write_bytes / (1024 * 1024)) - self.io_write_mb
        
        return {
            "cpu_percent": cpu_percent,
            "memory_mb": memory_mb,
            "io_read_mb": io_read_mb,
            "io_write_mb": io_write_mb,
            "duration_sec": self.end_time - self.start_time,
        }


class TestRunner:
    """A class for running tests against code variants in isolated environments.

    This class provides functionality to run different types of tests (unit, integration,
    performance) against code variants with support for timeouts, resource monitoring,
    and parallel execution.
    """

    def __init__(self, config: Optional[TestConfig] = None) -> None:
        """Initialize the TestRunner.

        Args:
            config: Test configuration. If None, uses default configuration.
        """
        self.config = config or TestConfig()
        self.resource_usage = ResourceUsage()

    def discover_tests(self, test_type: str = "unit") -> List[str]:
        """Discover test files matching the specified test type pattern.

        Args:
            test_type: Type of tests to discover (e.g., "unit", "integration")

        Returns:
            List of discovered test file paths
        """
        pattern = self.config.test_patterns.get(test_type, self.config.test_patterns["unit"])
        test_dir = Path(self.config.test_dir)
        
        if not test_dir.exists():
            return []
            
        return [str(p) for p in test_dir.rglob(pattern)]

    def run_tests(
        self, 
        target_path: Union[str, Path], 
        test_types: Optional[List[str]] = None,
        **kwargs
    ) -> TestResults:
        """Run specified test types against a target path.

        Args:
            target_path: Path to the target to test (file or directory)
            test_types: List of test types to run (e.g., ["unit", "integration"])
            **kwargs: Override test configuration

        Returns:
            List of test results, one per test type
        """
        # Update config with any overrides
        config = self._update_config(kwargs)
        test_types = test_types or ["unit"]
        results: TestResults = []

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Running tests...", total=len(test_types))
            
            with concurrent.futures.ThreadPoolExecutor(
                max_workers=min(config.max_workers, len(test_types))
            ) as executor:
                future_to_test = {
                    executor.submit(self._run_test_type, str(target_path), test_type, config): test_type
                    for test_type in test_types
                }

                for future in concurrent.futures.as_completed(future_to_test):
                    test_type = future_to_test[future]
                    try:
                        result = future.result()
                        results.append(result)
                    except Exception as exc:
                        results.append(self._create_error_result(test_type, str(exc)))
                    
                    progress.update(task, advance=1, description=f"Completed {test_type} tests")

        return results

    def _run_test_type(
        self, 
        target_path: str, 
        test_type: str, 
        config: TestConfig
    ) -> TestResult:
        """Run all tests of a specific type against a target.

        Args:
            target_path: Path to the target to test
            test_type: Type of tests to run
            config: Test configuration

        Returns:
            Test result dictionary
        """
        # Start resource monitoring
        self.resource_usage.start()
        
        # Prepare test command
        cmd = self._get_test_command(target_path, test_type, config)
        
        # Run the tests
        try:
            result = self._execute_test_command(cmd, config)
            
            # Parse the test results
            test_result = self._parse_test_results(
                result, 
                test_type, 
                self.resource_usage.stop()
            )
            
            return test_result
            
        except Exception as exc:
            return self._create_error_result(
                test_type, 
                str(exc),
                self.resource_usage.stop() if self.resource_usage.process else None
            )
    
    def _execute_test_command(
        self, 
        cmd: List[str], 
        config: TestConfig
    ) -> subprocess.CompletedProcess:
        """Execute a test command with timeout and resource limits.
        
        Args:
            cmd: Command to execute
            config: Test configuration
            
        Returns:
            Completed process information
            
        Raises:
            subprocess.TimeoutExpired: If the command times out
            subprocess.CalledProcessError: If the command returns non-zero
        """
        # Set up environment
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join([str(Path.cwd())] + sys.path)
        
        # Execute the command
        return subprocess.run(
            cmd,
            capture_output=config.capture_output,
            text=True,
            timeout=config.timeout,
            check=False,
            shell=False,
            env=env,
        )
    
    def _get_test_command(
        self, 
        target_path: str, 
        test_type: str, 
        config: TestConfig
    ) -> List[str]:
        """Build the test command for the specified test type.
        
        Args:
            target_path: Path to the target to test
            test_type: Type of tests to run
            config: Test configuration
            
        Returns:
            Command as a list of arguments
            
        Raises:
            ValueError: If the test type is not supported
        """
        # Base pytest command
        cmd = [sys.executable, "-m", "pytest"]
        
        # Add common arguments
        cmd.extend(["--tb=short", "-v"])
        
        # Add type-specific arguments
        if test_type == "unit":
            cmd.extend(["-m", "not integration and not performance"])
        elif test_type == "integration":
            cmd.extend(["-m", "integration"])
        elif test_type == "performance":
            cmd.extend(["--benchmark-only"])
        else:
            raise ValueError(f"Unknown test type: {test_type}")
        
        # Add coverage if enabled
        if config.coverage:
            cmd.extend([
                "--cov", 
                "--cov-report", 
                config.coverage_report if config.coverage_report else ""
            ])
        
        # Add random seed if specified
        if config.random_seed is not None:
            cmd.extend(["--random-order-seed", str(config.random_seed)])
        
        # Add log level
        cmd.extend(["--log-level", config.log_level])
        
        # Add target path and any extra arguments
        cmd.extend([target_path] + config.extra_args)
        
        return cmd
    
    def _parse_test_results(
        self, 
        result: subprocess.CompletedProcess, 
        test_type: str,
        resources: Dict[str, float]
    ) -> TestResult:
        """Parse test results from pytest output.
        
        Args:
            result: Completed process information
            test_type: Type of tests that were run
            resources: Resource usage information
            
        Returns:
            Parsed test results
        """
        # Extract test statistics from output
        stats = self._extract_test_stats(result.stdout)
        
        return {
            "test_type": test_type,
            "success": result.returncode == 0,
            "exit_code": result.returncode,
            "output": result.stdout + result.stderr,
            "timestamp": datetime.utcnow().isoformat(),
            "resources": resources,
            **stats,
        }
    
    @staticmethod
    def _extract_test_stats(output: str) -> Dict[str, Any]:
        """Extract test statistics from pytest output.
        
        Args:
            output: Pytest output
            
        Returns:
            Dictionary of test statistics
        """
        stats = {
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "tests_errors": 0,
            "test_duration": 0.0,
        }
        
        # Parse pytest output for test results
        result_patterns = {
            "tests_run": r'(\d+) (?:tests?|ran) in',
            "tests_passed": r'(\d+) (?:passed|PASSED)',
            "tests_failed": r'(\d+) (?:failed|FAILED)',
            "tests_skipped": r'(\d+) (?:skipped|SKIPPED)',
            "tests_errors": r'(\d+) (?:errors?|ERRORS?)',
            "test_duration": r'in (\d+\.\d+)s',
        }
        
        for stat, pattern in result_patterns.items():
            match = re.search(pattern, output)
            if match:
                try:
                    value = float(match.group(1))
                    stats[stat] = int(value) if stat != "test_duration" else value
                except (ValueError, IndexError):
                    continue
        
        return stats
    
    @staticmethod
    def _create_error_result(
        test_type: str, 
        error: str, 
        resources: Optional[Dict[str, float]] = None
    ) -> TestResult:
        """Create an error result dictionary.
        
        Args:
            test_type: Type of test that failed
            error: Error message
            resources: Optional resource usage information
            
        Returns:
            Error result dictionary
        """
        return {
            "test_type": test_type,
            "success": False,
            "error": error,
            "output": error,
            "timestamp": datetime.utcnow().isoformat(),
            "resources": resources or {},
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "tests_skipped": 0,
            "tests_errors": 1,
            "test_duration": 0.0,
        }
    
    def _update_config(self, overrides: Dict[str, Any]) -> TestConfig:
        """Update test configuration with overrides.
        
        Args:
            overrides: Dictionary of configuration overrides
            
        Returns:
            Updated test configuration
        """
        if not overrides:
            return self.config
            
        # Create a new config with overrides
        config_dict = self.config.__dict__.copy()
        config_dict.update({
            k: v for k, v in overrides.items() 
            if k in config_dict and not k.startswith('_')
        })
        
        # Handle test_patterns specially to merge dicts
        if 'test_patterns' in overrides and isinstance(overrides['test_patterns'], dict):
            config_dict['test_patterns'].update(overrides['test_patterns'])
        
        return TestConfig(**config_dict)

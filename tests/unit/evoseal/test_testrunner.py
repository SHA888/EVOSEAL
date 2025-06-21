"""
Unit tests for the TestRunner class in evoseal.
Covers test execution, timeout, error handling, and parallelism.
"""

from unittest.mock import MagicMock, patch

import pytest

from evoseal.testrunner import TestRunner

MAGIC_MAX_WORKERS = 2


@pytest.fixture
def runner():
    return TestRunner(timeout=2, max_workers=MAGIC_MAX_WORKERS)


def test_run_tests_success(runner):
    with patch("evoseal.testrunner.subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "All tests passed"
        mock_proc.stderr = ""
        mock_run.return_value = mock_proc
        results = runner.run_tests("dummy/path", test_types=["unit", "integration"])
        assert len(results) == MAGIC_MAX_WORKERS
        for r in results:
            assert r["status"] == "passed"
            assert "output" in r
            assert r["returncode"] == 0


def test_run_tests_failure(runner):
    with patch("evoseal.testrunner.subprocess.run") as mock_run:
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = "Some tests failed"
        mock_proc.stderr = "Error"
        mock_run.return_value = mock_proc
        results = runner.run_tests("dummy/path", test_types=["unit"])
        assert results[0]["status"] == "failed"
        assert results[0]["error"] == "Error"


def test_run_tests_timeout(runner):
    with patch("evoseal.testrunner.subprocess.run") as mock_run:
        mock_run.side_effect = TimeoutError("Timeout!")
        results = runner.run_tests("dummy/path", test_types=["unit"])
        assert results[0]["status"] in ("timeout", "error")


def test_run_tests_unknown_type(runner):
    with pytest.raises(ValueError):
        runner.run_tests("dummy/path", test_types=["unknown"])

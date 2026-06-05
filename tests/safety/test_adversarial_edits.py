"""
Adversarial self-modification tests for EVOSEAL.

Tests that the system prevents two attack windows from task 2.2 ADR:
- (T1) DGM edits targeting out-of-scope files (configs/safety.yaml, Makefile, .env)
        are blocked by the allowlist (task 2.13)
- (T2) Test code in a variant that tries to read secrets or write forbidden paths
        is isolated by the sandboxed test environment (task 2.14)

Status: These tests assume task 2.13 (edit-scope allowlist) and task 2.14
(sandboxed test execution) are implemented. Until then, they use mocks to define
the expected interface and behavior.
"""

import os
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, Mock, patch

import pytest


class MockEditValidator:
    """Mock for task 2.13 (edit-scope allowlist) functionality."""

    PROTECTED_PATHS = {
        "configs/safety.yaml",
        "Makefile",
        ".env",
        ".github/workflows/",
        ".git/",
    }

    @staticmethod
    def is_path_editable(file_path: str) -> bool:
        """Check if a file is in the editable-path allowlist."""
        file_path = str(file_path)
        # Check exact matches
        if file_path in MockEditValidator.PROTECTED_PATHS:
            return False
        # Check directory prefixes
        for protected in MockEditValidator.PROTECTED_PATHS:
            if file_path.startswith(protected):
                return False
        return True

    @staticmethod
    def validate_variant_edits(edited_files: list[str]) -> dict[str, Any]:
        """
        Validate that all edited files are in the allowlist.
        Returns: {
            'valid': bool,
            'violations': list[str]  # files that failed allowlist check
        }
        """
        violations = []
        for file_path in edited_files:
            if not MockEditValidator.is_path_editable(file_path):
                violations.append(file_path)

        return {
            "valid": len(violations) == 0,
            "violations": violations,
        }


class MockTestSandbox:
    """Mock for task 2.14 (sandboxed test execution) functionality."""

    @staticmethod
    def run_variant_tests(variant_code: str, test_commands: list[str]) -> dict[str, Any]:
        """
        Run variant tests in an isolated environment.
        - Secrets stripped from env
        - Network disabled/restricted
        - configs/safety.yaml and .env mounted read-only
        - Runs as unprivileged user (where applicable)

        Returns: {
            'passed': bool,
            'stdout': str,
            'stderr': str,
            'violations': list[str]  # any attempts to violate sandbox
        }
        """
        # This is a mock; real implementation in task 2.14
        return {
            "passed": True,
            "stdout": "",
            "stderr": "",
            "violations": [],
        }

    @staticmethod
    def detect_secret_access_attempts(variant_code: str) -> list[str]:
        """Detect if variant code tries to access secret env vars."""
        suspicious_patterns = [
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "os.environ",
            "os.getenv",
        ]
        attempts = []
        for pattern in suspicious_patterns:
            if pattern in variant_code:
                attempts.append(f"Suspicious pattern: {pattern}")
        return attempts


# ============================================================================
# T1 Window Tests: Edit-scope allowlist (task 2.13)
# ============================================================================


class TestT1EditScopeAllowlist:
    """Test that DGM edits targeting out-of-scope files are rejected."""

    def test_t1_reject_safety_yaml_edit(self):
        """T1-1: Reject edit targeting configs/safety.yaml."""
        edited_files = ["evoseal/core/foo.py", "configs/safety.yaml"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"], "Should reject configs/safety.yaml edit"
        assert "configs/safety.yaml" in result["violations"]

    def test_t1_reject_makefile_edit(self):
        """T1-2: Reject edit targeting Makefile."""
        edited_files = ["evoseal/core/foo.py", "Makefile"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"], "Should reject Makefile edit"
        assert "Makefile" in result["violations"]

    def test_t1_reject_env_edit(self):
        """T1-3: Reject edit targeting .env."""
        edited_files = ["evoseal/core/foo.py", ".env"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"], "Should reject .env edit"
        assert ".env" in result["violations"]

    def test_t1_reject_workflow_edit(self):
        """T1-4: Reject edit targeting .github/workflows/."""
        edited_files = ["evoseal/core/foo.py", ".github/workflows/ci.yml"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"], "Should reject workflow edit"
        assert ".github/workflows/ci.yml" in result["violations"]

    def test_t1_reject_git_state_edit(self):
        """T1-5: Reject edit targeting .git directory."""
        edited_files = ["evoseal/core/foo.py", ".git/config"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"], "Should reject .git edit"
        assert ".git/config" in result["violations"]

    def test_t1_allow_core_edits(self):
        """T1-6: Allow edits to evoseal/core/."""
        edited_files = ["evoseal/core/foo.py", "evoseal/core/bar.py"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert result["valid"], "Should allow core edits"
        assert len(result["violations"]) == 0

    def test_t1_allow_integration_edits(self):
        """T1-7: Allow edits to evoseal/integration/."""
        edited_files = ["evoseal/integration/dgm_adapter.py"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert result["valid"], "Should allow integration edits"

    def test_t1_allow_test_edits(self):
        """T1-8: Allow edits to tests/."""
        edited_files = ["tests/unit/core/test_foo.py"]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert result["valid"], "Should allow test edits"

    def test_t1_mixed_valid_and_invalid(self):
        """T1-9: Report violations even when mixed with valid edits."""
        expected_violations = 2
        edited_files = [
            "evoseal/core/good.py",  # valid
            "configs/safety.yaml",  # invalid
            "tests/unit/test_good.py",  # valid
            "Makefile",  # invalid
        ]
        result = MockEditValidator.validate_variant_edits(edited_files)
        assert not result["valid"]
        assert len(result["violations"]) == expected_violations
        assert "configs/safety.yaml" in result["violations"]
        assert "Makefile" in result["violations"]

    def test_t1_allowlist_not_editable_by_loop(self):
        """T1-10: The allowlist itself cannot be edited by the loop."""
        # This is a structural requirement: the allowlist is not editable
        # even to itself. This prevents the loop from weakening its own guards.
        # Validation should be hardcoded, not loaded from an editable config.
        protected = MockEditValidator.PROTECTED_PATHS
        assert isinstance(protected, set)
        # In real impl (2.13), this should be a code-level constant,
        # not loaded from any mutable configuration


# ============================================================================
# T2 Window Tests: Sandboxed test execution (task 2.14)
# ============================================================================


class TestT2SandboxedTestExecution:
    """Test that variant test code is isolated from secrets and restricted paths."""

    def test_t2_strip_secrets_from_environment(self):
        """T2-1: Secrets are stripped from subprocess environment."""
        # Task 2.14 responsibility: when running variant tests,
        # ANTHROPIC_API_KEY, OPENAI_API_KEY, and .env should not be
        # visible to the subprocess.
        variant_code = "import os; key = os.environ.get('ANTHROPIC_API_KEY')"
        attempts = MockTestSandbox.detect_secret_access_attempts(variant_code)
        assert len(attempts) > 0, "Should detect secret access attempts"

    def test_t2_reject_secret_in_getenv(self):
        """T2-2: Reject variants that try to read secrets via os.getenv."""
        variant_code = """
import os
api_key = os.getenv('OPENAI_API_KEY')
"""
        attempts = MockTestSandbox.detect_secret_access_attempts(variant_code)
        # In real impl, this code would fail at runtime because
        # the env var is stripped. Here we just verify detection.
        assert len(attempts) > 0

    def test_t2_network_isolation(self):
        """T2-3: Network access is restricted or disabled for test subprocess.

        Real implementation (task 2.14) should verify:
        - No TCP/UDP sockets created
        - Or sockets restricted to localhost
        - Or iptables/firewall prevents egress
        """
        # This is documented intent; actual enforcement is platform-dependent
        pass

    def test_t2_safety_yaml_readonly(self):
        """T2-4: configs/safety.yaml is mounted/enforced read-only.

        Example malicious variant code (verified by 2.14 at runtime):
            with open('configs/safety.yaml', 'w') as f:
                f.write('bad config')

        Task 2.14 should prevent this at subprocess exec time
        by making the file read-only or by containerization.
        """
        # Documented requirement; enforcement is task 2.14
        pass

    def test_t2_env_file_readonly(self):
        """T2-5: .env is mounted/enforced read-only.

        Example malicious variant code (verified by 2.14 at runtime):
            with open('.env', 'w') as f:
                f.write('BAD_KEY=value')

        Task 2.14 should prevent file writes via read-only mounting.
        """
        # Documented requirement; enforcement is task 2.14
        pass

    def test_t2_forbidden_path_write_blocked(self):
        """T2-6: Variant cannot write to .git, .github, or Makefile."""
        # This overlaps with T1 (edit-scope allowlist), but T2 is the
        # runtime enforcement for code that the loop did not generate.
        # For example, if DGM generates code that *then runs tests*,
        # and the test code tries to write .git, the test sandbox
        # should block it.
        pass

    def test_t2_unprivileged_user_execution(self):
        """T2-7: Test subprocess runs as unprivileged user (where applicable).

        On Unix-like systems, subprocess should run as a non-root user
        with restricted capabilities.
        """
        # Platform-dependent; documented as intent
        pass

    def test_t2_cpu_and_memory_limits(self):
        """T2-8: Resource limits enforced (CPU, memory, open files).

        Per task 2.15 (runaway controls), subprocess should have:
        - CPU time ≤ ~120s
        - Address space ≤ 2 GB
        - Open files ≤ 256
        """
        # This is actually task 2.15, not 2.14, but related
        pass


# ============================================================================
# Integration Tests: Rollback on violation
# ============================================================================


class TestRollbackOnViolation:
    """Test that violations in T1/T2 trigger rollback."""

    def test_rollback_on_t1_violation(self):
        """Integration: T1 violation → rollback triggered."""
        # When an edit violates the allowlist, the variant should be rejected
        # and a rollback initiated (via safety_integration.py).
        # This test assumes task 2.13 is integrated into the evolution loop.
        pass

    def test_rollback_on_t2_violation(self):
        """Integration: T2 violation (test isolation breach) → rollback triggered."""
        # When variant tests try to read secrets or write protected paths,
        # the test fails, variant is rejected, rollback initiated.
        # This test assumes task 2.14 is integrated into the evolution loop.
        pass


# ============================================================================
# Configuration and Fixtures
# ============================================================================


@pytest.fixture
def mock_edit_validator():
    """Fixture: mock edit validator (task 2.13)."""
    return MockEditValidator()


@pytest.fixture
def mock_test_sandbox():
    """Fixture: mock test sandbox (task 2.14)."""
    return MockTestSandbox()


@pytest.fixture
def temp_safety_yaml(tmp_path):
    """Fixture: temporary safety.yaml for testing."""
    safety_file = tmp_path / "configs" / "safety.yaml"
    safety_file.parent.mkdir(parents=True, exist_ok=True)
    safety_file.write_text("""
# Temporary safety config for testing
auto_checkpoint: true
auto_rollback: true
regression_threshold: 0.05
""")
    return safety_file


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

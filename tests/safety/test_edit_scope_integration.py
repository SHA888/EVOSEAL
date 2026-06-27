"""
Integration tests for edit-scope validation in SafetyIntegration.

Verifies that the SafetyIntegration class properly validates edits
before they are applied to the filesystem.
"""

from pathlib import Path

import pytest

from evoseal.core.edit_scope_validator import EditScopeError
from evoseal.core.safety_integration import SafetyIntegration


@pytest.fixture
def repo_root(tmp_path):
    """Create a minimal repo structure."""
    (tmp_path / "evoseal").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".env").touch()
    (tmp_path / "Makefile").touch()
    return tmp_path


@pytest.fixture
def safety_integration(repo_root):
    """Create a SafetyIntegration instance with edit scope validation enabled."""
    config = {
        "auto_checkpoint": True,
        "auto_rollback": True,
        "safety_checks_enabled": True,
        "enforce_edit_scope": True,
        "edit_scope": {
            "allowed_patterns": {
                "evoseal/": True,
                "tests/": True,
                "examples/": True,
                "docs/": True,
            }
        },
    }
    return SafetyIntegration(config, repo_root=repo_root)


class TestEditScopeIntegration:
    """Test SafetyIntegration's edit-scope validation."""

    def test_safety_integration_validates_forbidden_edits(self, safety_integration, repo_root):
        """SafetyIntegration rejects edits to forbidden files."""
        forbidden_path = str(repo_root / "configs" / "safety.yaml")

        with pytest.raises(EditScopeError):
            safety_integration.validate_edit_path(forbidden_path)

    def test_safety_integration_accepts_allowed_edits(self, safety_integration, repo_root):
        """SafetyIntegration accepts edits to allowed files."""
        allowed_path = str(repo_root / "evoseal" / "feature.py")

        # Should not raise
        safety_integration.validate_edit_path(allowed_path)

    def test_edit_scope_disabled_allows_any_path(self, repo_root):
        """When enforce_edit_scope=False, any path is allowed."""
        config = {
            "enforce_edit_scope": False,
        }
        safety_integration = SafetyIntegration(config, repo_root=repo_root)
        forbidden_path = str(repo_root / "configs" / "safety.yaml")

        # Should not raise even for forbidden path
        safety_integration.validate_edit_path(forbidden_path)

    def test_safety_status_includes_edit_scope_enforcement(self, safety_integration):
        """Safety status reports whether edit scope is enforced."""
        status = safety_integration.get_safety_status()
        assert "edit_scope_enforced" in status
        assert status["edit_scope_enforced"] is True

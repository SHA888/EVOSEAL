"""
Adversarial tests for edit-scope allowlist (Tier 1, T1 window).

These tests verify that the system rejects edits targeting safety-critical files
(configs/safety.yaml, .env, Makefile, .github/workflows/) and anything outside
the declared mutable surface, as defined by threat model §3 and §6.

See task 2.13 in Plans.md for DoD context.
"""

from pathlib import Path

import pytest

from evoseal.core.edit_scope_validator import EditScopeError, EditScopeValidator


@pytest.fixture
def validator():
    """Create a validator with default allowlist."""
    return EditScopeValidator()


@pytest.fixture
def repo_root(tmp_path):
    """Create a minimal repo structure."""
    # Create a fake repo root
    (tmp_path / "evoseal").mkdir()
    (tmp_path / "configs").mkdir()
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".env").touch()
    (tmp_path / "Makefile").touch()
    (tmp_path / "tests").mkdir()
    return tmp_path


class TestEditScopeAllowlist:
    """Test that edits targeting forbidden paths are rejected."""

    def test_reject_safety_config_edit(self, validator, repo_root):
        """Edits to configs/safety.yaml are rejected (T1 window control)."""
        forbidden_path = str(repo_root / "configs" / "safety.yaml")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(forbidden_path, repo_root)

        assert "safety.yaml" in str(exc_info.value)
        assert "forbidden" in str(exc_info.value).lower()

    def test_reject_env_file_edit(self, validator, repo_root):
        """Edits to .env are rejected (secrets protection)."""
        forbidden_path = str(repo_root / ".env")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(forbidden_path, repo_root)

        assert ".env" in str(exc_info.value)

    def test_reject_makefile_edit(self, validator, repo_root):
        """Edits to Makefile are rejected (critical build config)."""
        forbidden_path = str(repo_root / "Makefile")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(forbidden_path, repo_root)

        assert "Makefile" in str(exc_info.value)

    def test_reject_github_workflows_edit(self, validator, repo_root):
        """Edits to .github/workflows/ are rejected (CI integrity)."""
        forbidden_path = str(repo_root / ".github" / "workflows" / "ci.yml")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(forbidden_path, repo_root)

        assert ".github/workflows" in str(exc_info.value)

    def test_reject_git_directory_edit(self, validator, repo_root):
        """Edits to .git/ are rejected (integrity protection)."""
        git_dir = repo_root / ".git"
        git_dir.mkdir(exist_ok=True)
        forbidden_path = str(git_dir / "config")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(forbidden_path, repo_root)

        assert ".git" in str(exc_info.value)

    def test_reject_outside_repo_root(self, validator, repo_root):
        """Edits outside repo root are rejected."""
        outside_path = "/etc/passwd"

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(outside_path, repo_root)

        assert "outside" in str(exc_info.value).lower() or "scope" in str(exc_info.value).lower()

    def test_accept_evoseal_module_edit(self, validator, repo_root):
        """Edits to evoseal/ module files are accepted."""
        allowed_path = str(repo_root / "evoseal" / "core" / "new_feature.py")

        # Should not raise
        validator.validate_edit_path(allowed_path, repo_root)

    def test_accept_test_edit(self, validator, repo_root):
        """Edits to tests/ are accepted (test infrastructure is mutable)."""
        allowed_path = str(repo_root / "tests" / "unit" / "test_new.py")

        # Should not raise
        validator.validate_edit_path(allowed_path, repo_root)

    def test_accept_examples_edit(self, validator, repo_root):
        """Edits to examples/ are accepted."""
        examples_dir = repo_root / "examples"
        examples_dir.mkdir()
        allowed_path = str(examples_dir / "new_example.py")

        # Should not raise
        validator.validate_edit_path(allowed_path, repo_root)

    def test_accept_docs_edit(self, validator, repo_root):
        """Edits to docs/ are accepted."""
        docs_dir = repo_root / "docs"
        docs_dir.mkdir()
        allowed_path = str(docs_dir / "new_doc.md")

        # Should not raise
        validator.validate_edit_path(allowed_path, repo_root)

    def test_allowlist_is_immutable(self, validator):
        """The allowlist itself cannot be modified by the validator (it is immutable)."""
        original_forbidden = validator.forbidden_paths.copy()
        original_allowed = validator.allowed_patterns.copy()

        # The validator should not expose mutable setters; check that the patterns
        # are defined as constants or read-only properties
        assert hasattr(
            validator, "forbidden_paths"
        ), "forbidden_paths should be a defined attribute"
        assert hasattr(
            validator, "allowed_patterns"
        ), "allowed_patterns should be a defined attribute"

        # After validator operations, the rules should not have changed
        try:
            validator.validate_edit_path("/tmp/test.py", Path("/tmp"))
        except EditScopeError:
            pass

        assert validator.forbidden_paths == original_forbidden
        assert validator.allowed_patterns == original_allowed

    def test_relative_path_handling(self, validator, repo_root):
        """Paths are canonicalized before validation (absolute + normalization)."""
        # Resolve a relative path within the repo_root context
        relative_within_repo = "evoseal/test.py"
        absolute_within_repo = str(repo_root / relative_within_repo)

        # Should not raise - this is within the allowed mutable surface
        validator.validate_edit_path(absolute_within_repo, repo_root)

        # A relative path that would resolve outside repo (when resolved from repo_root)
        # Create an absolute path that is outside repo_root
        outside_repo = "/etc/passwd"

        # Validator should handle this gracefully (reject or raise clearly)
        # This tests that path traversal attacks don't bypass the allowlist
        with pytest.raises((EditScopeError, ValueError)):
            validator.validate_edit_path(outside_repo, repo_root)

    def test_symlink_attacks_rejected(self, validator, repo_root):
        """Symlink attacks (symlink to forbidden file) are rejected."""
        symlink_path = repo_root / "allowed_symlink"
        forbidden_target = repo_root / "configs" / "safety.yaml"

        # Create a symlink that points to a forbidden file
        forbidden_target.parent.mkdir(exist_ok=True)
        forbidden_target.touch()
        symlink_path.symlink_to(forbidden_target)

        # The validator should reject this (either by detecting the symlink
        # or by resolving it and rejecting the target)
        with pytest.raises(EditScopeError):
            validator.validate_edit_path(str(symlink_path), repo_root)

    def test_adversarial_edit_targeting_safety_yaml(self, validator, repo_root):
        """Adversarial case: DGM-generated edit attempting to disable safety checks.

        This tests the T1 window control from the threat model: a variant
        that tries to edit configs/safety.yaml to lower guardrails is blocked
        at the edit-application time, not at outcome validation.
        """
        safety_config_path = str(repo_root / "configs" / "safety.yaml")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(safety_config_path, repo_root)

        error_msg = str(exc_info.value)
        assert "forbidden" in error_msg.lower()
        assert "safety" in error_msg.lower()

    def test_adversarial_edit_targeting_env_secrets(self, validator, repo_root):
        """Adversarial case: DGM-generated edit attempting to exfiltrate .env.

        Blocking this prevents the variant from reading API keys even if
        it somehow gained read access to .env during the subprocess execution.
        """
        env_path = str(repo_root / ".env")

        with pytest.raises(EditScopeError) as exc_info:
            validator.validate_edit_path(env_path, repo_root)

        error_msg = str(exc_info.value)
        assert ".env" in error_msg or "env" in error_msg.lower()

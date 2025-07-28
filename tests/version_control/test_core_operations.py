"""Unit tests for core Git operations."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from evoseal.utils.version_control.cmd_git import CmdGit
from evoseal.utils.version_control.exceptions import GitError


def test_initialize_new_repo(temp_dir: Path):
    """Test initializing a new Git repository."""
    repo = CmdGit(repo_path=temp_dir)
    result = repo.initialize()

    assert result is repo
    assert repo.repo_path == temp_dir
    assert (temp_dir / ".git").exists()


def test_initialize_existing_repo(git_repo: CmdGit):
    """Test initializing an existing Git repository."""
    repo_path = git_repo.repo_path

    # Should not raise an exception
    repo = CmdGit(repo_path=repo_path)
    result = repo.initialize()

    assert result is repo
    assert repo.repo_path == repo_path


def test_clone_repository(temp_dir: Path, git_remote_repo: Path):
    """Test cloning a repository."""
    # Create and initialize the source repository
    source_path = temp_dir / "source"
    source_path.mkdir(parents=True, exist_ok=True)

    # Initialize the source repository
    repo = CmdGit(repo_path=source_path)
    repo.initialize()

    # Configure user for the test repository
    repo._run_git_command(["config", "user.name", "Test User"])
    repo._run_git_command(["config", "user.email", "test@example.com"])

    # Create a file and commit it
    test_file = repo.repo_path / "test.txt"
    test_file.write_text("test")
    repo._run_git_command(["add", "test.txt"])
    repo._run_git_command(["commit", "-m", "Add test file"])

    # Set the default branch to main
    repo._run_git_command(["branch", "-M", "main"])

    # Add the remote
    repo._run_git_command(["remote", "add", "origin", str(git_remote_repo)])

    # Push to the remote with the full refspec
    success, stdout, stderr = repo._run_git_command(["push", "-u", "origin", "main:main"])
    assert success, f"Failed to push to remote: {stderr}"

    # Clone the repository
    clone_path = temp_dir / "clone"

    # Create the clone directory first
    clone_path.mkdir(parents=True, exist_ok=True)

    # Initialize and clone the repository
    cloned_repo = CmdGit(repo_path=clone_path)
    cloned_repo.initialize()

    # Configure user for the cloned repository
    cloned_repo._run_git_command(["config", "user.name", "Test User"])
    cloned_repo._run_git_command(["config", "user.email", "test@example.com"])

    # Add the remote
    cloned_repo._run_git_command(["remote", "add", "origin", str(git_remote_repo)])

    # Fetch and pull the changes
    cloned_repo._run_git_command(["fetch", "origin", "main"])
    cloned_repo._run_git_command(["checkout", "-b", "main", "--track", "origin/main"])
    cloned_repo._run_git_command(["pull", "origin", "main"])

    # Verify the clone was successful
    assert cloned_repo.repo_path == clone_path

    # Check that the test file exists and has the correct content
    cloned_test_file = clone_path / "test.txt"
    assert cloned_test_file.exists(), f"Test file not found in {clone_path}"
    assert cloned_test_file.read_text() == "test"


def test_commit_changes(git_repo: CmdGit):
    """Test committing changes to the repository."""
    # Create a new file
    test_file = git_repo.repo_path / "test.txt"
    test_file.write_text("test content")

    # Explicitly stage the file first
    git_repo._run_git_command(["add", "test.txt"])

    # Commit the file
    result = git_repo.commit("Add test file")

    # Verify the commit was successful
    assert result.success

    # Check the git log to see our commit
    success, log_output, _ = git_repo._run_git_command(["log", "--oneline"])
    assert success
    assert "Add test file" in log_output

    # Check that the file is tracked and clean
    status_result = git_repo.status()
    assert status_result.success
    assert "nothing to commit, working tree clean" in status_result.output.lower()


def test_push_changes(git_repo_with_commit: CmdGit, git_remote_repo: Path):
    """Test pushing changes to a remote repository."""
    # Configure user for the test repository
    git_repo_with_commit._run_git_command(["config", "user.name", "Test User"])
    git_repo_with_commit._run_git_command(["config", "user.email", "test@example.com"])

    # Add the remote
    result = git_repo_with_commit.add_remote("origin", str(git_remote_repo))
    assert result.success

    # Ensure we're on the main branch and it's tracked
    git_repo_with_commit._run_git_command(["branch", "-M", "main"])

    # Create a file and commit it
    test_file = git_repo_with_commit.repo_path / "test_push.txt"
    test_file.write_text("test push content")

    # Stage and commit the file
    git_repo_with_commit._run_git_command(["add", "test_push.txt"])
    git_repo_with_commit._run_git_command(["commit", "-m", "Add test file for push"])

    # Push to the remote with the -u flag to set upstream
    result = git_repo_with_commit.push(remote="origin", branch="main", set_upstream=True)
    assert result.success, f"Push failed: {result.error}"

    # Verify the push was successful by checking the remote
    success, remote_refs, _ = git_repo_with_commit._run_git_command(
        ["ls-remote", "origin", "refs/heads/main"]
    )
    assert success, "Failed to list remote refs"
    assert "main" in remote_refs, "Main branch not found in remote refs"


def test_pull_changes(temp_dir: Path, git_remote_repo: Path):
    """Test pulling changes from a remote repository."""
    # Create the first repository directory and initialize
    repo1_path = temp_dir / "repo1"
    repo1_path.mkdir(parents=True, exist_ok=True)

    # Initialize the first repository
    repo1 = CmdGit(repo_path=repo1_path)
    repo1.initialize()

    # Configure user for the test repository
    repo1._run_git_command(["config", "user.name", "Test User"])
    repo1._run_git_command(["config", "user.email", "test@example.com"])

    # Create and add a test file
    test_file = repo1_path / "test_file.txt"
    test_file.write_text("initial content")

    # Stage and commit the file
    repo1._run_git_command(["add", "test_file.txt"])
    repo1._run_git_command(["commit", "-m", "Initial commit"])

    # Add the remote and push the initial commit
    repo1.add_remote("origin", str(git_remote_repo))

    # Set the default branch to main and push
    repo1._run_git_command(["branch", "-M", "main"])
    repo1.push(remote="origin", branch="main")

    # Create a second repository
    repo2_path = temp_dir / "repo2"
    repo2_path.mkdir(parents=True, exist_ok=True)

    # Initialize the second repository
    repo2 = CmdGit(repo_path=repo2_path)
    repo2.initialize()

    # Configure user for the test repository
    repo2._run_git_command(["config", "user.name", "Test User"])
    repo2._run_git_command(["config", "user.email", "test@example.com"])

    # Add the remote
    repo2._run_git_command(["remote", "add", "origin", str(git_remote_repo)])

    # Fetch and checkout the main branch
    repo2._run_git_command(["fetch", "origin", "main"])
    repo2._run_git_command(["checkout", "-b", "main", "--track", "origin/main"])
    repo2._run_git_command(["pull", "origin", "main"])

    # Verify the clone was successful by checking if the test file exists
    test_file = repo2_path / "test_file.txt"
    assert test_file.exists(), f"Test file not found in {repo2_path}"

    # Make a change in the first repository and push
    new_file = repo1_path / "new_file.txt"
    new_file.write_text("new content")
    repo1._run_git_command(["add", "new_file.txt"])
    repo1._run_git_command(["commit", "-m", "Add new file"])

    # Push the changes
    push_result = repo1.push(remote="origin", branch="main")
    assert push_result.success, f"Failed to push changes: {push_result.error or 'Unknown error'}"

    # Pull the changes in the second repository
    pull_result = repo2.pull(remote="origin", branch="main")

    # Verify the pull was successful
    assert pull_result.success, f"Failed to pull changes: {pull_result.error or 'Unknown error'}"

    # Verify the new file exists and has the correct content
    new_file_path = repo2_path / "new_file.txt"
    assert new_file_path.exists(), f"File {new_file_path} does not exist after pull"
    assert new_file_path.read_text() == "new content", "File content does not match expected"


def test_checkout_branch(git_repo_with_commit: CmdGit):
    """Test checking out a branch."""
    # Get the current branch name (usually 'master' or 'main')
    success, default_branch, _ = git_repo_with_commit._run_git_command(["branch", "--show-current"])
    assert success
    default_branch = default_branch.strip()

    # Create a new branch using the CmdGit API
    result = git_repo_with_commit.branch("feature-branch")
    assert result.success

    # Checkout the new branch
    result = git_repo_with_commit.checkout("feature-branch")
    assert result.success

    # Verify we're on the new branch
    success, current_branch, _ = git_repo_with_commit._run_git_command(["branch", "--show-current"])
    assert success
    assert current_branch.strip() == "feature-branch"

    # Make a change and commit
    feature_file = git_repo_with_commit.repo_path / "feature.txt"
    feature_file.write_text("feature")

    # Stage and commit the file
    git_repo_with_commit._run_git_command(["add", "feature.txt"])
    git_repo_with_commit._run_git_command(["commit", "-m", "Add feature file"])

    # Checkout the default branch (master or main)
    result = git_repo_with_commit.checkout(default_branch)
    assert result.success

    # Verify the feature file doesn't exist in the default branch
    assert not feature_file.exists()

    # Checkout feature branch again
    result = git_repo_with_commit.checkout("feature-branch")
    assert result.success
    assert (git_repo_with_commit.repo_path / "feature.txt").exists()


def test_status(git_repo_with_commit: CmdGit):
    """Test getting repository status."""
    # Check status of clean repository
    result = git_repo_with_commit.status()
    assert result.success
    assert "nothing to commit" in result.output.lower()

    # Create an untracked file
    (git_repo_with_commit.repo_path / "new_file.txt").write_text("new")

    # Check status with untracked file
    result = git_repo_with_commit.status()
    assert "new_file.txt" in result.output
    assert "untracked files" in result.output.lower()


def test_diff(git_repo_with_commit: CmdGit):
    """Test getting repository diffs."""
    # Modify a file
    readme = git_repo_with_commit.repo_path / "README.md"
    readme.write_text("# Modified README\n")

    # Get the diff
    result = git_repo_with_commit.diff()

    assert result.success
    assert "README.md" in result.output
    assert "+# Modified README" in result.output

    # Stage the changes
    git_repo_with_commit._run_git_command(["add", "README.md"])

    # Get staged diff
    result = git_repo_with_commit.diff(staged=True)
    assert result.success
    assert "README.md" in result.output
    assert "+# Modified README" in result.output


def test_log(git_repo_with_commit: CmdGit):
    """Test getting commit logs."""
    # Make a few commits
    for i in range(3):
        (git_repo_with_commit.repo_path / f"file_{i}.txt").write_text(f"content {i}")
        git_repo_with_commit._run_git_command(["add", f"file_{i}.txt"])
        git_repo_with_commit._run_git_command(["commit", "-m", f"Add file {i}"])

    # Get the log
    result = git_repo_with_commit.log(n=2)

    assert result.success
    assert "Add file 2" in result.output
    assert "Add file 1" in result.output
    assert "Add file 0" not in result.output  # Should be limited to 2 commits


def test_branch_operations(git_repo_with_commit: CmdGit):
    """Test branch operations."""
    # Create a new branch
    result = git_repo_with_commit.branch("feature-branch")
    assert result.success

    # List branches and verify the new branch exists
    result = git_repo_with_commit.branch()
    assert result.success
    assert isinstance(result.output, str)
    assert "feature-branch" in result.output

    # Get the current branch
    success, current_branch, _ = git_repo_with_commit._run_git_command(["branch", "--show-current"])
    assert success

    # Switch to the new branch
    result = git_repo_with_commit.checkout("feature-branch")
    assert result.success

    # Create a file in the new branch
    test_file = git_repo_with_commit.repo_path / "branch_test.txt"
    test_file.write_text("test branch content")

    # Stage and commit the file
    git_repo_with_commit._run_git_command(["add", "branch_test.txt"])
    git_repo_with_commit._run_git_command(["commit", "-m", "Add test file to branch"])

    # Switch back to the original branch
    result = git_repo_with_commit.checkout(current_branch.strip())
    assert result.success

    # Delete the branch (must use -D to force delete as it's not fully merged)
    success, _, _ = git_repo_with_commit._run_git_command(["branch", "-D", "feature-branch"])
    assert success

    # Verify branch was deleted
    result = git_repo_with_commit.branch()
    assert result.success
    assert "feature-branch" not in result.output

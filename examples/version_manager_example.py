"""
Example usage of the VersionManager class.

This example demonstrates how to use the VersionManager to perform common
version control operations on a Git repository.
"""

import os
import tempfile
from pathlib import Path

from evoseal.utils.version_control import CmdGit, VersionManager


def main():
    # Create a temporary directory for the example
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")

        # Initialize a new Git repository
        print("\n1. Initializing a new Git repository...")
        vm = VersionManager(temp_dir, CmdGit(temp_dir))
        vm.initialize_repository()
        print(f"Repository initialized at: {vm.repo_path}")

        # Create a sample file
        sample_file = Path(temp_dir) / "README.md"
        sample_file.write_text("# My Project\n\nThis is a sample project.")
        print(f"\n2. Created sample file: {sample_file}")

        # Check status
        print("\n3. Git status:")
        status = vm.get_status()
        print(f"Staged: {status['staged']}")
        print(f"Unstaged: {status['unstaged']}")
        print(f"Untracked: {status['untracked']}")

        # Stage and commit the file
        print("\n4. Staging and committing the file...")
        commit_success = vm.create_commit("Initial commit", ["README.md"])
        if commit_success:
            print("Successfully committed changes")

        # Check the log
        print("\n5. Git log:")
        commits = vm.get_commit_history()
        for commit in commits:
            print(f"{commit.hash[:7]} {commit.author}: {commit.message}")

        # Create a new branch
        print("\n6. Creating and switching to a new branch...")
        branch_name = "feature/new-feature"
        branch_created = vm.create_branch(branch_name, checkout=True)
        if branch_created:
            print(f"Successfully created and switched to branch '{branch_name}'")

        # Get current branch
        current_branch = vm.get_current_branch()
        print(f"\n7. Current branch: {current_branch}")

        # List all branches
        print("\n8. All branches:")
        branches = vm.list_branches(include_remote=False)
        for branch in branches:
            print(f"- {branch.name}{' (current)' if branch.is_current else ''}")

        # Get repository structure
        print("\n9. Repository structure:")
        structure = vm.get_repository_structure()
        print(structure)

        print("\nExample completed successfully!")


if __name__ == "__main__":
    main()

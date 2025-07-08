"""
Example usage of the GitInterface class.

This example demonstrates how to use the CmdGit implementation of GitInterface
to perform common Git operations.
"""

import os
import tempfile
from pathlib import Path

from evoseal.utils.version_control import CmdGit, GitResult


def main():
    # Create a temporary directory for the example
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")

        # Initialize a new Git repository
        print("\n1. Initializing a new Git repository...")
        git = CmdGit(temp_dir).initialize()
        print(f"Repository initialized at: {git.repo_path}")

        # Create a sample file
        sample_file = Path(temp_dir) / "README.md"
        sample_file.write_text("# My Project\n\nThis is a sample project.")
        print(f"\n2. Created sample file: {sample_file}")

        # Check status
        print("\n3. Git status:")
        status = git.status()
        print(status.output)

        # Stage and commit the file
        print("\n4. Staging and committing the file...")
        commit_result = git.commit("Initial commit", ["README.md"])
        if commit_result.success:
            print("Successfully committed changes")
        else:
            print(f"Error committing changes: {commit_result.error}")

        # Check the log
        print("\n5. Git log:")
        log = git.log()
        print(log.output)

        # Create a new branch
        print("\n6. Creating and switching to a new branch...")
        branch_result = git.checkout("feature/new-feature", create=True)
        if branch_result.success:
            print(f"Successfully created and switched to branch 'feature/new-feature'")

        # Get repository structure
        print("\n7. Repository structure:")
        structure = git.get_repository_structure()
        print(structure)

        print("\nExample completed successfully!")


if __name__ == "__main__":
    main()

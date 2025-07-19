"""
Repository Management Module

This module provides utilities for managing git repositories in the EVOSEAL system.
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple, Set
from dataclasses import dataclass
from datetime import datetime
import logging

from git import Repo, GitCommandError, RemoteReference, Head

# Configure logging
logger = logging.getLogger(__name__)

class RepositoryError(Exception):
    """Base exception for repository-related errors."""
    pass

class RepositoryNotFoundError(RepositoryError):
    """Raised when a repository is not found."""
    pass

class BranchError(RepositoryError):
    """Raised for branch-related errors."""
    pass

class MergeError(RepositoryError):
    """Raised when a merge operation fails."""
    pass

class ConflictError(RepositoryError):
    """Raised when there are merge conflicts."""
    def __init__(self, message: str, conflicts: List[str] = None):
        super().__init__(message)
        self.conflicts = conflicts or []

class RepositoryManager:
    """Manages git repositories for the evolution pipeline."""
    
    def __init__(self, work_dir: Path):
        """Initialize the repository manager.
        
        Args:
            work_dir: Base working directory for repositories
        """
        self.work_dir = work_dir
        self.repos_dir = work_dir / "repositories"
        self.repos_dir.mkdir(parents=True, exist_ok=True)
    
    def clone_repository(self, url: str, name: Optional[str] = None) -> Path:
        """Clone a git repository.
        
        Args:
            url: URL of the git repository
            name: Optional name for the repository directory
            
        Returns:
            Path to the cloned repository
        """
        if name is None:
            name = url.split('/')[-1].replace('.git', '')
            
        repo_path = self.repos_dir / name
        
        # Remove existing directory if it exists
        if repo_path.exists():
            shutil.rmtree(repo_path)
        
        # Clone the repository
        repo = Repo.clone_from(url, repo_path)
        return repo_path
    
    def get_repository(self, name: str) -> Optional[Repo]:
        """Get a repository by name.
        
        Args:
            name: Name of the repository
            
        Returns:
            GitPython Repo object or None if not found
        """
        repo_path = self.repos_dir / name
        if not repo_path.exists():
            return None
        return Repo(repo_path)
    
    def checkout_branch(self, repo_name: str, branch: str, create: bool = False) -> bool:
        """Checkout a branch in the repository.
        
        Args:
            repo_name: Name of the repository
            branch: Branch name to checkout
            create: If True, create the branch if it doesn't exist
        
        Returns:
            bool: True if checkout was successful, False otherwise
        """
        repo = self.get_repository(repo_name)
        if not repo:
            return False
            
        try:
            if create:
                # Create and checkout new branch
                repo.git.checkout('-b', branch)
            else:
                # Checkout existing branch
                repo.git.checkout(branch)
            return True
        except git.GitCommandError as e:
            print(f"Failed to checkout branch: {e}")
            return False
    
    def commit_changes(
        self, 
        repo_name: str, 
        message: str, 
        paths: Optional[list] = None
    ) -> bool:
        """Commit changes in the repository.
        
        Args:
            repo_name: Name of the repository
            message: Commit message
            paths: Specific paths to commit (None for all changes)
            
        Returns:
            bool: True if commit was successful, False otherwise
        """
        repo = self.get_repository(repo_name)
        if not repo:
            return False
            
        try:
            if paths:
                repo.index.add(paths)
            else:
                repo.git.add('--all')
            
            # Check if there are any changes to commit
            if not repo.index.diff('HEAD'):
                return True
                
            repo.index.commit(message)
            return True
        except Exception as e:
            print(f"Failed to commit changes: {e}")
            return False
    
    def create_branch_from_commit(
        self,
        repo_name: str,
        branch_name: str,
        commit_hash: str
    ) -> bool:
        """Create a new branch from a specific commit.
        
        Args:
            repo_name: Name of the repository
            branch_name: Name of the new branch
            commit_hash: Commit hash to create branch from
            
        Returns:
            bool: True if branch creation was successful, False otherwise
        """
        repo = self.get_repository(repo_name)
        if not repo:
            return False
            
        try:
            # Create and checkout new branch at specific commit
            repo.git.checkout('-b', branch_name, commit_hash)
            return True
        except git.GitCommandError as e:
            print(f"Failed to create branch: {e}")
            return False
    
    def get_commit_info(self, repo_name: str, commit_hash: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific commit.
        
        Args:
            repo_name: Name of the repository
            commit_hash: Commit hash
            
        Returns:
            Dictionary with commit information or None if not found
        """
        repo = self.get_repository(repo_name)
        if not repo:
            return None
            
        try:
            commit = repo.commit(commit_hash)
            return {
                'hash': commit.hexsha,
                'author': str(commit.author),
                'message': commit.message.strip(),
                'date': commit.committed_datetime.isoformat(),
                'parents': [p.hexsha for p in commit.parents]
            }
        except git.GitCommandError:
            return None
    
    def get_status(self, repo_name: str) -> Dict[str, Any]:
        """Get the current status of the repository.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            Dictionary with repository status
            
        Raises:
            RepositoryNotFoundError: If repository is not found
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            return {
                'branch': repo.active_branch.name if not repo.head.is_detached else None,
                'detached': repo.head.is_detached,
                'dirty': repo.is_dirty(),
                'untracked': repo.untracked_files,
                'modified': [item.a_path for item in repo.index.diff(None)],
                'staged': [item.a_path for item in repo.index.diff('HEAD')],
                'commit': repo.head.commit.hexsha,
                'remote': next(iter(repo.remotes[0].urls)) if repo.remotes else None,
                'ahead': len(list(repo.iter_commits(f"{repo.active_branch.name}@{{u}}..{repo.active_branch.name}"))) if not repo.head.is_detached and repo.remotes else 0,
                'behind': len(list(repo.iter_commits(f"{repo.active_branch.name}..{repo.active_branch.name}@{{u}}"))) if not repo.head.is_detached and repo.remotes else 0
            }
        except GitCommandError as e:
            logger.error(f"Error getting status for repository '{repo_name}': {e}")
            raise RepositoryError(f"Failed to get repository status: {e}")
    
    def merge_branch(self, repo_name: str, source_branch: str, target_branch: str, no_ff: bool = False) -> Dict[str, Any]:
        """Merge changes from source branch into target branch.
        
        Args:
            repo_name: Name of the repository
            source_branch: Branch to merge from
            target_branch: Branch to merge into
            no_ff: If True, create a merge commit even if fast-forward is possible
            
        Returns:
            Dictionary with merge result
            
        Raises:
            RepositoryError: For general repository errors
            MergeError: If merge fails
            ConflictError: If there are merge conflicts
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            # Save current branch to return to it later
            current_branch = repo.active_branch.name if not repo.head.is_detached else None
            
            # Checkout target branch
            repo.git.checkout(target_branch)
            
            # Try to merge
            merge_result = repo.git.merge(source_branch, no_ff=no_ff, no_commit=True)
            
            # If we get here, merge was successful
            repo.git.merge('--continue')
            
            # Return to original branch if needed
            if current_branch and current_branch != target_branch:
                repo.git.checkout(current_branch)
                
            return {
                'success': True,
                'message': f"Successfully merged {source_branch} into {target_branch}",
                'result': merge_result
            }
            
        except GitCommandError as e:
            # Check for merge conflicts
            if 'CONFLICT' in str(e):
                conflicts = []
                for path in repo.index.unmerged:
                    if path not in conflicts:
                        conflicts.append(path)
                raise ConflictError(
                    f"Merge conflict in {repo_name}",
                    conflicts=conflicts
                )
            
            # Other git command errors
            logger.error(f"Error merging branch '{source_branch}' into '{target_branch}': {e}")
            raise MergeError(f"Failed to merge branches: {e}")
            
        except Exception as e:
            logger.error(f"Unexpected error during merge: {e}")
            raise RepositoryError(f"Unexpected error during merge: {e}")
    
    def resolve_conflicts(self, repo_name: str, resolution: Dict[str, str]) -> bool:
        """Resolve merge conflicts by providing resolutions for conflicted files.
        
        Args:
            repo_name: Name of the repository
            resolution: Dictionary mapping file paths to their resolved content
            
        Returns:
            bool: True if conflicts were resolved successfully
            
        Raises:
            RepositoryError: For general repository errors
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            # Write resolved content to files
            for file_path, content in resolution.items():
                full_path = repo.working_dir / file_path
                with open(full_path, 'w') as f:
                    f.write(content)
                repo.git.add(file_path)
                
            # Continue the merge
            repo.git.commit('-m', 'Resolved merge conflicts')
            return True
            
        except Exception as e:
            logger.error(f"Error resolving conflicts: {e}")
            raise RepositoryError(f"Failed to resolve conflicts: {e}")
    
    def create_tag(self, repo_name: str, tag_name: str, message: str = '', commit: str = 'HEAD') -> bool:
        """Create a tag at the specified commit.
        
        Args:
            repo_name: Name of the repository
            tag_name: Name of the tag
            message: Tag message
            commit: Commit to tag (default: HEAD)
            
        Returns:
            bool: True if tag was created successfully
            
        Raises:
            RepositoryError: If tag creation fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            repo.create_tag(tag_name, ref=commit, message=message)
            return True
        except GitCommandError as e:
            logger.error(f"Error creating tag '{tag_name}': {e}")
            raise RepositoryError(f"Failed to create tag: {e}")
    
    def get_diff(self, repo_name: str, base: str = 'HEAD', compare: str = None) -> str:
        """Get the diff between two commits or branches.
        
        Args:
            repo_name: Name of the repository
            base: Base commit/branch
            compare: Compare commit/branch (default: working directory)
            
        Returns:
            str: Diff output
            
        Raises:
            RepositoryError: If diff cannot be generated
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            if compare:
                return repo.git.diff(f"{base}..{compare}")
            return repo.git.diff(base)
        except GitCommandError as e:
            logger.error(f"Error generating diff: {e}")
            raise RepositoryError(f"Failed to generate diff: {e}")
    
    def stash_changes(self, repo_name: str, message: str = '') -> bool:
        """Stash changes in the working directory.
        
        Args:
            repo_name: Name of the repository
            message: Optional stash message
            
        Returns:
            bool: True if changes were stashed successfully
            
        Raises:
            RepositoryError: If stash operation fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            repo.git.stash('save', message)
            return True
        except GitCommandError as e:
            logger.error(f"Error stashing changes: {e}")
            raise RepositoryError(f"Failed to stash changes: {e}")
    
    def apply_stash(self, repo_name: str, stash_ref: str = 'stash@{0}') -> bool:
        """Apply a stashed change.
        
        Args:
            repo_name: Name of the repository
            stash_ref: Reference to the stash to apply (default: most recent)
            
        Returns:
            bool: True if stash was applied successfully
            
        Raises:
            RepositoryError: If stash application fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            repo.git.stash('apply', stash_ref)
            return True
        except GitCommandError as e:
            logger.error(f"Error applying stash: {e}")
            raise RepositoryError(f"Failed to apply stash: {e}")
            
    def get_branches(self, repo_name: str, remote: bool = False) -> List[str]:
        """Get list of branches in the repository.
        
        Args:
            repo_name: Name of the repository
            remote: If True, get remote branches instead of local
            
        Returns:
            List of branch names
            
        Raises:
            RepositoryError: If branch listing fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            if remote:
                return [ref.remote_head for ref in repo.remote().refs 
                       if ref.remote_head != 'HEAD']
            return [ref.name for ref in repo.branches]
        except Exception as e:
            logger.error(f"Error listing branches: {e}")
            raise RepositoryError(f"Failed to list branches: {e}")
            
    def get_commit_history(self, repo_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get commit history for the repository.
        
        Args:
            repo_name: Name of the repository
            limit: Maximum number of commits to return
            
        Returns:
            List of commit dictionaries with keys: hash, author, message, date
            
        Raises:
            RepositoryError: If commit history cannot be retrieved
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            commits = []
            for commit in repo.iter_commits(max_count=limit):
                commits.append({
                    'hash': commit.hexsha,
                    'author': str(commit.author),
                    'message': commit.message.strip(),
                    'date': commit.committed_datetime.isoformat()
                })
            return commits
        except Exception as e:
            logger.error(f"Error getting commit history: {e}")
            raise RepositoryError(f"Failed to get commit history: {e}")
            
    def reset_to_commit(self, repo_name: str, commit_hash: str, hard: bool = False) -> bool:
        """Reset repository to a specific commit.
        
        Args:
            repo_name: Name of the repository
            commit_hash: Hash of the commit to reset to
            hard: If True, discard all changes (dangerous!)
            
        Returns:
            bool: True if reset was successful
            
        Raises:
            RepositoryError: If reset fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            reset_type = '--hard' if hard else '--soft'
            repo.git.reset(reset_type, commit_hash)
            return True
        except GitCommandError as e:
            logger.error(f"Error resetting to commit {commit_hash}: {e}")
            raise RepositoryError(f"Failed to reset repository: {e}")
            
    def get_file_content(self, repo_name: str, file_path: str, 
                        ref: str = 'HEAD') -> Optional[str]:
        """Get the content of a file at a specific reference.
        
        Args:
            repo_name: Name of the repository
            file_path: Path to the file relative to repository root
            ref: Git reference (commit hash, branch, or tag)
            
        Returns:
            File content as string, or None if file doesn't exist
            
        Raises:
            RepositoryError: If file cannot be read
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            # Try to get the file content
            try:
                return repo.git.show(f"{ref}:{file_path}")
            except GitCommandError:
                return None
        except Exception as e:
            logger.error(f"Error reading file {file_path} at {ref}: {e}")
            raise RepositoryError(f"Failed to read file: {e}")
            
    def get_remote_url(self, repo_name: str, remote_name: str = 'origin') -> Optional[str]:
        """Get the URL of a remote repository.
        
        Args:
            repo_name: Name of the local repository
            remote_name: Name of the remote (default: 'origin')
            
        Returns:
            Remote URL if it exists, None otherwise
            
        Raises:
            RepositoryError: If repository access fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            for remote in repo.remotes:
                if remote.name == remote_name:
                    return list(remote.urls)[0]
            return None
        except Exception as e:
            logger.error(f"Error getting remote URL: {e}")
            raise RepositoryError(f"Failed to get remote URL: {e}")
            
    def get_default_branch(self, repo_name: str) -> str:
        """Get the default branch name of a repository.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            Name of the default branch (e.g., 'main', 'master')
            
        Raises:
            RepositoryError: If the default branch cannot be determined
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            # Try to get the default branch from the remote
            try:
                remote = repo.remote()
                if remote:
                    # Get the HEAD reference from the remote
                    remote_head = remote.refs.HEAD
                    if remote_head and hasattr(remote_head, 'reference'):
                        return remote_head.reference.name.split('/')[-1]
            except Exception:
                logger.debug("Could not determine default branch from remote, trying local")
            
            # Fall back to local branches
            for branch in repo.branches:
                if branch.name in ['main', 'master']:
                    return branch.name
            
            # If no standard branch found, return the first branch
            if repo.branches:
                return repo.branches[0].name
                
            raise RepositoryError("No branches found in repository")
            
        except Exception as e:
            logger.error(f"Error getting default branch: {e}")
            raise RepositoryError(f"Failed to get default branch: {e}")
            
    def pull_changes(self, repo_name: str, branch: Optional[str] = None) -> bool:
        """Pull the latest changes from the remote repository.
        
        Args:
            repo_name: Name of the repository
            branch: Branch to pull (default: current branch)
            
        Returns:
            bool: True if pull was successful, False otherwise
            
        Raises:
            RepositoryError: If the pull fails
        """
        repo = self.get_repository(repo_name)
        if not repo:
            raise RepositoryNotFoundError(f"Repository '{repo_name}' not found")
            
        try:
            # Get the current branch if none specified
            if not branch:
                branch = repo.active_branch.name
            
            # Ensure we're on the right branch
            if repo.active_branch.name != branch:
                self.checkout_branch(repo_name, branch)
            
            # Pull changes from the remote
            origin = repo.remote('origin')
            if not origin:
                raise RepositoryError("No remote named 'origin' found")
                
            # Fetch updates first
            origin.fetch()
            
            # Get the remote tracking branch
            remote_ref = f"origin/{branch}"
            if remote_ref not in repo.refs:
                raise RepositoryError(f"Remote branch {branch} not found")
            
            # Merge changes from the remote
            repo.git.merge(remote_ref)
            
            logger.info(f"Successfully pulled changes for {repo_name} on branch {branch}")
            return True
            
        except GitCommandError as e:
            error_msg = f"Failed to pull changes: {e}"
            logger.error(error_msg)
            raise RepositoryError(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error during pull: {e}"
            logger.error(error_msg, exc_info=True)
            raise RepositoryError(error_msg)
            
    def get_repository(self, repo_name: str) -> Optional[Repo]:
        """Get a repository object by name.
        
        Args:
            repo_name: Name of the repository
            
        Returns:
            git.Repo object if found, None otherwise
        """
        repo_path = self.repos_dir / repo_name
        if not repo_path.exists() or not (repo_path / '.git').exists():
            return None
            
        try:
            return Repo(repo_path)
        except Exception as e:
            logger.error(f"Error accessing repository {repo_name}: {e}")
            return None

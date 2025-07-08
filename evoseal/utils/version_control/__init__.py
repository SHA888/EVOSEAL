"""
Version Control Module for EVOSEAL

This module provides a unified interface for version control operations,
with implementations for different version control systems.
"""

from .cmd_git import CmdGit
from .config import default_git_implementation
from .git_interface import GitInterface, GitOperation, GitResult
from .version_manager import BranchInfo, CommitInfo, VersionManager

__all__ = [
    'GitInterface',
    'GitResult',
    'GitOperation',
    'CmdGit',
    'VersionManager',
    'CommitInfo',
    'BranchInfo',
    'default_git_implementation',
]

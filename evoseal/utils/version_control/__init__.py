"""
Version Control Module for EVOSEAL

This module provides a unified interface for version control operations,
with implementations for different version control systems.
"""

from .cmd_git import CmdGit
from .git_interface import GitInterface, GitOperation, GitResult

# Default implementation to use
default_git_implementation = CmdGit

__all__ = ['GitInterface', 'GitResult', 'GitOperation', 'CmdGit', 'default_git_implementation']

"""
Version Control Configuration

This module contains configuration and shared utilities for the version control module.
"""

from .cmd_git import CmdGit

# Default implementation to use
default_git_implementation = CmdGit

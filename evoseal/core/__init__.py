"""Core functionality for EVOSEAL's evolutionary framework.

This module contains the core components that power EVOSEAL's evolutionary
capabilities, including the main controller, evaluator, and selection mechanisms.
"""

from evoseal.core.controller import OpenEvolve
from evoseal.core.evaluator import Evaluator
from evoseal.core.selection import SelectionStrategy
from evoseal.core.version_database import VersionDatabase

__all__ = [
    'OpenEvolve',
    'Evaluator',
    'SelectionStrategy',
    'VersionDatabase',
]
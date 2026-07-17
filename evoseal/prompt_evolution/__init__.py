"""Prompt-level co-evolution for EVOSEAL's local (CPU) models.

Improves the coder/reviewer agents by evolving their *system prompts* from
reviewer feedback — the runnable substitute for GPU-only weight fine-tuning. See
``docs/architecture/local_coevolution.md``.
"""

from __future__ import annotations

from evoseal.providers.local_models import AgentRole

from .coevolution_manager import (
    DEFAULT_CODER_PROMPT,
    DEFAULT_REVIEWER_PROMPT,
    CoevolutionManager,
    default_manager,
)
from .models import (
    CodeAttempt,
    CoevolutionCycleResult,
    PromptVersion,
    ReviewCritique,
    TaskSpec,
)
from .prompt_evolver import PromptEditProposal, PromptEvolver
from .prompt_store import PromptStore

__all__ = [
    "AgentRole",
    "CoevolutionManager",
    "default_manager",
    "DEFAULT_CODER_PROMPT",
    "DEFAULT_REVIEWER_PROMPT",
    "TaskSpec",
    "CodeAttempt",
    "ReviewCritique",
    "PromptVersion",
    "CoevolutionCycleResult",
    "PromptEvolver",
    "PromptEditProposal",
    "PromptStore",
]

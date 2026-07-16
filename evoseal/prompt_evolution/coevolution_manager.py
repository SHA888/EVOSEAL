"""Prompt-level co-evolution loop driven by two local Ollama models.

One cycle:

1. **generate** - the coder model writes code for a task using its current
   system prompt.
2. **review**   - the reviewer model scores the code (0-1) and lists issues.
3. **evolve**   - if the score is below ``accept_threshold``, the reviewer model
   rewrites the coder's system prompt to address the issues (guardrailed).
4. **validate** - the task is re-run with the candidate prompt; the new prompt is
   accepted only if the score improves by at least ``min_score_gain`` — otherwise
   it is discarded and the previous prompt stays active (rollback).

This is the CPU-feasible substitute for EVOSEAL's Devstral weight fine-tuning: the
agents self-improve at the *prompt* level, no GPU required. The accept/rollback
gate mirrors the project's "validate or revert" safety premise.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from evoseal.providers.local_models import (
    DEFAULT_OLLAMA_BASE_URL,
    AgentRole,
)
from evoseal.providers.ollama_provider import OllamaProvider

from .models import (
    CodeAttempt,
    CoevolutionCycleResult,
    ReviewCritique,
    TaskSpec,
)
from .prompt_evolver import PromptEvolver
from .prompt_store import PromptStore

logger = logging.getLogger(__name__)

#: Stable header the coder prompt must always keep (guardrail marker).
CODER_ROLE_MARKER = "ROLE: coder"

DEFAULT_CODER_PROMPT = (
    f"# {CODER_ROLE_MARKER}\n"
    "You are a precise code-writing agent. For each task:\n"
    "- Output complete, runnable code — no placeholders, no TODOs, no ellipses.\n"
    "- Lead with the code in a single fenced block; keep prose to a sentence or two.\n"
    "- Handle edge cases and errors; do not assume inputs are always valid.\n"
    "- If requirements are ambiguous, state one assumption in a single line.\n"
)

DEFAULT_REVIEWER_PROMPT = (
    "# ROLE: reviewer\n"
    "You are a strict, concise code reviewer. Judge correctness, edge cases, error "
    "handling, and security. Be terse and specific.\n"
)


class CoevolutionManager:
    """Coordinate the coder/reviewer prompt co-evolution loop."""

    def __init__(
        self,
        *,
        coder_provider: Any | None = None,
        reviewer_provider: Any | None = None,
        prompt_store: PromptStore | None = None,
        evolver: PromptEvolver | None = None,
        base_url: str = DEFAULT_OLLAMA_BASE_URL,
        accept_threshold: float = 0.7,
        min_score_gain: float = 0.05,
        coder_seed_prompt: str = DEFAULT_CODER_PROMPT,
    ) -> None:
        # Providers resolve their model from what is installed (see local_models).
        self.coder = coder_provider or OllamaProvider(base_url=base_url, role=AgentRole.CODER)
        self.reviewer = reviewer_provider or OllamaProvider(
            base_url=base_url, role=AgentRole.REVIEWER
        )
        self.store = prompt_store or PromptStore()
        self.evolver = evolver or PromptEvolver(
            self.reviewer, protected_markers=(CODER_ROLE_MARKER,)
        )
        self.accept_threshold = accept_threshold
        self.min_score_gain = min_score_gain
        self._cycle_counter = 0

        # Ensure the coder role has an active prompt to start from.
        self.store.seed(AgentRole.CODER, coder_seed_prompt)

    async def run_cycle(self, task: TaskSpec) -> CoevolutionCycleResult:
        """Run one generate -> review -> (maybe) evolve pass for ``task``."""
        self._cycle_counter += 1
        cycle_id = f"cycle-{self._cycle_counter:04d}-{task.id}"

        active = self.store.get_active(AgentRole.CODER)
        if active is None:  # pragma: no cover - seed guarantees this
            active = self.store.seed(AgentRole.CODER, DEFAULT_CODER_PROMPT)
        prompt_before = active.prompt_text

        attempt = await self._generate(task, prompt_before)
        critique = await self._review(task, attempt)
        score_before = critique.score

        result = CoevolutionCycleResult(
            cycle_id=cycle_id,
            task_id=task.id,
            attempt=attempt,
            critique=critique,
            prompt_before_id=active.version_id,
            score_before=score_before,
        )

        if critique.passed(self.accept_threshold):
            result.reason = (
                f"score {score_before:.2f} >= threshold {self.accept_threshold:.2f}; "
                "no evolution needed"
            )
            logger.info("[%s] %s", cycle_id, result.reason)
            return result

        proposal = await self.evolver.evolve(
            current_prompt=prompt_before, task=task, attempt=attempt, critique=critique
        )
        result.evolved = True
        if not proposal.valid:
            result.reason = f"evolution rejected by guardrails: {proposal.reason}"
            logger.info("[%s] %s", cycle_id, result.reason)
            return result

        # Validate the candidate prompt actually helps before adopting it.
        revalidation = await self._generate(task, proposal.new_prompt)
        recritique = await self._review(task, revalidation)
        score_after = recritique.score
        result.score_after = score_after

        if score_after >= score_before + self.min_score_gain:
            new_version = self.store.register(
                AgentRole.CODER,
                proposal.new_prompt,
                parent_id=active.version_id,
                rationale=proposal.rationale,
                score=score_after,
                metrics={"score_before": score_before, "score_after": score_after},
            )
            result.accepted = True
            result.prompt_after_id = new_version.version_id
            result.reason = (
                f"accepted prompt {new_version.version_id}: "
                f"{score_before:.2f} -> {score_after:.2f}"
            )
        else:
            result.reason = (
                f"rolled back: candidate did not improve "
                f"({score_before:.2f} -> {score_after:.2f}, "
                f"need +{self.min_score_gain:.2f})"
            )
        logger.info("[%s] %s", cycle_id, result.reason)
        return result

    async def run_cycles(self, tasks: list[TaskSpec]) -> list[CoevolutionCycleResult]:
        """Run one cycle per task, in order, threading the evolving prompt through."""
        return [await self.run_cycle(task) for task in tasks]

    # -- model calls ---------------------------------------------------------

    async def _generate(self, task: TaskSpec, system_prompt: str) -> CodeAttempt:
        user = task.description
        if task.acceptance:
            user += f"\n\nAcceptance criteria:\n{task.acceptance}"
        response = await self.coder.submit_prompt(user, system=system_prompt)
        return CodeAttempt(
            task_id=task.id,
            model=getattr(self.coder, "model", "unknown"),
            code=self._extract_code(response),
            raw_response=response,
        )

    async def _review(self, task: TaskSpec, attempt: CodeAttempt) -> ReviewCritique:
        review_prompt = (
            f"Task:\n{task.description}\n\n"
            f"Code to review:\n{attempt.raw_response}\n\n"
            "List concrete issues as '- ' bullet points (correctness, edge cases, "
            "error handling, security). If none, write '- none'. Then, on the LAST "
            "line, output a quality score in exactly this format: 'SCORE: X/10' "
            "(X is 0-10, 10 is flawless)."
        )
        response = await self.reviewer.submit_prompt(review_prompt, system=DEFAULT_REVIEWER_PROMPT)
        score = self._parse_score(response)
        issues = self._parse_issues(response)
        return ReviewCritique(
            task_id=task.id,
            model=getattr(self.reviewer, "model", "unknown"),
            score=score,
            issues=issues,
            summary=response.strip()[:400],
            raw=response,
        )

    # -- parsing helpers -----------------------------------------------------

    @staticmethod
    def _extract_code(response: str) -> str:
        blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", response, re.DOTALL)
        if blocks:
            return "\n\n".join(b.strip() for b in blocks)
        return response.strip()

    @staticmethod
    def _parse_score(response: str) -> float:
        """Extract a 0-1 quality score from reviewer text."""
        match = re.search(r"SCORE:\s*(\d+(?:\.\d+)?)\s*/\s*(\d+(?:\.\d+)?)", response, re.I)
        if not match:
            match = re.search(r"(\d+(?:\.\d+)?)\s*/\s*(10|100|5)\b", response)
        if match:
            value, maximum = float(match.group(1)), float(match.group(2))
            if maximum > 0:
                return max(0.0, min(1.0, value / maximum))
        # No explicit score: fall back to an issue-count heuristic.
        issues = CoevolutionManager._parse_issues(response)
        real = [i for i in issues if i.strip().lower() not in {"none", "no issues"}]
        return max(0.0, 1.0 - 0.2 * len(real))

    @staticmethod
    def _parse_issues(response: str) -> list[str]:
        issues: list[str] = []
        for line in response.splitlines():
            stripped = line.strip()
            if stripped.startswith(("- ", "* ")):
                text = stripped[2:].strip()
                if text and not text.upper().startswith("SCORE:"):
                    issues.append(text)
        if len(issues) == 1 and issues[0].lower() in {"none", "no issues", "no issues found"}:
            return []
        return issues


def default_manager(base_dir: Path | str | None = None) -> CoevolutionManager:
    """Convenience factory: a manager backed by discovered local models."""
    return CoevolutionManager(prompt_store=PromptStore(base_dir))

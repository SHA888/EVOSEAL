"""Turn a reviewer critique into an improved coder system prompt.

This is the CPU-feasible analogue of SEAL's "self-edit": instead of fine-tuning
model *weights* from evolution data (which needs a GPU), we ask a model to rewrite
the *system prompt* so future attempts avoid the mistakes the reviewer flagged.

All edits pass through :meth:`PromptEvolver._validate` guardrails before they can
be accepted, because the prompt is a self-modification surface and a degenerate or
truncated rewrite must never silently replace a working prompt.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .models import CodeAttempt, ReviewCritique, TaskSpec

logger = logging.getLogger(__name__)

_OPEN = "<IMPROVED_PROMPT>"
_CLOSE = "</IMPROVED_PROMPT>"


class SupportsSubmitPrompt(Protocol):
    """Minimal provider interface the evolver needs (matches SEALProvider)."""

    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str: ...


@dataclass
class PromptEditProposal:
    """A candidate prompt rewrite plus the verdict of the guardrails."""

    new_prompt: str
    rationale: str
    valid: bool
    reason: str = ""


class PromptEvolver:
    """Distill critiques into guardrailed system-prompt edits."""

    def __init__(
        self,
        provider: SupportsSubmitPrompt,
        *,
        max_prompt_chars: int = 6000,
        min_prompt_chars: int = 80,
        protected_markers: tuple[str, ...] = (),
    ) -> None:
        self.provider = provider
        self.max_prompt_chars = max_prompt_chars
        self.min_prompt_chars = min_prompt_chars
        # Substrings that MUST survive an edit if they were in the original prompt
        # (e.g. a role header or a hard safety rule the loop must not delete).
        self.protected_markers = protected_markers

    async def evolve(
        self,
        *,
        current_prompt: str,
        task: TaskSpec,
        attempt: CodeAttempt,
        critique: ReviewCritique,
    ) -> PromptEditProposal:
        """Propose an improved version of ``current_prompt``."""
        meta_prompt = self._build_meta_prompt(current_prompt, task, attempt, critique)
        try:
            response = await self.provider.submit_prompt(meta_prompt, temperature=0.3)
        except Exception as exc:  # provider/network failure must not crash the loop
            logger.error("Prompt evolution call failed: %s", exc)
            return PromptEditProposal("", "", valid=False, reason=f"evolver call failed: {exc}")

        candidate = self._extract(response)
        if candidate is None:
            return PromptEditProposal(
                "", "", valid=False, reason="no improved prompt found in response"
            )

        valid, reason = self._validate(current_prompt, candidate)
        rationale = self._summarize_reason(critique)
        return PromptEditProposal(candidate, rationale, valid=valid, reason=reason)

    # -- internals -----------------------------------------------------------

    def _build_meta_prompt(
        self,
        current_prompt: str,
        task: TaskSpec,
        attempt: CodeAttempt,
        critique: ReviewCritique,
    ) -> str:
        issues = "\n".join(f"- {issue}" for issue in critique.issues) or "- (no itemized issues)"
        return (
            "You are improving the SYSTEM PROMPT of a code-writing agent so that its "
            "future answers avoid the problems a reviewer found.\n\n"
            f"TASK THE AGENT WAS GIVEN:\n{task.description}\n\n"
            f"REVIEWER SCORE: {critique.score:.2f} / 1.00\n"
            f"REVIEWER ISSUES:\n{issues}\n\n"
            f"REVIEWER SUMMARY:\n{critique.summary or '(none)'}\n\n"
            "CURRENT SYSTEM PROMPT (rewrite this, keep its role/identity and any "
            "safety rules intact):\n"
            f"---\n{current_prompt}\n---\n\n"
            "Rewrite the system prompt so a coder following it would avoid the issues "
            "above. Keep it concise and general (do NOT hard-code this one task's "
            "answer). Preserve the agent's role header and any existing rules; only "
            "add or sharpen guidance.\n\n"
            f"Reply with ONLY the full improved system prompt, wrapped exactly like "
            f"this and nothing else:\n{_OPEN}\n<the full improved system prompt>\n{_CLOSE}"
        )

    def _extract(self, response: str) -> str | None:
        """Pull the rewritten prompt out of a model response.

        Smaller models often ignore the sentinel markers, so we fall back to a
        fenced block or the whole response — but ONLY when it still carries every
        protected marker, so a plain critique can never masquerade as a prompt.
        The revalidation step then double-gates acceptance.
        """
        match = re.search(re.escape(_OPEN) + r"(.*?)" + re.escape(_CLOSE), response, re.DOTALL)
        if match:
            return match.group(1).strip()

        blocks = re.findall(r"```[a-zA-Z0-9_+-]*\n(.*?)```", response, re.DOTALL)
        for block in sorted(blocks, key=len, reverse=True):
            if self._looks_like_prompt(block):
                return block.strip()

        if self._looks_like_prompt(response):
            return response.strip()
        return None

    def _looks_like_prompt(self, text: str) -> bool:
        """Heuristic guard for markerless fallbacks (never a hard accept)."""
        if self.protected_markers:
            return all(marker in text for marker in self.protected_markers)
        return len(text.strip()) >= self.min_prompt_chars

    def _validate(self, current: str, candidate: str) -> tuple[bool, str]:
        stripped = candidate.strip()
        if len(stripped) < self.min_prompt_chars:
            return False, f"too short ({len(stripped)} < {self.min_prompt_chars} chars)"
        if len(stripped) > self.max_prompt_chars:
            return False, f"too long ({len(stripped)} > {self.max_prompt_chars} chars)"
        if stripped == current.strip():
            return False, "identical to current prompt"
        for marker in self.protected_markers:
            if marker in current and marker not in candidate:
                return False, f"dropped protected marker: {marker!r}"
        return True, "ok"

    @staticmethod
    def _summarize_reason(critique: ReviewCritique) -> str:
        head = critique.issues[0] if critique.issues else (critique.summary or "low score")
        return f"address reviewer feedback (score {critique.score:.2f}): {head}"

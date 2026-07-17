"""Unit tests for the guardrailed prompt evolver."""

from __future__ import annotations

import pytest

from evoseal.prompt_evolution import (
    CodeAttempt,
    PromptEvolver,
    ReviewCritique,
    TaskSpec,
)


class ScriptedProvider:
    """A provider that returns a fixed response (or raises)."""

    model = "scripted"

    def __init__(self, response: str | None = None, error: Exception | None = None):
        self.response = response
        self.error = error

    async def submit_prompt(self, prompt: str, **kwargs) -> str:
        if self.error is not None:
            raise self.error
        assert self.response is not None
        return self.response


def _task():
    return TaskSpec(id="t1", description="Write add(a, b) that returns a + b")


def _attempt():
    return CodeAttempt(task_id="t1", model="m", code="def add(a,b): return a-b", raw_response="...")


def _critique():
    return ReviewCritique(
        task_id="t1", model="m", score=0.3, issues=["add() subtracts instead of adds"]
    )


def _wrap(prompt: str) -> str:
    return f"<IMPROVED_PROMPT>\n{prompt}\n</IMPROVED_PROMPT>"


@pytest.mark.asyncio
async def test_valid_edit_extracted_and_accepted():
    new_prompt = (
        "# ROLE: coder\nBe precise. Verify that each operator matches the requested "
        "operation, handle edge cases, and always output complete, runnable code."
    )
    evolver = PromptEvolver(ScriptedProvider(_wrap(new_prompt)), protected_markers=("ROLE: coder",))
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert proposal.valid
    assert proposal.new_prompt == new_prompt
    assert "score 0.30" in proposal.rationale


@pytest.mark.asyncio
async def test_missing_markers_rejected():
    evolver = PromptEvolver(ScriptedProvider("here is a better prompt but no markers"))
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert not proposal.valid
    assert "no improved prompt" in proposal.reason


@pytest.mark.asyncio
async def test_markerless_fallback_accepted_when_protected_marker_present():
    # No sentinel markers, but the response IS a valid prompt carrying the required
    # protected marker -> fallback extraction should recover it.
    rewrite = (
        "# ROLE: coder\nYou are a precise coder. Verify operators match the requested "
        "operation, cover edge cases, and always return complete, runnable code."
    )
    evolver = PromptEvolver(ScriptedProvider(rewrite), protected_markers=("ROLE: coder",))
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert proposal.valid
    assert proposal.new_prompt == rewrite


@pytest.mark.asyncio
async def test_markerless_critique_not_mistaken_for_prompt():
    # A plain critique lacking the protected marker must NOT be accepted as a prompt.
    critique_text = (
        "The function subtracts instead of adds and has no error handling for "
        "non-numeric inputs; overall this needs a correctness fix before merging."
    )
    evolver = PromptEvolver(ScriptedProvider(critique_text), protected_markers=("ROLE: coder",))
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert not proposal.valid
    assert "no improved prompt" in proposal.reason


@pytest.mark.asyncio
async def test_dropped_protected_marker_rejected():
    # Candidate omits the required "ROLE: coder" marker (but is long enough to pass
    # the length guardrail, so the marker check is what rejects it).
    evolver = PromptEvolver(
        ScriptedProvider(
            _wrap(
                "You are a careful coding agent. Double-check operators and edge cases, "
                "and always return complete, runnable code with error handling."
            )
        ),
        protected_markers=("ROLE: coder",),
    )
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert not proposal.valid
    assert "protected marker" in proposal.reason


@pytest.mark.asyncio
async def test_too_short_rejected():
    evolver = PromptEvolver(ScriptedProvider(_wrap("tiny")), min_prompt_chars=80)
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert not proposal.valid
    assert "too short" in proposal.reason


@pytest.mark.asyncio
async def test_identical_prompt_rejected():
    current = (
        "# ROLE: coder\nWrite complete, correct, runnable code for the given task, "
        "handling edge cases and errors, and keeping prose to a minimum."
    )
    evolver = PromptEvolver(ScriptedProvider(_wrap(current)), protected_markers=("ROLE: coder",))
    proposal = await evolver.evolve(
        current_prompt=current, task=_task(), attempt=_attempt(), critique=_critique()
    )
    assert not proposal.valid
    assert "identical" in proposal.reason


@pytest.mark.asyncio
async def test_provider_error_is_contained():
    evolver = PromptEvolver(ScriptedProvider(error=RuntimeError("ollama down")))
    proposal = await evolver.evolve(
        current_prompt="# ROLE: coder\nWrite code.",
        task=_task(),
        attempt=_attempt(),
        critique=_critique(),
    )
    assert not proposal.valid
    assert "evolver call failed" in proposal.reason

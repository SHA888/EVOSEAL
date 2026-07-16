"""Unit tests for the co-evolution manager (generate/review/evolve/rollback)."""

from __future__ import annotations

import pytest

from evoseal.prompt_evolution import (
    AgentRole,
    CoevolutionManager,
    PromptEvolver,
    PromptStore,
    TaskSpec,
)


class SequenceProvider:
    """Returns queued responses in order; repeats the last one when exhausted."""

    def __init__(self, responses, model="seq"):
        self.responses = list(responses)
        self.model = model
        self.calls: list[tuple[str, dict]] = []

    async def submit_prompt(self, prompt: str, **kwargs) -> str:
        self.calls.append((prompt, kwargs))
        if len(self.responses) > 1:
            return self.responses.pop(0)
        return self.responses[0] if self.responses else ""


def _wrap(prompt: str) -> str:
    return f"<IMPROVED_PROMPT>\n{prompt}\n</IMPROVED_PROMPT>"


CODE_BAD = "```python\ndef add(a, b):\n    return a - b\n```"
CODE_GOOD = "```python\ndef add(a, b):\n    return a + b\n```"
IMPROVED = (
    "# ROLE: coder\nYou are a precise coder. Verify each operator matches the "
    "requested operation and cover edge cases. Output complete runnable code."
)


def _manager(tmp_path, coder, reviewer):
    return CoevolutionManager(
        coder_provider=coder,
        reviewer_provider=reviewer,
        prompt_store=PromptStore(tmp_path / "p"),
        evolver=PromptEvolver(reviewer, protected_markers=("ROLE: coder",)),
        accept_threshold=0.7,
        min_score_gain=0.05,
    )


@pytest.mark.asyncio
async def test_high_score_needs_no_evolution(tmp_path):
    coder = SequenceProvider([CODE_GOOD])
    reviewer = SequenceProvider(["- none\nSCORE: 9/10"])
    mgr = _manager(tmp_path, coder, reviewer)

    result = await mgr.run_cycle(TaskSpec(id="t1", description="Write add"))

    assert not result.evolved
    assert not result.accepted
    assert result.score_before >= 0.7
    assert "no evolution needed" in result.reason
    # Still only the seed version.
    assert len(mgr.store.list_versions(AgentRole.CODER)) == 1


@pytest.mark.asyncio
async def test_low_score_evolves_and_accepts_on_improvement(tmp_path):
    coder = SequenceProvider([CODE_BAD, CODE_GOOD])  # attempt, then revalidation
    reviewer = SequenceProvider(
        [
            "- add() subtracts instead of adds\nSCORE: 3/10",  # first review
            _wrap(IMPROVED),  # evolve
            "- none\nSCORE: 9/10",  # revalidation review
        ]
    )
    mgr = _manager(tmp_path, coder, reviewer)

    result = await mgr.run_cycle(TaskSpec(id="t1", description="Write add"))

    assert result.evolved
    assert result.accepted
    assert result.score_before == pytest.approx(0.3)
    assert result.score_after == pytest.approx(0.9)
    active = mgr.store.get_active(AgentRole.CODER)
    assert active.version_id == result.prompt_after_id
    assert active.prompt_text == IMPROVED


@pytest.mark.asyncio
async def test_no_improvement_rolls_back(tmp_path):
    coder = SequenceProvider([CODE_BAD, CODE_BAD])
    reviewer = SequenceProvider(
        [
            "- wrong operator\nSCORE: 3/10",  # first review
            _wrap(IMPROVED),  # evolve
            "- still wrong\nSCORE: 3/10",  # revalidation: no gain
        ]
    )
    mgr = _manager(tmp_path, coder, reviewer)
    seed_id = mgr.store.get_active(AgentRole.CODER).version_id

    result = await mgr.run_cycle(TaskSpec(id="t1", description="Write add"))

    assert result.evolved
    assert not result.accepted
    assert "rolled back" in result.reason
    # The active prompt is unchanged and no new version was adopted.
    assert mgr.store.get_active(AgentRole.CODER).version_id == seed_id


@pytest.mark.asyncio
async def test_guardrail_rejection_skips_revalidation(tmp_path):
    coder = SequenceProvider([CODE_BAD])
    reviewer = SequenceProvider(
        [
            "- wrong operator\nSCORE: 3/10",
            _wrap("no role marker and otherwise fine but drops the protected header text"),
        ]
    )
    mgr = _manager(tmp_path, coder, reviewer)

    result = await mgr.run_cycle(TaskSpec(id="t1", description="Write add"))

    assert result.evolved
    assert not result.accepted
    assert "guardrails" in result.reason
    assert result.score_after is None  # never revalidated
    # coder called exactly once (no revalidation attempt).
    assert len(coder.calls) == 1


def test_score_parsing_variants():
    assert CoevolutionManager._parse_score("blah\nSCORE: 10/10") == pytest.approx(1.0)
    assert CoevolutionManager._parse_score("SCORE: 5/10") == pytest.approx(0.5)
    assert CoevolutionManager._parse_score("rating 8/10 overall") == pytest.approx(0.8)
    # No explicit score -> issue-count heuristic (2 issues -> 1 - 0.4).
    heuristic = CoevolutionManager._parse_score("- issue one\n- issue two")
    assert heuristic == pytest.approx(0.6)


def test_issue_parsing_none():
    assert CoevolutionManager._parse_issues("- none\nSCORE: 9/10") == []
    assert CoevolutionManager._parse_issues("- a\n- b\nSCORE: 5/10") == ["a", "b"]

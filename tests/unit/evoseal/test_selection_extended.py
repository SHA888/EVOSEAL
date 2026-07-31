"""Extended unit tests for SelectionAlgorithm.

Covers custom fitness_key, empty population, custom strategies,
elitism edge cases, and other paths not covered by the original test_selection.py.
"""

from __future__ import annotations

import random
import secrets

import pytest

from evoseal.core.selection import SelectionAlgorithm

pytestmark = pytest.mark.unit


@pytest.fixture
def population():
    return [
        {"id": f"v{i}", "eval_score": score} for i, score in enumerate([0.9, 0.8, 0.7, 0.6, 0.5])
    ]


@pytest.fixture(autouse=False)
def seeded_rng(monkeypatch):
    """Replace secrets.SystemRandom with a seeded RNG for deterministic tests."""
    rng = random.Random(42)
    monkeypatch.setattr(secrets, "SystemRandom", lambda: rng)


# --- Custom fitness_key ---


def test_tournament_custom_fitness_key(population, seeded_rng):
    """Tournament selection should respect a custom fitness_key."""
    for ind in population:
        ind["custom_score"] = 1.0 - ind["eval_score"]  # invert scores
    selector = SelectionAlgorithm()
    selected = selector.select(
        population,
        num_selected=3,
        strategy="tournament",
        fitness_key="custom_score",
    )
    # v4 has the highest custom_score (0.5) so it is guaranteed as the elite.
    assert selected[0]["id"] == "v4"
    assert len(selected) == 3


def test_roulette_custom_fitness_key(population):
    """Roulette selection should respect a custom fitness_key."""
    for ind in population:
        ind["custom_score"] = 1.0 - ind["eval_score"]
    selector = SelectionAlgorithm()
    selected = selector.select(
        population,
        num_selected=3,
        strategy="roulette",
        fitness_key="custom_score",
    )
    assert len(selected) == 3


# --- Empty / minimal population ---


def test_tournament_empty_population_raises():
    """Empty population raises IndexError — the algorithm cannot sample from nothing."""
    selector = SelectionAlgorithm()
    with pytest.raises(IndexError):
        selector.select([], num_selected=3, strategy="tournament")


def test_roulette_empty_population_raises():
    """Empty population raises IndexError — the algorithm cannot sample from nothing."""
    selector = SelectionAlgorithm()
    with pytest.raises(IndexError):
        selector.select([], num_selected=3, strategy="roulette")


def test_tournament_single_individual():
    pop = [{"id": "v0", "eval_score": 0.5}]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=1, strategy="tournament")
    assert len(selected) == 1
    assert selected[0]["id"] == "v0"


def test_roulette_single_individual():
    pop = [{"id": "v0", "eval_score": 0.5}]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=1, strategy="roulette")
    assert len(selected) == 1


# --- Elitism edge cases ---


def test_elitism_larger_than_population():
    """When elitism >= population size, all individuals are elites."""
    pop = [{"id": "v0", "eval_score": 0.5}, {"id": "v1", "eval_score": 0.8}]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=2, strategy="tournament", elitism=5)
    assert len(selected) == 2
    # Both should be present as elites
    ids = {ind["id"] for ind in selected}
    assert ids == {"v0", "v1"}


def test_elitism_zero(population):
    """With elitism=0, no guaranteed top individuals."""
    selector = SelectionAlgorithm()
    selected = selector.select(population, num_selected=3, strategy="tournament", elitism=0)
    assert len(selected) == 3


# --- num_selected edge cases ---


def test_num_selected_larger_than_population(population, seeded_rng):
    """When num_selected > len(population), result is padded with repeats."""
    selector = SelectionAlgorithm()
    selected = selector.select(population, num_selected=10, strategy="tournament")
    assert len(selected) == 10
    population_ids = {ind["id"] for ind in population}
    selected_ids = [ind["id"] for ind in selected]
    assert set(selected_ids) <= population_ids
    assert len(set(selected_ids)) < len(selected_ids)


def test_num_selected_zero(population):
    selector = SelectionAlgorithm()
    selected = selector.select(population, num_selected=0, strategy="tournament")
    assert len(selected) == 0


# --- Custom strategies ---


def test_custom_strategy():
    def top_one(pop, num_selected, **kw):
        return [max(pop, key=lambda x: x.get("eval_score", 0))]

    selector = SelectionAlgorithm(strategies={"top_one": top_one})
    pop = [{"id": "v0", "eval_score": 0.3}, {"id": "v1", "eval_score": 0.9}]
    selected = selector.select(pop, num_selected=1, strategy="top_one")
    assert len(selected) == 1
    assert selected[0]["id"] == "v1"


# --- Negative / missing scores ---


def test_tournament_with_negative_scores(seeded_rng):
    pop = [{"id": f"v{i}", "eval_score": s} for i, s in enumerate([-0.5, 0.0, 0.5])]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=2, strategy="tournament")
    assert len(selected) == 2


def test_roulette_with_negative_scores(seeded_rng):
    """Negative scores are clamped to 0 in roulette selection."""
    pop = [{"id": f"v{i}", "eval_score": s} for i, s in enumerate([-0.5, 0.0, 0.5])]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=2, strategy="roulette")
    assert len(selected) == 2
    assert all(s["id"] in {"v0", "v1", "v2"} for s in selected)


def test_tournament_missing_eval_score(seeded_rng):
    """Missing eval_score defaults to 0."""
    pop = [{"id": "v0"}, {"id": "v1", "eval_score": 0.9}]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=1, strategy="tournament")
    assert len(selected) == 1
    assert selected[0]["id"] == "v1"

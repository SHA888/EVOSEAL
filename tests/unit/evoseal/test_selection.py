"""
Unit tests for the SelectionAlgorithm class in evoseal.

Covers tournament, roulette, elitism, and edge cases.
"""

import pytest

from evoseal.core.selection import SelectionAlgorithm

TOURNAMENT_SIZE = 2
NUM_SELECTED_TOURNAMENT = 3
NUM_SELECTED_ROULETTE = 4
ELITISM_COUNT = 2
ELITE_TOP_SCORES = [0.9, 0.8]
ZERO_FITNESS = 0.0
POPULATION_SIZE = 5
HIGH_SCORE = 0.9


@pytest.fixture
def population():
    return [
        {"id": f"v{i}", "eval_score": score} for i, score in enumerate([0.9, 0.8, 0.7, 0.6, 0.5])
    ]


def test_tournament_selection_basic(population):
    selector = SelectionAlgorithm()
    selected = selector.select(
        population,
        num_selected=NUM_SELECTED_TOURNAMENT,
        strategy="tournament",
        tournament_size=TOURNAMENT_SIZE,
    )
    assert len(selected) == NUM_SELECTED_TOURNAMENT
    # Should favor higher eval_score
    assert any(ind["eval_score"] == HIGH_SCORE for ind in selected)


def test_roulette_selection_basic(population):
    selector = SelectionAlgorithm()
    selected = selector.select(population, num_selected=NUM_SELECTED_ROULETTE, strategy="roulette")
    assert len(selected) == NUM_SELECTED_ROULETTE
    # Should favor higher eval_score
    assert any(ind["eval_score"] == HIGH_SCORE for ind in selected)


def test_elitism(population):
    selector = SelectionAlgorithm()
    selected = selector.select(
        population,
        num_selected=NUM_SELECTED_TOURNAMENT,
        strategy="tournament",
        elitism=ELITISM_COUNT,
    )
    top_scores = sorted([ind["eval_score"] for ind in selected], reverse=True)
    assert top_scores[:ELITISM_COUNT] == ELITE_TOP_SCORES


def test_zero_fitness():
    pop = [{"id": f"v{i}", "eval_score": ZERO_FITNESS} for i in range(POPULATION_SIZE)]
    selector = SelectionAlgorithm()
    selected = selector.select(pop, num_selected=NUM_SELECTED_TOURNAMENT, strategy="roulette")
    assert len(selected) == NUM_SELECTED_TOURNAMENT
    # Should not error even if all fitness are zero


def test_unknown_strategy(population):
    selector = SelectionAlgorithm()
    with pytest.raises(ValueError):
        selector.select(population, num_selected=2, strategy="unknown")

"""Unit tests for the Controller class in evoseal/core/controller.py."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from evoseal.core.controller import Controller


@pytest.fixture
def controller():
    mock_runner = MagicMock()
    mock_evaluator = MagicMock()
    return Controller(test_runner=mock_runner, evaluator=mock_evaluator)


# --- initialize ---


def test_initialize_sets_state_and_generation(controller):
    config = {"max_generations": 10, "strategy": "default"}
    controller.initialize(config)
    assert controller.state["config"] == config
    assert controller.state["generations"] == []
    assert controller.current_generation == 0


def test_initialize_resets_generation_counter(controller):
    controller.current_generation = 5
    controller.initialize({"k": "v"})
    assert controller.current_generation == 0


# --- select_candidates ---


def test_select_candidates_returns_top_n(controller):
    eval_results = [
        {"score": 0.3},
        {"score": 0.9},
        {"score": 0.5},
        {"score": 0.8},
        {"score": 0.1},
        {"score": 0.7},
    ]
    selected = controller.select_candidates(eval_results)
    assert len(selected) == 5  # default top 5
    scores = [r["score"] for r in selected]
    assert scores == sorted(scores, reverse=True)


def test_select_candidates_handles_fewer_than_five(controller):
    eval_results = [{"score": 0.5}, {"score": 0.9}]
    selected = controller.select_candidates(eval_results)
    assert len(selected) == 2


def test_select_candidates_defaults_missing_score_to_zero(controller):
    eval_results = [{"score": 0.8}, {}, {"score": 0.6}]
    selected = controller.select_candidates(eval_results)
    # The one without 'score' gets 0.0; top 3 should be 0.8, 0.6, 0.0
    assert len(selected) == 3
    assert selected[0]["score"] == 0.8


# --- run_generation ---


def test_run_generation_orchestrates_and_advances(controller):
    controller.initialize({})
    controller.test_runner.run_tests.return_value = [
        {"pass_rate": 1.0, "coverage": 0.9, "quality": 0.8},
    ]
    controller.evaluator.evaluate.return_value = [{"score": 0.95, "feedback": "ok"}]

    controller.run_generation()

    controller.test_runner.run_tests.assert_called_once_with(".")
    controller.evaluator.evaluate.assert_called_once()
    assert controller.current_generation == 1
    gen = controller.state["generations"][0]
    assert gen["generation"] == 0
    assert gen["test_results"] == controller.test_runner.run_tests.return_value
    assert gen["eval_results"] == controller.evaluator.evaluate.return_value


def test_run_generation_multiple(controller):
    controller.initialize({})
    controller.test_runner.run_tests.return_value = []
    controller.evaluator.evaluate.return_value = []

    controller.run_generation()
    controller.run_generation()

    assert controller.current_generation == 2
    assert len(controller.state["generations"]) == 2


# --- get_state ---


def test_get_state_empty_before_init(controller):
    assert controller.get_state() == {}


def test_get_state_returns_current_state(controller):
    controller.initialize({"foo": "bar"})
    state = controller.get_state()
    assert state["config"]["foo"] == "bar"


# --- cli_interface ---


def test_cli_status(controller):
    controller.initialize({"x": 1})
    result = controller.cli_interface("status")
    assert result["config"]["x"] == 1


def test_cli_run_generation(controller):
    controller.initialize({})
    controller.test_runner.run_tests.return_value = []
    controller.evaluator.evaluate.return_value = []
    result = controller.cli_interface("run_generation")
    assert result["msg"] == "Generation complete"
    assert result["generation"] == 1


def test_cli_unknown_command(controller):
    result = controller.cli_interface("nonexistent")
    assert "error" in result

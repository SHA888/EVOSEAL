"""
Unit tests for the OpenEvolve Controller class.
Covers initialization, generation management, coordination, candidate selection, and CLI interface.
"""

from unittest.mock import MagicMock

import pytest

from evoseal.controller import Controller


@pytest.fixture
def dummy_runner():
    runner = MagicMock()
    runner.run_tests.return_value = [
        {"id": 1, "score": 0.5},
        {"id": 2, "score": 0.8},
        {"id": 3, "score": 0.3},
    ]
    return runner


@pytest.fixture
def dummy_evaluator():
    evaluator = MagicMock()
    evaluator.evaluate.return_value = [
        {"id": 1, "score": 0.5},
        {"id": 2, "score": 0.8},
        {"id": 3, "score": 0.3},
    ]
    return evaluator


@pytest.fixture
def controller(dummy_runner, dummy_evaluator):
    return Controller(test_runner=dummy_runner, evaluator=dummy_evaluator)


def test_initialize(controller):
    config = {"param": 42}
    controller.initialize(config)
    state = controller.get_state()
    assert state["config"] == config
    assert state["generations"] == []
    assert controller.current_generation == 0


def test_run_generation(controller):
    controller.initialize({})
    controller.run_generation()
    state = controller.get_state()
    assert len(state["generations"]) == 1
    gen = state["generations"][0]
    assert gen["generation"] == 0
    assert "test_results" in gen
    assert "eval_results" in gen
    assert "selected" in gen
    assert controller.current_generation == 1


MAX_CANDIDATES = 3


def test_select_candidates(controller):
    eval_results = [
        {"id": 1, "score": 0.1},
        {"id": 2, "score": 0.9},
        {"id": 3, "score": 0.5},
    ]
    selected = controller.select_candidates(eval_results)
    assert selected[0]["score"] >= selected[1]["score"] >= selected[2]["score"]
    assert len(selected) <= MAX_CANDIDATES


def test_cli_interface_status(controller):
    controller.initialize({"foo": "bar"})
    status = controller.cli_interface("status")
    assert status["config"]["foo"] == "bar"


def test_cli_interface_run_generation(controller):
    controller.initialize({})
    resp = controller.cli_interface("run_generation")
    assert resp["msg"] == "Generation complete"
    assert resp["generation"] == 1


def test_cli_interface_unknown(controller):
    resp = controller.cli_interface("unknown_command")
    assert "error" in resp

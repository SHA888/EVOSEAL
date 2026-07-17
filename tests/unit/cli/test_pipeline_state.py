"""Regression tests for PipelineState persistence."""

from __future__ import annotations

import json

import pytest

from evoseal.cli.commands.pipeline import PipelineState


@pytest.fixture
def state_file(tmp_path):
    return str(tmp_path / "state" / "pipeline_state.json")


def test_missing_state_file_returns_default(state_file):
    state = PipelineState(state_file).load_state()
    assert state["status"] == "not_started"
    assert state["current_iteration"] == 0


def test_corrupt_state_file_returns_default_without_recursing(tmp_path, state_file):
    """A corrupt-but-present state file must not recurse.

    load_state() used to call itself on JSONDecodeError; because the file still
    existed, the existence check passed again and it looped until RecursionError.
    """
    mgr = PipelineState(state_file)
    mgr.ensure_state_dir()
    with open(state_file, "w") as f:
        f.write("{ this is not json")

    state = mgr.load_state()  # must not raise RecursionError

    assert state["status"] == "not_started"
    assert state["current_iteration"] == 0


def test_empty_state_file_returns_default(state_file):
    mgr = PipelineState(state_file)
    mgr.ensure_state_dir()
    open(state_file, "w").close()

    assert mgr.load_state()["status"] == "not_started"


def test_update_state_survives_a_corrupt_file(state_file):
    """update_state() reads then writes; a corrupt read must not break the write."""
    mgr = PipelineState(state_file)
    mgr.ensure_state_dir()
    with open(state_file, "w") as f:
        f.write("not json at all")

    mgr.update_state({"status": "running", "current_iteration": 3})

    with open(state_file) as f:
        written = json.load(f)
    assert written["status"] == "running"
    assert written["current_iteration"] == 3


def test_round_trip_state(state_file):
    mgr = PipelineState(state_file)
    mgr.save_state({**mgr._default_state(), "status": "paused"})
    assert mgr.load_state()["status"] == "paused"

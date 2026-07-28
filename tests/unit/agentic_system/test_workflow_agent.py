"""Unit tests for WorkflowAgent and WorkflowEngine.execute_step."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from evoseal.agents.agentic_workflow_agent import WorkflowAgent
from evoseal.core.workflow import WorkflowEngine


@pytest.fixture
def engine_with_component():
    """Create a WorkflowEngine with a registered mock component."""
    engine = WorkflowEngine()
    comp = MagicMock()
    comp.greet.return_value = "hello"
    engine.register_component("greeter", comp)
    return engine, comp


class TestWorkflowEngineExecuteStep:
    """Tests for the public WorkflowEngine.execute_step method."""

    def test_execute_step_sync_context(self, engine_with_component):
        """execute_step works from a plain sync context (no running loop)."""
        engine, comp = engine_with_component
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}
        result = engine.execute_step(step)
        assert result == "hello"
        comp.greet.assert_called_once()

    def test_execute_step_inside_running_loop(self, engine_with_component):
        """execute_step works when called from inside a running event loop."""
        engine, comp = engine_with_component
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        async def _run():
            return engine.execute_step(step)

        result = asyncio.run(_run())
        assert result == "hello"
        comp.greet.assert_called_once()

    def test_execute_step_propagates_error(self, engine_with_component):
        """execute_step propagates exceptions from the step."""
        engine, comp = engine_with_component
        comp.boom.side_effect = RuntimeError("kaboom")
        step = {"name": "bad", "component": "greeter", "method": "boom", "params": {}}
        with pytest.raises(RuntimeError, match="kaboom"):
            engine.execute_step(step)

    def test_execute_step_missing_component(self):
        """execute_step raises ValueError for unknown component."""
        engine = WorkflowEngine()
        step = {"name": "s1", "component": "ghost", "method": "run", "params": {}}
        with pytest.raises(ValueError, match="not found"):
            engine.execute_step(step)

    def test_execute_step_missing_component_field(self):
        """execute_step raises ValueError when component field is absent."""
        engine = WorkflowEngine()
        step = {"name": "s1", "method": "run", "params": {}}
        with pytest.raises(ValueError, match="missing required 'component'"):
            engine.execute_step(step)

    @pytest.mark.asyncio
    async def test_execute_step_async(self, engine_with_component):
        """execute_step_async works from an async context."""
        engine, comp = engine_with_component
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}
        result = await engine.execute_step_async(step)
        assert result == "hello"
        comp.greet.assert_called_once()


class TestWorkflowAgent:
    """Tests for WorkflowAgent."""

    def test_act_uses_public_execute_step(self, engine_with_component, monkeypatch):
        """act() calls the public execute_step, not the private _execute_step."""
        engine, _ = engine_with_component
        agent = WorkflowAgent(engine)
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}
        execute_step = MagicMock(return_value="hello")
        monkeypatch.setattr(engine, "execute_step", execute_step)

        result = agent.act(step)

        assert result == "hello"
        assert agent.last_result == "hello"
        execute_step.assert_called_once_with(step)

    def test_act_inside_running_loop(self, engine_with_component):
        """act() works when called from inside a running event loop."""
        engine, comp = engine_with_component
        agent = WorkflowAgent(engine)
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        async def _run():
            return agent.act(step)

        result = asyncio.run(_run())
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_act_async(self, engine_with_component):
        """act_async() executes a step without blocking."""
        engine, comp = engine_with_component
        agent = WorkflowAgent(engine)
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        result = await agent.act_async(step)

        assert result == "hello"
        assert agent.last_result == "hello"

    def test_act_async_uses_public_execute_step_async(self, engine_with_component, monkeypatch):
        """act_async() calls the public execute_step_async, not the private _execute_step_async."""
        engine, _ = engine_with_component
        agent = WorkflowAgent(engine)
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        async def _fake(step):
            return "hello"

        monkeypatch.setattr(engine, "execute_step_async", _fake)

        result = asyncio.run(agent.act_async(step))
        assert result == "hello"
        assert agent.last_result == "hello"

    def test_receive(self):
        """receive() stores the message."""
        engine = WorkflowEngine()
        agent = WorkflowAgent(engine)
        agent.receive("ping")
        assert agent.last_message == "ping"

    def test_get_status(self, engine_with_component):
        """get_status() returns name, last_result, last_message."""
        engine, comp = engine_with_component
        agent = WorkflowAgent(engine, name="my_agent")
        assert agent.get_status() == {
            "name": "my_agent",
            "last_result": None,
            "last_message": None,
        }

        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}
        agent.act(step)
        agent.receive("done")

        status = agent.get_status()
        assert status["name"] == "my_agent"
        assert status["last_result"] == "hello"
        assert status["last_message"] == "done"

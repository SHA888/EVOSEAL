"""Unit tests for WorkflowAgent and WorkflowEngine.execute_step."""

from __future__ import annotations

import asyncio
import threading
import time
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

    def test_execute_step_nested_offloaded_no_deadlock(self, engine_with_component):
        """Nested execute_step from within an offloaded worker avoids deadlock."""
        engine, comp = engine_with_component

        outer_step = {"name": "outer", "component": "greeter", "method": "greet", "params": {}}
        inner_step = {"name": "inner", "component": "greeter", "method": "greet", "params": {}}

        # composite_step calls execute_step again while already offloaded.
        def composite_step_handler(params):
            return engine.execute_step(inner_step)

        comp.composite.side_effect = lambda **kw: composite_step_handler(kw)
        outer_step["method"] = "composite"

        async def _run():
            return engine.execute_step(outer_step)

        # Must complete within a few seconds — a deadlock would hang.
        result = asyncio.run(_run())
        assert result == "hello"
        comp.composite.assert_called_once()
        comp.greet.assert_called_once()

    def test_execute_step_concurrent_offloaded_calls(self, engine_with_component):
        """Two concurrent offloaded execute_step calls are serialized by the lock."""
        import concurrent.futures as cfutures

        engine, comp = engine_with_component

        active_count = 0
        max_active = 0
        lock = threading.Lock()
        proceed = threading.Event()

        def tracked_greet(**kw):
            nonlocal active_count, max_active
            with lock:
                active_count += 1
                max_active = max(max_active, active_count)
            proceed.wait(timeout=5)
            with lock:
                active_count -= 1
            return "hello"

        comp.greet.side_effect = tracked_greet
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        async def _run_one():
            return engine.execute_step(step)

        async def _run_both():
            loop = asyncio.get_running_loop()
            with cfutures.ThreadPoolExecutor(max_workers=2) as pool:
                f1 = loop.run_in_executor(pool, lambda: asyncio.run(_run_one()))
                f2 = loop.run_in_executor(pool, lambda: asyncio.run(_run_one()))
                # Let both calls progress, then release the step body.
                await asyncio.sleep(0.2)
                proceed.set()
                return await asyncio.gather(f1, f2)

        results = asyncio.run(_run_both())
        assert all(r == "hello" for r in results)
        # If serialized, at most 1 step body runs at a time.
        assert max_active == 1, f"Expected max 1 concurrent step body, got {max_active}"

    def test_cleanup_prevents_new_submissions(self):
        """After cleanup(), execute_step raises RuntimeError."""
        engine = WorkflowEngine()
        engine.register_component("c", MagicMock())
        step = {"name": "s1", "component": "c", "method": "run", "params": {}}
        engine.cleanup()
        with pytest.raises(RuntimeError, match="cleanup"):
            engine.execute_step(step)

    def test_context_manager_cleans_up(self):
        """WorkflowEngine works as a context manager and cleans up on exit."""
        with WorkflowEngine() as engine:
            engine.register_component("c", MagicMock())
            step = {"name": "s1", "component": "c", "method": "run", "params": {}}
            result = engine.execute_step(step)
        # After exiting, cleanup has been called.
        with pytest.raises(RuntimeError, match="cleanup"):
            engine.execute_step(step)

    def test_cleanup_waits_for_in_flight_offloaded_call(self, engine_with_component):
        """cleanup() racing an in-flight offloaded execute_step() must not
        surface a raw "cannot schedule new futures after shutdown" error.

        cleanup() only flips _step_shutdown under _step_active_lock before
        shutting the executor down; that alone doesn't stop a call that
        already passed the shutdown check and is mid-submit inside the
        _step_lock critical section from racing the executor's shutdown.
        cleanup() must also acquire _step_lock so it waits for any such
        in-flight call to finish first.
        """
        engine, comp = engine_with_component
        entered = threading.Event()
        release = threading.Event()

        def slow_greet(**kw):
            entered.set()
            release.wait(timeout=5)
            return "hello"

        comp.greet.side_effect = slow_greet
        step = {"name": "s1", "component": "greeter", "method": "greet", "params": {}}

        async def _run():
            return engine.execute_step(step)

        result_box: dict[str, Any] = {}

        def _call_from_loop():
            result_box["result"] = asyncio.run(_run())

        caller = threading.Thread(target=_call_from_loop)
        caller.start()
        entered.wait(timeout=5)  # step body is running on the offloaded worker

        cleanup_thread = threading.Thread(target=engine.cleanup)
        cleanup_thread.start()
        time.sleep(0.1)  # give cleanup a chance to race the in-flight call
        release.set()

        caller.join(timeout=5)
        cleanup_thread.join(timeout=5)

        assert not caller.is_alive()
        assert not cleanup_thread.is_alive()
        assert result_box["result"] == "hello"


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

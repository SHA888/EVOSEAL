"""
Unit tests for AgenticSystem framework.
"""

from typing import Any

import pytest

from evoseal.agents.agentic_system import Agent, AgenticSystem


class DummyAgent:
    def __init__(self, name: str):
        self.name = name
        self.messages = []
        self.tasks = []
        self.status = {"ready": True}

    def act(self, observation: Any) -> Any:
        self.tasks.append(observation)
        return f"{self.name} did {observation}"

    def receive(self, message: Any) -> None:
        self.messages.append(message)

    def get_status(self) -> dict[str, Any]:
        return {**self.status, "messages": len(self.messages), "tasks": len(self.tasks)}


EXPECTED_AGENT_COUNT = 1


class RealAgent:
    def __init__(self):
        self.acted = []
        self.received = []

    def act(self, observation):
        self.acted.append(observation)
        return f"acted:{observation}"

    def receive(self, message):
        self.received.append(message)

    def get_status(self):
        return {"acted": len(self.acted), "received": len(self.received)}


def test_real_agent_integration():
    sys = AgenticSystem()
    agent = RealAgent()
    sys.create_agent("real", agent)
    assert sys.list_agents() == ["real"]
    sys.send_message("real", "msg")
    assert agent.received == ["msg"]
    res = sys.assign_task("real", "task1")
    assert res == "acted:task1"
    status = sys.get_agent_status("real")
    assert status["acted"] == 1 and status["received"] == 1
    sys.destroy_agent("real")
    assert "real" not in sys.list_agents()
    with pytest.raises(KeyError):
        sys.get_agent_status("real")
    with pytest.raises(ValueError):
        sys.create_agent("real", agent)
        sys.create_agent("real", agent)


def test_create_and_destroy_agent():
    sys = AgenticSystem()
    agent = DummyAgent("A")
    sys.create_agent("A", agent)
    expected_agent_count = 1
    assert len(sys.list_agents()) == expected_agent_count
    sys.destroy_agent("A")
    assert "A" not in sys.list_agents()
    with pytest.raises(KeyError):
        sys.destroy_agent("A")


def test_send_message_and_assign_task():
    sys = AgenticSystem()
    agent = DummyAgent("B")
    sys.create_agent("B", agent)
    sys.send_message("B", "hello")
    assert agent.messages == ["hello"]
    result = sys.assign_task("B", "compute")
    assert result == "B did compute"
    assert agent.tasks == ["compute"]
    with pytest.raises(KeyError):
        sys.send_message("C", "fail")
    with pytest.raises(KeyError):
        sys.assign_task("C", "fail")


def test_monitor_performance_and_status():
    sys = AgenticSystem()
    agent = DummyAgent("C")
    sys.create_agent("C", agent)
    sys.assign_task("C", "t1")
    sys.assign_task("C", "t2")
    perf = sys.monitor_performance("C")
    assert perf["C"] == ["C did t1", "C did t2"]
    status = sys.get_agent_status("C")
    assert status["ready"] is True
    assert status["messages"] == 0
    expected_task_count = 2
    assert status["tasks"] == expected_task_count
    all_perf = sys.monitor_performance()
    assert "C" in all_perf

"""
Unit tests for AgenticSystem framework.
"""

from typing import Any

import pytest

from evoseal.agentic_system import Agent, AgenticSystem


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

"""
Unit tests for AgenticSystem framework.
"""

from typing import Any

import pytest

from evoseal.agents.agentic_system import Agent, AgenticSystem


@pytest.fixture
def dummy_agent():
    """Fixture that creates a DummyAgent instance for testing."""

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

    return DummyAgent("test_agent")


@pytest.fixture
def real_agent():
    """Fixture that creates a RealAgent instance for testing."""

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

    return RealAgent()


def test_real_agent_integration(real_agent):
    """Test integration with a real agent implementation."""
    sys = AgenticSystem()
    sys.create_agent("test_agent", real_agent)

    # Test sending a message
    sys.send_message("test_agent", "Hello")
    assert len(real_agent.received) == 1
    assert real_agent.received[0] == "Hello"

    # Test assigning a task
    result = sys.assign_task("test_agent", "task1")
    assert result == "acted:task1"
    assert len(real_agent.acted) == 1
    assert real_agent.acted[0] == "task1"

    # Test getting status
    status = sys.get_agent_status("test_agent")
    assert status == {"acted": 1, "received": 1}


def test_create_and_destroy_agent(dummy_agent):
    """Test agent creation and destruction."""
    sys = AgenticSystem()

    # Test creating an agent
    sys.create_agent("test_agent", dummy_agent)
    assert "test_agent" in sys.agents
    assert sys.agents["test_agent"] == dummy_agent

    # Test destroying an agent
    sys.destroy_agent("test_agent")
    assert "test_agent" not in sys.agents


def test_send_message_and_assign_task(dummy_agent):
    """Test sending messages and assigning tasks to agents."""
    sys = AgenticSystem()
    sys.create_agent("test_agent", dummy_agent)

    # Test sending a message
    sys.send_message("test_agent", "Hello")
    assert len(dummy_agent.messages) == 1
    assert dummy_agent.messages[0] == "Hello"

    # Test assigning a task
    result = sys.assign_task("test_agent", "task1")
    assert result == "test_agent did task1"
    assert len(dummy_agent.tasks) == 1
    assert dummy_agent.tasks[0] == "task1"


def test_monitor_performance_and_status(dummy_agent):
    """Test monitoring agent performance and status."""
    sys = AgenticSystem()
    sys.create_agent("agent1", dummy_agent)
    agent2 = type(dummy_agent)("agent2")  # Create another instance of the same class

    sys.create_agent("agent2", agent2)

    # Perform some actions
    sys.send_message("agent1", "msg1")
    sys.assign_task("agent1", "task1")
    sys.send_message("agent2", "msg2")
    sys.assign_task("agent2", "task2")

    # Test getting status for one agent
    status1 = sys.get_agent_status("agent1")
    assert status1 == {"ready": True, "messages": 1, "tasks": 1}

    # Test getting status for each agent
    agent1_status = sys.get_agent_status("agent1")
    agent2_status = sys.get_agent_status("agent2")
    assert isinstance(agent1_status, dict)
    assert isinstance(agent2_status, dict)

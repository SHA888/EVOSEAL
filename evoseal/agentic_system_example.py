"""
Example usage of AgenticSystem with a simple agent.
"""

from typing import Any

from evoseal.agentic_system import Agent, AgenticSystem


class EchoAgent(Agent):
    def __init__(self, name: str):
        self.name = name
        self.last_message = None
        self.last_task = None

    def act(self, observation: Any) -> Any:
        self.last_task = observation
        return f"EchoAgent {self.name} acting on {observation}"

    def receive(self, message: Any) -> None:
        self.last_message = message

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "last_message": self.last_message,
            "last_task": self.last_task,
        }


def main() -> None:
    system = AgenticSystem()
    agent = EchoAgent("X")
    system.create_agent("X", agent)
    print("Agents:", system.list_agents())
    system.send_message("X", "Hello!")
    print("Status after message:", system.get_agent_status("X"))
    result = system.assign_task("X", "Test task")
    print("Task result:", result)
    print("Performance:", system.monitor_performance("X"))
    system.destroy_agent("X")
    print("Agents after destroy:", system.list_agents())


if __name__ == "__main__":
    main()

"""
Agent implementation that wraps the WorkflowEngine for integration with AgenticSystem.
"""

from typing import Any

from evoseal.agents.agentic_system import Agent
from evoseal.core.workflow import WorkflowEngine


class WorkflowAgent(Agent):
    def __init__(self, engine: WorkflowEngine, name: str = "workflow"):
        self.engine = engine
        self.name = name
        self.last_result = None
        self.last_message = None

    def act(self, observation: Any) -> Any:
        # Treat observation as a workflow step or config
        self.last_result = self.engine._execute_step(observation)
        return self.last_result

    def receive(self, message: Any) -> None:
        self.last_message = message

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "last_result": self.last_result,
            "last_message": self.last_message,
        }

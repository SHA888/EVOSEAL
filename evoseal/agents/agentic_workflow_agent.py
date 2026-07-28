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
        """Execute a workflow step.

        Delegates to the engine's public ``execute_step`` which is safe to
        call from within a running event loop.
        """
        self.last_result = self.engine.execute_step(observation)
        return self.last_result

    async def act_async(self, observation: Any) -> Any:
        """Execute a workflow step asynchronously.

        Use this variant when the caller is already in an async context.
        """
        self.last_result = await self.engine.execute_step_async(observation)
        return self.last_result

    def receive(self, message: Any) -> None:
        self.last_message = message

    def get_status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "last_result": self.last_result,
            "last_message": self.last_message,
        }

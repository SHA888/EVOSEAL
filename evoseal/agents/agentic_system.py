"""
AgenticSystem Framework for EVOSEAL
-----------------------------------
This module defines the AgenticSystem class, responsible for managing agent lifecycles, interactions, communication, task assignment, and performance monitoring.
The framework is designed to be extensible for different agent types and behaviors.
"""

import inspect
from typing import Any, Callable, Optional, Protocol, Union

from evoseal.utils.logging import Logger


class Agent(Protocol):
    """Protocol for agent interface. Agents must implement these methods."""

    def act(self, observation: Any) -> Any: ...
    def receive(self, message: Any) -> None: ...
    def get_status(self) -> dict[str, Any]: ...


class AgenticSystem:
    """
    Manages the lifecycle and interactions of agents in the system. Supports agent groups, logging, and async agents.
    """

    def __init__(self, logger: Optional[Logger] = None) -> None:
        self.agents: dict[str, Agent] = {}
        self.performance: dict[str, list[Any]] = {}
        self.groups: dict[str, list[str]] = {}  # group_name -> list of agent_ids
        self.logger = logger or Logger("AgenticSystem")

    def create_agent(self, agent_id: str, agent: Agent, group: Optional[str] = None) -> None:
        """Register a new agent. Optionally assign to a group."""
        if agent_id in self.agents:
            raise ValueError(f"Agent '{agent_id}' already exists.")
        self.agents[agent_id] = agent
        self.performance[agent_id] = []
        if group:
            self.groups.setdefault(group, []).append(agent_id)
        self.logger.info(f"Created agent '{agent_id}'" + (f" in group '{group}'" if group else ""))

    def destroy_agent(self, agent_id: str) -> None:
        """Remove an agent from the system."""
        if agent_id in self.agents:
            del self.agents[agent_id]
            del self.performance[agent_id]
            for members in self.groups.values():
                if agent_id in members:
                    members.remove(agent_id)
            self.logger.info(f"Destroyed agent '{agent_id}'")
        else:
            raise KeyError(f"Agent '{agent_id}' does not exist.")

    def send_message(self, agent_id: str, message: Any) -> None:
        """Send a message to a specific agent."""
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' does not exist.")
        self.agents[agent_id].receive(message)
        self.logger.info(f"Sent message to agent '{agent_id}': {message}")

    async def send_message_async(self, agent_id: str, message: Any) -> None:
        """Send a message to an agent, supporting async agents."""
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' does not exist.")
        agent = self.agents[agent_id]
        receive = getattr(agent, "receive", None)
        if receive is None:
            raise AttributeError(f"Agent '{agent_id}' does not have a receive method.")
        if inspect.iscoroutinefunction(receive):
            await receive(message)
        else:
            receive(message)
        self.logger.info(f"Sent async message to agent '{agent_id}': {message}")

    def assign_task(self, agent_id: str, task: Any) -> Any:
        """Assign a task to an agent and record the result."""
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' does not exist.")
        result = self.agents[agent_id].act(task)
        self.performance[agent_id].append(result)
        self.logger.info(f"Assigned task to agent '{agent_id}': {task} (result: {result})")
        return result

    async def assign_task_async(self, agent_id: str, task: Any) -> Any:
        """Assign a task to an agent, supporting async agents."""
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' does not exist.")
        agent = self.agents[agent_id]
        act = getattr(agent, "act", None)
        if act is None:
            raise AttributeError(f"Agent '{agent_id}' does not have an act method.")
        if inspect.iscoroutinefunction(act):
            result = await act(task)
        else:
            result = act(task)
        self.performance[agent_id].append(result)
        self.logger.info(f"Assigned async task to agent '{agent_id}': {task} (result: {result})")
        return result

    def monitor_performance(self, agent_id: Optional[str] = None) -> dict[str, list[Any]]:
        """Return performance history for one or all agents."""
        if agent_id:
            if agent_id not in self.performance:
                raise KeyError(f"Agent '{agent_id}' does not exist.")
            return {agent_id: self.performance[agent_id]}
        return dict(self.performance)

    def monitor_group_performance(self, group: str) -> dict[str, list[Any]]:
        """Return performance history for a group of agents."""
        if group not in self.groups:
            raise KeyError(f"Group '{group}' does not exist.")
        return {aid: self.performance[aid] for aid in self.groups[group] if aid in self.performance}

    def get_agent_status(self, agent_id: str) -> dict[str, Any]:
        """Get status of a specific agent."""
        if agent_id not in self.agents:
            raise KeyError(f"Agent '{agent_id}' does not exist.")
        return self.agents[agent_id].get_status()

    def get_group_status(self, group: str) -> dict[str, dict[str, Any]]:
        """Get status for all agents in a group."""
        if group not in self.groups:
            raise KeyError(f"Group '{group}' does not exist.")
        return {
            aid: self.agents[aid].get_status() for aid in self.groups[group] if aid in self.agents
        }

    def list_agents(self) -> list[str]:
        """List all agent IDs in the system."""
        return list(self.agents.keys())

    def create_group(self, group_name: str, agent_ids: Optional[list[str]] = None) -> None:
        """Create a new agent group with optional initial members."""
        if group_name in self.groups:
            raise ValueError(f"Group '{group_name}' already exists.")
        self.groups[group_name] = agent_ids or []
        self.logger.info(f"Created group '{group_name}' with agents: {self.groups[group_name]}")

    def assign_agent_to_group(self, agent_id: str, group_name: str) -> None:
        """Assign an existing agent to a group."""
        if group_name not in self.groups:
            self.groups[group_name] = []
        if agent_id not in self.groups[group_name]:
            self.groups[group_name].append(agent_id)
        self.logger.info(f"Assigned agent '{agent_id}' to group '{group_name}'")

    def list_groups(self) -> list[str]:
        """List all group names."""
        return list(self.groups.keys())

    def broadcast_message(self, group: str, message: Any) -> None:
        """Send a message to all agents in a group."""
        if group not in self.groups:
            raise KeyError(f"Group '{group}' does not exist.")
        for aid in self.groups[group]:
            if aid in self.agents:
                self.agents[aid].receive(message)
        self.logger.info(f"Broadcasted message to group '{group}': {message}")

    async def broadcast_message_async(self, group: str, message: Any) -> None:
        """Send a message to all agents in a group (async support)."""
        if group not in self.groups:
            raise KeyError(f"Group '{group}' does not exist.")
        for aid in self.groups[group]:
            if aid in self.agents:
                receive = getattr(self.agents[aid], "receive", None)
                if receive:
                    if inspect.iscoroutinefunction(receive):
                        await receive(message)
                    else:
                        receive(message)
        self.logger.info(f"Async broadcasted message to group '{group}': {message}")

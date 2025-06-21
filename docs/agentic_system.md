# AgenticSystem Framework (EVOSEAL)

## Overview
The `AgenticSystem` is a flexible, extensible framework for managing agent lifecycles, communication, task assignment, and performance monitoring in EVOSEAL. It supports agent groups, integrates with real EVOSEAL modules (like `WorkflowEngine`), and is ready for both synchronous and asynchronous agent implementations.

## Features
- **Lifecycle Management:** Create, destroy, and group agents.
- **Interaction:** Send messages and assign tasks (sync/async) to agents or groups.
- **Monitoring:** Track agent and group performance, query agent status.
- **Extensibility:** Any class implementing the `Agent` protocol can be managed.
- **Logging:** Uses the EVOSEAL logging system.

## Example: Integrate with WorkflowEngine
```python
from evoseal.agentic_system import AgenticSystem
from evoseal.agentic_workflow_agent import WorkflowAgent
from evoseal.core.workflow import WorkflowEngine

engine = WorkflowEngine()
system = AgenticSystem()
workflow_agent = WorkflowAgent(engine)
system.create_agent("wf1", workflow_agent, group="workflows")

step = {"name": "step1", "component": "dgm", "method": "run", "params": {}}
result = system.assign_task("wf1", step)
print("Workflow result:", result)
```

## Agent Groups
```python
system.create_group("teamA", ["wf1"])
system.broadcast_message("teamA", "Start round!")
```

## Async Support
```python
import asyncio
asyncio.run(system.assign_task_async("wf1", step))
```

## Custom Agent Example
```python
class MyAgent:
    def act(self, observation):
        return f"Processed {observation}"
    def receive(self, message):
        print(f"Got message: {message}")
    def get_status(self):
        return {"status": "ok"}

system.create_agent("a1", MyAgent())
```

## API Reference
- `create_agent(agent_id, agent, group=None)`
- `destroy_agent(agent_id)`
- `assign_task(agent_id, task)` / `assign_task_async(agent_id, task)`
- `send_message(agent_id, message)` / `send_message_async(agent_id, message)`
- `create_group(group_name, agent_ids=None)`
- `assign_agent_to_group(agent_id, group_name)`
- `broadcast_message(group, message)` / `broadcast_message_async(group, message)`
- `monitor_performance(agent_id=None)` / `monitor_group_performance(group)`
- `get_agent_status(agent_id)` / `get_group_status(group)`
- `list_agents()` / `list_groups()`

## Notes
- Agents can be any class implementing `act`, `receive`, and `get_status`.
- Async support is transparent: if an agent’s method is async, AgenticSystem will await it.
- Logging is integrated for all major operations.

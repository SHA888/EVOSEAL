"""
Simple Workflow Example

This example demonstrates how to use the WorkflowEngine to create and execute
a simple workflow with multiple steps and components.
"""

import logging

from evoseal.core.events import Event
from evoseal.core.workflow import WorkflowEngine, WorkflowStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Mock components for demonstration
class DataLoader:
    """Mock data loading component."""

    def load_data(self, source: str) -> dict:
        logger.info(f"Loading data from {source}")
        return {"data": [1, 2, 3, 4, 5], "source": source}


class DataProcessor:
    """Mock data processing component."""

    def process(self, data: dict) -> dict:
        logger.info(f"Processing {len(data['data'])} items")
        return {"processed_data": [x * 2 for x in data["data"]]}


class DataSaver:
    """Mock data saving component."""

    def save(self, data: dict, destination: str) -> bool:
        logger.info(f"Saving processed data to {destination}")
        logger.debug(f"Data to save: {data}")
        return True


def workflow_completed_callback(event: Event) -> None:
    """Example callback for workflow completion.

    Args:
        event: Event object containing workflow completion data
    """
    data = event.data
    logger.info(f"Workflow completed: {data['workflow']}")


def main() -> None:
    """Run the example workflow."""
    # Initialize the workflow engine
    engine = WorkflowEngine()

    # Register components
    engine.register_component("loader", DataLoader())
    engine.register_component("processor", DataProcessor())
    engine.register_component("saver", DataSaver())

    # Register event handlers
    engine.register_event_handler("workflow_completed", workflow_completed_callback)

    # Define the workflow
    from evoseal.core.workflow import StepConfig  # Import the StepConfig type

    workflow_steps: list[StepConfig] = [
        StepConfig(
            name="load_data",
            component="loader",
            method="load_data",
            params={"source": "example.csv"},
        ),
        StepConfig(
            name="process_data",
            component="processor",
            method="process",
            params={},
        ),
        StepConfig(
            name="save_results",
            component="saver",
            method="save",
            params={"destination": "output.json"},
        ),
    ]

    engine.define_workflow("data_processing", workflow_steps)

    # Execute the workflow
    print("Starting workflow execution...")
    success = engine.execute_workflow("data_processing")

    # Print final status
    status = engine.get_status()
    print(f"\nWorkflow completed: {success}")
    print(f"Final status: {status.name}")


if __name__ == "__main__":
    main()

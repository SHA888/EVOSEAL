#!/usr/bin/env python3
"""
Simple Enhanced Event System Demo

This example demonstrates the core event handling capabilities
without requiring the full pipeline setup.
"""

import asyncio
import logging
from typing import Any, Dict

from evoseal.core.events import (
    ComponentEvent,
    EnhancedEventBus,
    ErrorEvent,
    Event,
    EventBus,
    EventType,
    MetricsEvent,
    ProgressEvent,
    StateChangeEvent,
    create_component_event,
    create_error_event,
    create_event_filter,
    create_metrics_event,
    create_progress_event,
    create_state_change_event,
    enhanced_event_bus,
    event_bus,
    subscribe,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class SimpleEventDemo:
    """Demonstrates core event system capabilities."""

    def __init__(self):
        self.event_counts: Dict[str, int] = {}
        self.error_events: list[ErrorEvent] = []
        self.progress_events: list[ProgressEvent] = []

    async def run_demo(self):
        """Run the event system demonstration."""
        print("🚀 EVOSEAL Enhanced Event System Demo")
        print("=" * 50)

        # 1. Basic Event Publishing and Subscription
        await self.demo_basic_events()

        # 2. Specialized Event Types
        await self.demo_specialized_events()

        # 3. Event Filtering
        await self.demo_event_filtering()

        # 4. Enhanced EventBus Features
        await self.demo_enhanced_eventbus()

        print("\n✅ Event System Demo Complete!")
        print(f"📊 Total events processed: {sum(self.event_counts.values())}")
        print(f"❌ Error events: {len(self.error_events)}")
        print(f"📈 Progress events: {len(self.progress_events)}")

    async def demo_basic_events(self):
        """Demonstrate basic event publishing and subscription."""
        print("\n1️⃣ Basic Event Publishing and Subscription")
        print("-" * 40)

        # Subscribe to workflow events
        @subscribe(EventType.WORKFLOW_STARTED)
        async def on_workflow_started(event: Event):
            print(f"   🎯 Workflow started: {event.data}")
            self.event_counts["workflow_started"] = self.event_counts.get("workflow_started", 0) + 1

        @subscribe(EventType.WORKFLOW_COMPLETED)
        async def on_workflow_completed(event: Event):
            print(f"   ✅ Workflow completed: {event.data}")
            self.event_counts["workflow_completed"] = (
                self.event_counts.get("workflow_completed", 0) + 1
            )

        # Publish workflow events
        await event_bus.publish(
            Event(
                EventType.WORKFLOW_STARTED,
                "demo",
                {"workflow_id": "demo-001", "timestamp": "2024-01-01T10:00:00Z"},
            )
        )
        await event_bus.publish(
            Event(
                EventType.WORKFLOW_COMPLETED,
                "demo",
                {"workflow_id": "demo-001", "duration": 120.5},
            )
        )

        await asyncio.sleep(0.1)  # Allow events to process
        print(f"   📊 Events processed: {sum(self.event_counts.values())}")

    async def demo_specialized_events(self):
        """Demonstrate specialized event types."""
        print("\n2️⃣ Specialized Event Types")
        print("-" * 40)

        # Component Event
        component_event = create_component_event(
            event_type=EventType.COMPONENT_STARTED,
            component_type="DGM",
            component_id="dgm-001",
            operation="initialize",
            source="demo",
            version="1.0.0",
        )
        await event_bus.publish(component_event)
        print(
            f"   🔧 Component event: {component_event.component_type} {component_event.operation}"
        )

        # Error Event
        try:
            raise ValueError("This is a demo error")
        except Exception as e:
            error_event = create_error_event(
                error=e,
                source="demo",
                severity="warning",
                recoverable=True,
                context="demonstration",
            )
            await event_bus.publish(error_event)
            self.error_events.append(error_event)
            print(f"   ❌ Error event: {error_event.error_type} - {error_event.error_message}")

        # Progress Event
        for i in range(3):
            progress_event = create_progress_event(
                current=i + 1,
                total=3,
                stage="demo_processing",
                source="demo",
                message=f"Processing step {i + 1}",
                step=i + 1,
            )
            await event_bus.publish(progress_event)
            self.progress_events.append(progress_event)
            print(f"   📈 Progress: {progress_event.percentage:.1f}% - {progress_event.message}")

        # Metrics Event
        metrics_event = create_metrics_event(
            metrics={
                "cpu_usage": 45.2,
                "memory_usage": 78.5,
                "disk_io": 123.4,
                "network_io": 56.7,
            },
            source="demo",
            severity="info",
            threshold_exceeded=False,
        )
        await event_bus.publish(metrics_event)
        print(f"   📊 Metrics collected: {len(metrics_event.metrics)} metrics")

        # State Change Event
        state_event = create_state_change_event(
            old_state="initializing",
            new_state="running",
            entity_type="pipeline",
            entity_id="demo-pipeline",
            source="demo",
        )
        await event_bus.publish(state_event)
        print(f"   🔄 State change: {state_event.old_state} → {state_event.new_state}")

        await asyncio.sleep(0.1)

    async def demo_event_filtering(self):
        """Demonstrate event filtering capabilities."""
        print("\n3️⃣ Event Filtering")
        print("-" * 40)

        filtered_events = []

        # Create a filter for error events from specific sources
        error_filter = create_event_filter(
            event_types=[EventType.ERROR_OCCURRED, EventType.WARNING_ISSUED],
            sources=["demo", "test"],
            severity_levels=["error", "critical"],
        )

        # Subscribe with filter
        @subscribe(filter_fn=error_filter)
        async def on_filtered_error(event: Event):
            filtered_events.append(event)
            print(f"   🎯 Filtered error: {event.event_type} from {event.source}")

        # Publish various events (only some should be filtered)
        await event_bus.publish(create_error_event("Critical error", "demo", severity="critical"))
        await event_bus.publish(
            create_error_event("Warning", "demo", severity="warning")
        )  # Won't match filter
        await event_bus.publish(
            create_error_event("Error", "other", severity="error")
        )  # Won't match filter
        await event_bus.publish(
            Event(EventType.INFO_MESSAGE, "demo", {"message": "Info"})
        )  # Won't match filter

        await asyncio.sleep(0.1)
        print(f"   📊 Filtered events captured: {len(filtered_events)} out of 4 published")

    async def demo_enhanced_eventbus(self):
        """Demonstrate enhanced EventBus features."""
        print("\n4️⃣ Enhanced EventBus Features")
        print("-" * 40)

        # Enable logging and metrics on enhanced event bus
        enhanced_event_bus.enable_event_logging(max_history=50)

        # Publish batch events
        events = [
            Event(EventType.STEP_STARTED, "demo", {"step": "analysis"}),
            Event(EventType.STEP_STARTED, "demo", {"step": "generation"}),
            Event(EventType.STEP_COMPLETED, "demo", {"step": "analysis"}),
            Event(EventType.STEP_COMPLETED, "demo", {"step": "generation"}),
        ]

        published_events = await enhanced_event_bus.publish_batch(events)
        print(f"   📦 Batch published: {len(published_events)} events")

        # Get event history
        history = enhanced_event_bus.get_event_history(limit=5)
        print(f"   📚 Recent history: {len(history)} events")

        # Get event metrics
        metrics = enhanced_event_bus.get_event_metrics()
        print(f"   📊 Event metrics: {len(metrics)} event types tracked")

        # Show handler counts
        handler_count = enhanced_event_bus.get_handler_count(EventType.STEP_STARTED)
        print(f"   🎯 Handlers for STEP_STARTED: {handler_count}")

        all_types = enhanced_event_bus.get_all_event_types()
        print(f"   📋 Total event types with handlers: {len(all_types)}")

        # Show some metrics details
        print("\n   📊 Event Type Metrics:")
        for event_type, metrics_data in metrics.items():
            if isinstance(metrics_data, dict) and "count" in metrics_data:
                print(f"      {event_type}: {metrics_data['count']} events")

        # Show recent event history
        print(f"\n   📚 Recent Event History ({len(history)} events):")
        for i, event_dict in enumerate(history[:5], 1):
            event_type = event_dict.get("event_type", "unknown")
            source = event_dict.get("source", "unknown")
            print(f"      {i}. {event_type} from {source}")


async def main():
    """Run the enhanced event system demonstration."""
    demo = SimpleEventDemo()
    await demo.run_demo()


if __name__ == "__main__":
    asyncio.run(main())

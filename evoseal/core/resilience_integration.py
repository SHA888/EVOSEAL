"""Resilience integration module for EVOSEAL pipeline.

This module provides high-level integration of all resilience mechanisms
including error handling, recovery, logging, monitoring, and health checks.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from evoseal.core.error_recovery import error_recovery_manager
from evoseal.core.events import Event, EventBus, create_error_event
from evoseal.core.logging_system import get_logger, logging_manager
from evoseal.core.resilience import resilience_manager

logger = get_logger("resilience_integration")
event_bus = EventBus()


class ResilienceOrchestrator:
    """Orchestrates all resilience mechanisms for the EVOSEAL pipeline."""

    def __init__(self):
        self.is_initialized = False
        self.health_check_interval = 60  # seconds
        self.monitoring_tasks = []
        self.alert_handlers = []
        self.emergency_shutdown_enabled = True
        self.degraded_mode_active = False

    async def initialize(self):
        """Initialize the resilience orchestrator."""
        if self.is_initialized:
            return

        logger.info("Initializing resilience orchestrator")

        # Set up default error patterns and recovery strategies
        self._setup_default_error_patterns()

        # Register default alert handlers
        self._register_default_alert_handlers()

        # Start monitoring tasks
        await self._start_monitoring_tasks()

        self.is_initialized = True
        logger.info("Resilience orchestrator initialized successfully")

        # Publish initialization event
        await event_bus.publish(
            Event(
                event_type="RESILIENCE_ORCHESTRATOR_INITIALIZED",
                source="resilience_integration",
                data={
                    "timestamp": datetime.utcnow().isoformat(),
                    "health_check_interval": self.health_check_interval,
                    "emergency_shutdown_enabled": self.emergency_shutdown_enabled,
                },
            )
        )

    def _setup_default_error_patterns(self):
        """Set up default error patterns and recovery strategies."""
        from evoseal.core.error_recovery import ErrorPattern, RecoveryAction, RecoveryStrategy

        # Network-related errors
        error_recovery_manager.classifier.register_pattern(
            ErrorPattern(
                error_type="ConnectionError",
                recovery_strategy=RecoveryStrategy(
                    max_retries=5,
                    retry_delay=2.0,
                    backoff_multiplier=1.5,
                    recovery_actions=[RecoveryAction.RETRY, RecoveryAction.FALLBACK],
                ),
            )
        )

        # Timeout errors
        error_recovery_manager.classifier.register_pattern(
            ErrorPattern(
                error_type="TimeoutError",
                recovery_strategy=RecoveryStrategy(
                    max_retries=3,
                    retry_delay=5.0,
                    recovery_actions=[RecoveryAction.RETRY, RecoveryAction.RESTART_COMPONENT],
                ),
            )
        )

        # Memory errors
        error_recovery_manager.classifier.register_pattern(
            ErrorPattern(
                error_type="MemoryError",
                recovery_strategy=RecoveryStrategy(
                    max_retries=1,
                    retry_delay=10.0,
                    recovery_actions=[RecoveryAction.GRACEFUL_DEGRADATION],
                ),
            )
        )

        # Component-specific patterns
        error_recovery_manager.classifier.register_pattern(
            ErrorPattern(
                error_type="IntegrationError",
                component="dgm",
                recovery_strategy=RecoveryStrategy(
                    max_retries=3,
                    retry_delay=30.0,
                    recovery_actions=[RecoveryAction.RESTART_COMPONENT, RecoveryAction.FALLBACK],
                ),
            )
        )

        logger.info("Default error patterns configured")

    def _register_default_alert_handlers(self):
        """Register default alert handlers."""
        self.alert_handlers.extend(
            [
                self._handle_high_error_rate_alert,
                self._handle_component_failure_alert,
                self._handle_resource_exhaustion_alert,
                self._handle_circuit_breaker_alert,
            ]
        )

        logger.info(f"Registered {len(self.alert_handlers)} default alert handlers")

    async def _start_monitoring_tasks(self):
        """Start background monitoring tasks."""
        # Health monitoring task
        health_task = asyncio.create_task(self._health_monitoring_loop())
        self.monitoring_tasks.append(health_task)

        # Log analysis task
        log_analysis_task = asyncio.create_task(self._log_analysis_loop())
        self.monitoring_tasks.append(log_analysis_task)

        # Resilience status monitoring task
        resilience_task = asyncio.create_task(self._resilience_monitoring_loop())
        self.monitoring_tasks.append(resilience_task)

        logger.info(f"Started {len(self.monitoring_tasks)} monitoring tasks")

    async def _health_monitoring_loop(self):
        """Continuous health monitoring loop."""
        while True:
            try:
                await self._perform_health_checks()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Health monitoring error: {e}")
                await asyncio.sleep(self.health_check_interval)

    async def _log_analysis_loop(self):
        """Continuous log analysis loop."""
        while True:
            try:
                await self._analyze_logs()
                await asyncio.sleep(30)  # Check logs every 30 seconds
            except Exception as e:
                logger.error(f"Log analysis error: {e}")
                await asyncio.sleep(30)

    async def _resilience_monitoring_loop(self):
        """Monitor resilience mechanisms status."""
        while True:
            try:
                await self._monitor_resilience_status()
                await asyncio.sleep(45)  # Check every 45 seconds
            except Exception as e:
                logger.error(f"Resilience monitoring error: {e}")
                await asyncio.sleep(45)

    async def _perform_health_checks(self):
        """Perform comprehensive health checks."""
        health_status = {
            "timestamp": datetime.utcnow().isoformat(),
            "overall_health": "healthy",
            "components": {},
            "alerts": [],
        }

        # Check component health
        component_health = resilience_manager.health_monitor.metrics
        for component, metrics in component_health.items():
            health_status["components"][component] = {
                "status": metrics.health_status.value,
                "success_rate": metrics.success_rate,
                "error_rate": metrics.error_rate,
                "consecutive_failures": metrics.consecutive_failures,
            }

            # Check for alerts
            if metrics.health_status.value in ["unhealthy", "critical"]:
                health_status["alerts"].append(
                    {
                        "type": "component_unhealthy",
                        "component": component,
                        "status": metrics.health_status.value,
                        "consecutive_failures": metrics.consecutive_failures,
                    }
                )

        # Check circuit breaker status
        circuit_breakers = resilience_manager.circuit_breakers
        for name, cb in circuit_breakers.items():
            if cb.state.value == "open":
                health_status["alerts"].append(
                    {
                        "type": "circuit_breaker_open",
                        "component": name,
                        "failure_count": cb.failure_count,
                        "last_failure": (
                            cb.last_failure_time.isoformat() if cb.last_failure_time else None
                        ),
                    }
                )

        # Determine overall health
        if health_status["alerts"]:
            if any(
                alert["type"] == "component_unhealthy" and "critical" in alert.get("status", "")
                for alert in health_status["alerts"]
            ):
                health_status["overall_health"] = "critical"
            else:
                health_status["overall_health"] = "degraded"

        # Process alerts
        for alert in health_status["alerts"]:
            await self._process_alert(alert)

        # Publish health status event
        await event_bus.publish(
            Event(
                event_type="HEALTH_CHECK_COMPLETED",
                source="resilience_integration",
                data=health_status,
            )
        )

    async def _analyze_logs(self):
        """Analyze logs for patterns and alerts."""
        global_metrics = logging_manager.get_global_metrics()

        for logger_name, metrics in global_metrics.items():
            if not metrics:
                continue

            # Check for high error rates
            if metrics.get("error_rate", 0) > 0.1:  # 10% error rate
                await self._process_alert(
                    {
                        "type": "high_error_rate",
                        "component": logger_name,
                        "error_rate": metrics["error_rate"],
                        "total_logs": metrics["total_logs"],
                    }
                )

            # Check for critical log spikes
            critical_count = metrics.get("logs_by_level", {}).get("CRITICAL", 0)
            if critical_count > 5:
                await self._process_alert(
                    {
                        "type": "critical_log_spike",
                        "component": logger_name,
                        "critical_count": critical_count,
                    }
                )

    async def _monitor_resilience_status(self):
        """Monitor overall resilience status."""
        resilience_status = resilience_manager.get_resilience_status()
        recovery_stats = error_recovery_manager.get_recovery_statistics()

        # Check recovery success rates
        if recovery_stats and recovery_stats.get("success_rate", 1.0) < 0.5:
            await self._process_alert(
                {
                    "type": "low_recovery_success_rate",
                    "success_rate": recovery_stats["success_rate"],
                    "total_attempts": recovery_stats["total_attempts"],
                }
            )

        # Check for too many open circuit breakers
        open_circuits = sum(
            1
            for cb_status in resilience_status.get("circuit_breakers", {}).values()
            if cb_status.get("state") == "open"
        )

        if open_circuits > 2:  # More than 2 circuit breakers open
            await self._process_alert(
                {
                    "type": "multiple_circuit_breakers_open",
                    "open_count": open_circuits,
                    "circuit_breakers": resilience_status.get("circuit_breakers", {}),
                }
            )

    async def _process_alert(self, alert: Dict[str, Any]):
        """Process an alert through registered handlers."""
        alert["timestamp"] = datetime.utcnow().isoformat()

        logger.warning(f"Processing alert: {alert['type']}")

        # Run alert through handlers
        for handler in self.alert_handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Alert handler error: {e}")

        # Publish alert event
        await event_bus.publish(
            Event(event_type="RESILIENCE_ALERT", source="resilience_integration", data=alert)
        )

    async def _handle_high_error_rate_alert(self, alert: Dict[str, Any]):
        """Handle high error rate alerts."""
        if alert["type"] == "high_error_rate":
            component = alert.get("component", "unknown")
            error_rate = alert.get("error_rate", 0)

            logger.warning(f"High error rate detected for {component}: {error_rate:.2%}")

            # Consider enabling degraded mode
            if error_rate > 0.25:  # 25% error rate
                await self._enable_degraded_mode(f"High error rate: {error_rate:.2%}")

    async def _handle_component_failure_alert(self, alert: Dict[str, Any]):
        """Handle component failure alerts."""
        if alert["type"] == "component_unhealthy":
            component = alert.get("component", "unknown")
            status = alert.get("status", "unknown")

            logger.warning(f"Component {component} is {status}")

            # Try to restart critical components
            if status == "critical" and component in ["pipeline", "dgm", "openevolve"]:
                logger.info(f"Attempting to restart critical component: {component}")
                # Could trigger component restart here

    async def _handle_resource_exhaustion_alert(self, alert: Dict[str, Any]):
        """Handle resource exhaustion alerts."""
        if alert["type"] in ["high_memory_usage", "high_cpu_usage"]:
            logger.warning(f"Resource exhaustion detected: {alert['type']}")

            # Enable resource conservation mode
            await self._enable_resource_conservation()

    async def _handle_circuit_breaker_alert(self, alert: Dict[str, Any]):
        """Handle circuit breaker alerts."""
        if alert["type"] == "circuit_breaker_open":
            component = alert.get("component", "unknown")
            logger.warning(f"Circuit breaker open for {component}")

            # Try alternative components or degraded mode
            await self._handle_circuit_breaker_open(component)

    async def _enable_degraded_mode(self, reason: str):
        """Enable degraded mode operation."""
        if self.degraded_mode_active:
            return

        self.degraded_mode_active = True
        logger.warning(f"Enabling degraded mode: {reason}")

        await event_bus.publish(
            Event(
                event_type="DEGRADED_MODE_ENABLED",
                source="resilience_integration",
                data={
                    "reason": reason,
                    "timestamp": datetime.utcnow().isoformat(),
                },
            )
        )

    async def _enable_resource_conservation(self):
        """Enable resource conservation measures."""
        logger.info("Enabling resource conservation measures")

        # Could implement:
        # - Reduce parallel operations
        # - Increase delays between operations
        # - Disable non-essential features

        await event_bus.publish(
            Event(
                event_type="RESOURCE_CONSERVATION_ENABLED",
                source="resilience_integration",
                data={"timestamp": datetime.utcnow().isoformat()},
            )
        )

    async def _handle_circuit_breaker_open(self, component: str):
        """Handle open circuit breaker for a component."""
        logger.info(f"Handling open circuit breaker for {component}")

        # Could implement:
        # - Switch to backup component
        # - Enable fallback mode for that component
        # - Adjust workflow to skip that component

    async def get_comprehensive_status(self) -> Dict[str, Any]:
        """Get comprehensive resilience status."""
        return {
            "resilience_orchestrator": {
                "initialized": self.is_initialized,
                "degraded_mode_active": self.degraded_mode_active,
                "monitoring_tasks_count": len(self.monitoring_tasks),
                "alert_handlers_count": len(self.alert_handlers),
            },
            "resilience_manager": resilience_manager.get_resilience_status(),
            "error_recovery": error_recovery_manager.get_recovery_statistics(),
            "logging_metrics": logging_manager.get_global_metrics(),
        }

    async def shutdown(self):
        """Shutdown the resilience orchestrator."""
        logger.info("Shutting down resilience orchestrator")

        # Cancel monitoring tasks
        for task in self.monitoring_tasks:
            task.cancel()

        # Wait for tasks to complete
        if self.monitoring_tasks:
            await asyncio.gather(*self.monitoring_tasks, return_exceptions=True)

        self.is_initialized = False
        logger.info("Resilience orchestrator shutdown complete")


# Global resilience orchestrator instance
resilience_orchestrator = ResilienceOrchestrator()


async def initialize_resilience_system():
    """Initialize the complete resilience system."""
    logger.info("Initializing resilience system")

    # Start resilience manager monitoring
    await resilience_manager.start_monitoring()

    # Initialize orchestrator
    await resilience_orchestrator.initialize()

    logger.info("Resilience system initialized successfully")


def get_resilience_status() -> Dict[str, Any]:
    """Get comprehensive resilience status."""
    if not resilience_orchestrator.is_initialized:
        return {"error": "Resilience system not initialized"}

    return asyncio.run(resilience_orchestrator.get_comprehensive_status())


async def emergency_shutdown():
    """Trigger emergency shutdown of the resilience system."""
    logger.critical("Emergency shutdown triggered")
    await resilience_orchestrator.shutdown()

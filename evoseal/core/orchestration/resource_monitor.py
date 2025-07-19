"""
Resource Monitor for Workflow Orchestration

Monitors system resources and provides alerts and automatic actions based on thresholds.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

import psutil

from evoseal.core.events import create_error_event, event_bus

logger = logging.getLogger(__name__)


@dataclass
class ResourceThresholds:
    """Resource threshold configuration."""

    memory_warning: float = 0.7  # 70%
    memory_critical: float = 0.85  # 85%
    cpu_warning: float = 0.8  # 80%
    cpu_critical: float = 0.9  # 90%
    disk_warning: float = 0.8  # 80%
    disk_critical: float = 0.9  # 90%
    network_warning: float = 0.8  # 80% of bandwidth
    network_critical: float = 0.9  # 90% of bandwidth


@dataclass
class ResourceAlert:
    """Resource alert information."""

    alert_id: str
    timestamp: datetime
    resource_type: str
    severity: str  # warning, critical
    current_value: float
    threshold_value: float
    message: str
    resolved: bool = False
    resolved_at: Optional[datetime] = None


@dataclass
class ResourceSnapshot:
    """Snapshot of system resources at a point in time."""

    timestamp: datetime
    memory_percent: float
    memory_available_gb: float
    memory_used_gb: float
    cpu_percent: float
    cpu_count: int
    disk_percent: float
    disk_free_gb: float
    disk_used_gb: float
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    process_count: int = 0
    load_average: List[float] = field(default_factory=list)


class ResourceMonitor:
    """
    Monitors system resources and provides alerts and automatic actions.

    Tracks CPU, memory, disk, and network usage, providing configurable
    thresholds and automatic actions when limits are exceeded.
    """

    def __init__(
        self,
        thresholds: Optional[ResourceThresholds] = None,
        monitoring_interval: float = 30.0,
        history_retention_hours: int = 24,
        alert_cooldown_minutes: int = 5,
    ):
        """Initialize the resource monitor.

        Args:
            thresholds: Resource threshold configuration
            monitoring_interval: Interval between resource checks (seconds)
            history_retention_hours: How long to keep resource history
            alert_cooldown_minutes: Minimum time between similar alerts
        """
        self.thresholds = thresholds or ResourceThresholds()
        self.monitoring_interval = monitoring_interval
        self.history_retention_hours = history_retention_hours
        self.alert_cooldown_minutes = alert_cooldown_minutes

        # Monitoring state
        self._monitoring_active = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Resource history and alerts
        self.resource_history: List[ResourceSnapshot] = []
        self.active_alerts: Dict[str, ResourceAlert] = {}
        self.alert_history: List[ResourceAlert] = []

        # Alert callbacks
        self.alert_callbacks: List[Callable[[ResourceAlert], None]] = []

        # Network baseline (for calculating usage)
        self._network_baseline: Optional[Dict[str, float]] = None

        logger.info("ResourceMonitor initialized")

    async def start_monitoring(self) -> None:
        """Start resource monitoring."""
        if self._monitoring_active:
            logger.warning("Resource monitoring already active")
            return

        self._monitoring_active = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        # Initialize network baseline
        await self._initialize_network_baseline()

        logger.info("Resource monitoring started")

    async def stop_monitoring(self) -> None:
        """Stop resource monitoring."""
        if not self._monitoring_active:
            return

        self._monitoring_active = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        logger.info("Resource monitoring stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._monitoring_active:
            try:
                # Collect resource snapshot
                snapshot = await self._collect_resource_snapshot()

                # Store in history
                self.resource_history.append(snapshot)

                # Clean old history
                self._cleanup_history()

                # Check thresholds and generate alerts
                await self._check_thresholds(snapshot)

                # Wait for next interval
                await asyncio.sleep(self.monitoring_interval)

            except Exception as e:
                logger.error(f"Error in resource monitoring loop: {e}")
                await asyncio.sleep(self.monitoring_interval)

    async def _collect_resource_snapshot(self) -> ResourceSnapshot:
        """Collect current resource usage snapshot."""
        # Memory information
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_available_gb = memory.available / (1024**3)
        memory_used_gb = memory.used / (1024**3)

        # CPU information
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_count = psutil.cpu_count()

        # Disk information
        disk = psutil.disk_usage('/')
        disk_percent = (disk.used / disk.total) * 100
        disk_free_gb = disk.free / (1024**3)
        disk_used_gb = disk.used / (1024**3)

        # Network information
        network_sent_mb, network_recv_mb = await self._get_network_usage()

        # Process information
        process_count = len(psutil.pids())

        # Load average (Unix-like systems)
        load_average = []
        try:
            load_average = list(psutil.getloadavg())
        except AttributeError:
            # Windows doesn't have load average
            pass

        return ResourceSnapshot(
            timestamp=datetime.utcnow(),
            memory_percent=memory_percent,
            memory_available_gb=round(memory_available_gb, 2),
            memory_used_gb=round(memory_used_gb, 2),
            cpu_percent=cpu_percent,
            cpu_count=cpu_count,
            disk_percent=round(disk_percent, 1),
            disk_free_gb=round(disk_free_gb, 2),
            disk_used_gb=round(disk_used_gb, 2),
            network_sent_mb=round(network_sent_mb, 2),
            network_recv_mb=round(network_recv_mb, 2),
            process_count=process_count,
            load_average=load_average,
        )

    async def _initialize_network_baseline(self) -> None:
        """Initialize network usage baseline."""
        try:
            net_io = psutil.net_io_counters()
            self._network_baseline = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "timestamp": datetime.utcnow().timestamp(),
            }
        except Exception as e:
            logger.warning(f"Failed to initialize network baseline: {e}")
            self._network_baseline = None

    async def _get_network_usage(self) -> tuple[float, float]:
        """Get network usage since last measurement."""
        try:
            if not self._network_baseline:
                return 0.0, 0.0

            net_io = psutil.net_io_counters()
            current_time = datetime.utcnow().timestamp()

            # Calculate bytes transferred since baseline
            bytes_sent_diff = net_io.bytes_sent - self._network_baseline["bytes_sent"]
            bytes_recv_diff = net_io.bytes_recv - self._network_baseline["bytes_recv"]
            time_diff = current_time - self._network_baseline["timestamp"]

            # Convert to MB/s and then to MB for the interval
            if time_diff > 0:
                sent_mb = (bytes_sent_diff / (1024**2)) * (self.monitoring_interval / time_diff)
                recv_mb = (bytes_recv_diff / (1024**2)) * (self.monitoring_interval / time_diff)
            else:
                sent_mb = recv_mb = 0.0

            # Update baseline
            self._network_baseline = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "timestamp": current_time,
            }

            return sent_mb, recv_mb

        except Exception as e:
            logger.warning(f"Failed to get network usage: {e}")
            return 0.0, 0.0

    async def _check_thresholds(self, snapshot: ResourceSnapshot) -> None:
        """Check resource thresholds and generate alerts."""
        # Check memory thresholds
        await self._check_resource_threshold(
            "memory",
            snapshot.memory_percent / 100,
            self.thresholds.memory_warning,
            self.thresholds.memory_critical,
            f"Memory usage: {snapshot.memory_percent:.1f}%",
        )

        # Check CPU thresholds
        await self._check_resource_threshold(
            "cpu",
            snapshot.cpu_percent / 100,
            self.thresholds.cpu_warning,
            self.thresholds.cpu_critical,
            f"CPU usage: {snapshot.cpu_percent:.1f}%",
        )

        # Check disk thresholds
        await self._check_resource_threshold(
            "disk",
            snapshot.disk_percent / 100,
            self.thresholds.disk_warning,
            self.thresholds.disk_critical,
            f"Disk usage: {snapshot.disk_percent:.1f}%",
        )

    async def _check_resource_threshold(
        self,
        resource_type: str,
        current_value: float,
        warning_threshold: float,
        critical_threshold: float,
        message: str,
    ) -> None:
        """Check a specific resource threshold."""
        severity = None
        threshold_value = None

        if current_value >= critical_threshold:
            severity = "critical"
            threshold_value = critical_threshold
        elif current_value >= warning_threshold:
            severity = "warning"
            threshold_value = warning_threshold

        if severity:
            alert_key = f"{resource_type}_{severity}"

            # Check if we already have an active alert of this type
            if alert_key in self.active_alerts:
                # Check cooldown period
                last_alert = self.active_alerts[alert_key]
                cooldown_period = timedelta(minutes=self.alert_cooldown_minutes)
                if datetime.utcnow() - last_alert.timestamp < cooldown_period:
                    return  # Still in cooldown

            # Create new alert
            alert = ResourceAlert(
                alert_id=f"{alert_key}_{int(datetime.utcnow().timestamp())}",
                timestamp=datetime.utcnow(),
                resource_type=resource_type,
                severity=severity,
                current_value=current_value,
                threshold_value=threshold_value,
                message=message,
            )

            # Store alert
            self.active_alerts[alert_key] = alert
            self.alert_history.append(alert)

            # Trigger callbacks
            await self._trigger_alert_callbacks(alert)

            # Publish event
            await event_bus.publish(
                create_error_event(
                    error_type="resource_threshold_exceeded",
                    error_message=f"{severity.upper()}: {message}",
                    severity=severity,
                    recoverable=True,
                )
            )

            logger.warning(f"Resource alert: {severity.upper()} - {message}")

        else:
            # Check if we need to resolve any active alerts
            for alert_key in [f"{resource_type}_warning", f"{resource_type}_critical"]:
                if alert_key in self.active_alerts:
                    alert = self.active_alerts[alert_key]
                    if not alert.resolved:
                        alert.resolved = True
                        alert.resolved_at = datetime.utcnow()
                        logger.info(f"Resource alert resolved: {alert.message}")

    async def _trigger_alert_callbacks(self, alert: ResourceAlert) -> None:
        """Trigger registered alert callbacks."""
        for callback in self.alert_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(alert)
                else:
                    callback(alert)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")

    def _cleanup_history(self) -> None:
        """Clean up old resource history."""
        cutoff_time = datetime.utcnow() - timedelta(hours=self.history_retention_hours)

        # Clean resource history
        self.resource_history = [
            snapshot for snapshot in self.resource_history if snapshot.timestamp > cutoff_time
        ]

        # Clean alert history
        self.alert_history = [
            alert for alert in self.alert_history if alert.timestamp > cutoff_time
        ]

    def get_current_usage(self) -> Optional[ResourceSnapshot]:
        """Get the most recent resource snapshot."""
        return self.resource_history[-1] if self.resource_history else None

    def get_usage_history(
        self,
        hours: int = 1,
        resource_type: Optional[str] = None,
    ) -> List[ResourceSnapshot]:
        """Get resource usage history.

        Args:
            hours: Number of hours of history to return
            resource_type: Optional filter by resource type

        Returns:
            List of resource snapshots
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        history = [
            snapshot for snapshot in self.resource_history if snapshot.timestamp > cutoff_time
        ]

        return history

    def get_active_alerts(self) -> List[ResourceAlert]:
        """Get currently active alerts."""
        return [alert for alert in self.active_alerts.values() if not alert.resolved]

    def get_alert_history(self, hours: int = 24) -> List[ResourceAlert]:
        """Get alert history.

        Args:
            hours: Number of hours of history to return

        Returns:
            List of alerts
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)

        return [alert for alert in self.alert_history if alert.timestamp > cutoff_time]

    def add_alert_callback(self, callback: Callable[[ResourceAlert], None]) -> None:
        """Add an alert callback function.

        Args:
            callback: Function to call when alerts are triggered
        """
        self.alert_callbacks.append(callback)
        logger.info(f"Added alert callback: {callback.__name__}")

    def remove_alert_callback(self, callback: Callable[[ResourceAlert], None]) -> bool:
        """Remove an alert callback function.

        Args:
            callback: Function to remove

        Returns:
            True if callback was found and removed
        """
        try:
            self.alert_callbacks.remove(callback)
            logger.info(f"Removed alert callback: {callback.__name__}")
            return True
        except ValueError:
            logger.warning(f"Alert callback not found: {callback.__name__}")
            return False

    def get_resource_statistics(self) -> Dict[str, Any]:
        """Get resource usage statistics.

        Returns:
            Dictionary with resource statistics
        """
        if not self.resource_history:
            return {
                "monitoring_active": self._monitoring_active,
                "snapshots_collected": 0,
                "active_alerts": 0,
                "total_alerts": 0,
            }

        # Calculate statistics
        memory_values = [s.memory_percent for s in self.resource_history]
        cpu_values = [s.cpu_percent for s in self.resource_history]
        disk_values = [s.disk_percent for s in self.resource_history]

        return {
            "monitoring_active": self._monitoring_active,
            "snapshots_collected": len(self.resource_history),
            "active_alerts": len(self.get_active_alerts()),
            "total_alerts": len(self.alert_history),
            "memory_stats": {
                "current": memory_values[-1] if memory_values else 0,
                "average": sum(memory_values) / len(memory_values) if memory_values else 0,
                "max": max(memory_values) if memory_values else 0,
                "min": min(memory_values) if memory_values else 0,
            },
            "cpu_stats": {
                "current": cpu_values[-1] if cpu_values else 0,
                "average": sum(cpu_values) / len(cpu_values) if cpu_values else 0,
                "max": max(cpu_values) if cpu_values else 0,
                "min": min(cpu_values) if cpu_values else 0,
            },
            "disk_stats": {
                "current": disk_values[-1] if disk_values else 0,
                "average": sum(disk_values) / len(disk_values) if disk_values else 0,
                "max": max(disk_values) if disk_values else 0,
                "min": min(disk_values) if disk_values else 0,
            },
            "monitoring_interval": self.monitoring_interval,
            "history_retention_hours": self.history_retention_hours,
        }

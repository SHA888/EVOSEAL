"""Enhanced logging system for EVOSEAL pipeline with structured logging and monitoring.

This module provides comprehensive logging capabilities including structured logging,
log aggregation, real-time monitoring, alerting, and log analysis features.
"""

import json
import logging
import logging.handlers
import os
import sys
import threading
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from rich.console import Console
from rich.logging import RichHandler
from rich.table import Table

from evoseal.core.events import Event, EventBus, create_error_event

# Initialize event bus
event_bus = EventBus()


class LogLevel(Enum):
    """Log levels with numeric values."""

    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogCategory(Enum):
    """Categories for different types of logs."""

    PIPELINE = "pipeline"
    COMPONENT = "component"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"
    BUSINESS = "business"
    SYSTEM = "system"
    ERROR = "error"
    AUDIT = "audit"


@dataclass
class LogEntry:
    """Structured log entry."""

    timestamp: datetime
    level: LogLevel
    category: LogCategory
    component: str
    message: str
    context: Dict[str, Any] = field(default_factory=dict)
    correlation_id: Optional[str] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    trace_id: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


@dataclass
class LogMetrics:
    """Metrics for log analysis."""

    total_logs: int = 0
    logs_by_level: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    logs_by_component: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    logs_by_category: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    error_rate: float = 0.0
    warning_rate: float = 0.0
    avg_logs_per_minute: float = 0.0
    last_error: Optional[datetime] = None
    last_critical: Optional[datetime] = None


class LogAggregator:
    """Aggregates and analyzes log entries."""

    def __init__(self, window_size: int = 1000, analysis_interval: int = 60):
        self.window_size = window_size
        self.analysis_interval = analysis_interval
        self.log_buffer: deque = deque(maxlen=window_size)
        self.metrics = LogMetrics()
        self.alert_thresholds = {
            "error_rate": 0.1,  # 10% error rate
            "critical_count": 5,  # 5 critical logs in window
            "logs_per_minute": 1000,  # 1000 logs per minute
        }
        self.last_analysis = datetime.utcnow()
        self._lock = threading.Lock()

    def add_log_entry(self, entry: LogEntry):
        """Add a log entry to the buffer."""
        with self._lock:
            self.log_buffer.append(entry)
            self._update_metrics()

    def _update_metrics(self):
        """Update metrics based on current buffer."""
        if not self.log_buffer:
            return

        # Basic counts
        self.metrics.total_logs = len(self.log_buffer)

        # Reset counters
        self.metrics.logs_by_level.clear()
        self.metrics.logs_by_component.clear()
        self.metrics.logs_by_category.clear()

        # Analyze buffer
        error_count = 0
        warning_count = 0

        for entry in self.log_buffer:
            # Count by level
            self.metrics.logs_by_level[entry.level.name] += 1

            # Count by component
            self.metrics.logs_by_component[entry.component] += 1

            # Count by category
            self.metrics.logs_by_category[entry.category.value] += 1

            # Track errors and warnings
            if entry.level == LogLevel.ERROR:
                error_count += 1
                self.metrics.last_error = entry.timestamp
            elif entry.level == LogLevel.CRITICAL:
                error_count += 1
                self.metrics.last_critical = entry.timestamp
            elif entry.level == LogLevel.WARNING:
                warning_count += 1

        # Calculate rates
        if self.metrics.total_logs > 0:
            self.metrics.error_rate = error_count / self.metrics.total_logs
            self.metrics.warning_rate = warning_count / self.metrics.total_logs

        # Calculate logs per minute
        if len(self.log_buffer) >= 2:
            time_span = (
                self.log_buffer[-1].timestamp - self.log_buffer[0].timestamp
            ).total_seconds()
            if time_span > 0:
                self.metrics.avg_logs_per_minute = (len(self.log_buffer) / time_span) * 60

    def get_metrics(self) -> LogMetrics:
        """Get current log metrics."""
        with self._lock:
            return self.metrics

    def get_recent_logs(
        self,
        count: int = 50,
        level: Optional[LogLevel] = None,
        component: Optional[str] = None,
        category: Optional[LogCategory] = None,
    ) -> List[LogEntry]:
        """Get recent log entries with optional filtering."""
        with self._lock:
            logs = list(self.log_buffer)

            # Apply filters
            if level:
                logs = [log for log in logs if log.level == level]
            if component:
                logs = [log for log in logs if log.component == component]
            if category:
                logs = [log for log in logs if log.category == category]

            # Return most recent
            return logs[-count:] if logs else []

    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check for alert conditions."""
        alerts = []

        # Error rate alert
        if self.metrics.error_rate > self.alert_thresholds["error_rate"]:
            alerts.append(
                {
                    "type": "high_error_rate",
                    "message": f"Error rate {self.metrics.error_rate:.2%} exceeds threshold",
                    "severity": "warning",
                    "metrics": {"error_rate": self.metrics.error_rate},
                }
            )

        # Critical log count alert
        critical_count = self.metrics.logs_by_level.get("CRITICAL", 0)
        if critical_count >= self.alert_thresholds["critical_count"]:
            alerts.append(
                {
                    "type": "high_critical_count",
                    "message": f"Critical log count {critical_count} exceeds threshold",
                    "severity": "critical",
                    "metrics": {"critical_count": critical_count},
                }
            )

        # High log volume alert
        if self.metrics.avg_logs_per_minute > self.alert_thresholds["logs_per_minute"]:
            alerts.append(
                {
                    "type": "high_log_volume",
                    "message": f"Log volume {self.metrics.avg_logs_per_minute:.0f}/min exceeds threshold",
                    "severity": "warning",
                    "metrics": {"logs_per_minute": self.metrics.avg_logs_per_minute},
                }
            )

        return alerts


class StructuredLogger:
    """Structured logger with rich formatting and monitoring."""

    def __init__(
        self,
        name: str,
        log_dir: Optional[Path] = None,
        enable_console: bool = True,
        enable_file: bool = True,
        enable_json: bool = True,
        enable_monitoring: bool = True,
    ):
        self.name = name
        self.log_dir = log_dir or Path("logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize aggregator if monitoring enabled
        self.aggregator = LogAggregator() if enable_monitoring else None

        # Configure structlog
        self._configure_structlog()

        # Set up loggers
        self.logger = structlog.get_logger(name)
        self.python_logger = logging.getLogger(name)

        # Configure handlers
        if enable_console:
            self._setup_console_handler()
        if enable_file:
            self._setup_file_handler()
        if enable_json:
            self._setup_json_handler()

        # Start monitoring if enabled
        if enable_monitoring:
            self._start_monitoring()

    def _configure_structlog(self):
        """Configure structlog processors."""
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    def _setup_console_handler(self):
        """Set up rich console handler."""
        console = Console()
        handler = RichHandler(
            console=console,
            show_time=True,
            show_path=True,
            enable_link_path=True,
            markup=True,
        )
        handler.setLevel(logging.INFO)
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        self.python_logger.addHandler(handler)

    def _setup_file_handler(self):
        """Set up rotating file handler."""
        log_file = self.log_dir / f"{self.name}.log"
        handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"
        )
        handler.setFormatter(formatter)
        self.python_logger.addHandler(handler)

    def _setup_json_handler(self):
        """Set up JSON file handler for structured logs."""
        json_file = self.log_dir / f"{self.name}.json"
        handler = logging.handlers.RotatingFileHandler(
            json_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        handler.setLevel(logging.DEBUG)

        class JsonFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                    "level": record.levelname,
                    "logger": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }

                # Add exception info if present
                if record.exc_info:
                    log_entry["exception"] = self.formatException(record.exc_info)

                # Add extra fields
                for key, value in record.__dict__.items():
                    if key not in [
                        "name",
                        "msg",
                        "args",
                        "levelname",
                        "levelno",
                        "pathname",
                        "filename",
                        "module",
                        "lineno",
                        "funcName",
                        "created",
                        "msecs",
                        "relativeCreated",
                        "thread",
                        "threadName",
                        "processName",
                        "process",
                        "exc_info",
                        "exc_text",
                        "stack_info",
                    ]:
                        log_entry[key] = value

                return json.dumps(log_entry)

        handler.setFormatter(JsonFormatter())
        self.python_logger.addHandler(handler)

    def _start_monitoring(self):
        """Start log monitoring in background."""

        def monitor_loop():
            while True:
                try:
                    if self.aggregator:
                        alerts = self.aggregator.check_alerts()
                        for alert in alerts:
                            # Publish alert event
                            event_bus.publish(
                                Event(
                                    event_type="LOG_ALERT",
                                    source="logging_system",
                                    data=alert,
                                )
                            )
                    time.sleep(60)  # Check every minute
                except Exception as e:
                    self.python_logger.error(f"Log monitoring error: {e}")
                    time.sleep(60)

        thread = threading.Thread(target=monitor_loop, daemon=True)
        thread.start()

    def _create_log_entry(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        component: Optional[str] = None,
        **context,
    ) -> LogEntry:
        """Create a structured log entry."""
        return LogEntry(
            timestamp=datetime.utcnow(),
            level=level,
            category=category,
            component=component or self.name,
            message=message,
            context=context,
            correlation_id=context.get("correlation_id"),
            user_id=context.get("user_id"),
            session_id=context.get("session_id"),
            trace_id=context.get("trace_id"),
            error_details=context.get("error_details"),
        )

    def log(
        self,
        level: LogLevel,
        message: str,
        category: LogCategory = LogCategory.SYSTEM,
        component: Optional[str] = None,
        **context,
    ):
        """Log a message with structured data."""
        # Create structured log entry
        entry = self._create_log_entry(level, message, category, component, **context)

        # Add to aggregator if monitoring enabled
        if self.aggregator:
            self.aggregator.add_log_entry(entry)

        # Log using structlog
        log_method = getattr(self.logger, level.name.lower())
        log_method(
            message,
            category=category.value,
            component=component or self.name,
            **context,
        )

    def debug(self, message: str, **context):
        """Log debug message."""
        self.log(LogLevel.DEBUG, message, **context)

    def info(self, message: str, **context):
        """Log info message."""
        self.log(LogLevel.INFO, message, **context)

    def warning(self, message: str, **context):
        """Log warning message."""
        self.log(LogLevel.WARNING, message, **context)

    def error(self, message: str, **context):
        """Log error message."""
        self.log(LogLevel.ERROR, message, **context)

    def critical(self, message: str, **context):
        """Log critical message."""
        self.log(LogLevel.CRITICAL, message, **context)

    def log_pipeline_stage(
        self,
        stage: str,
        status: str,
        iteration: Optional[int] = None,
        **context,
    ):
        """Log pipeline stage information."""
        message = f"Pipeline stage {stage}: {status}"
        if iteration:
            message += f" (iteration {iteration})"

        self.log(
            LogLevel.INFO,
            message,
            category=LogCategory.PIPELINE,
            stage=stage,
            status=status,
            iteration=iteration,
            **context,
        )

    def log_component_operation(
        self,
        component: str,
        operation: str,
        status: str,
        duration: Optional[float] = None,
        **context,
    ):
        """Log component operation."""
        message = f"Component {component} {operation}: {status}"
        if duration:
            message += f" (took {duration:.2f}s)"

        self.log(
            LogLevel.INFO,
            message,
            category=LogCategory.COMPONENT,
            component=component,
            operation=operation,
            status=status,
            duration=duration,
            **context,
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: Union[int, float],
        unit: str = "",
        component: Optional[str] = None,
        **context,
    ):
        """Log performance metric."""
        message = f"Performance metric {metric_name}: {value}{unit}"

        self.log(
            LogLevel.INFO,
            message,
            category=LogCategory.PERFORMANCE,
            component=component,
            metric_name=metric_name,
            metric_value=value,
            metric_unit=unit,
            **context,
        )

    def log_error_with_context(
        self,
        error: Exception,
        component: Optional[str] = None,
        operation: Optional[str] = None,
        **context,
    ):
        """Log error with full context."""
        error_details = {
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "error_args": error.args,
        }

        # Add stack trace if available
        import traceback

        error_details["stack_trace"] = traceback.format_exc()

        self.log(
            LogLevel.ERROR,
            f"Error in {component or 'unknown'}: {str(error)}",
            category=LogCategory.ERROR,
            component=component,
            operation=operation,
            error_details=error_details,
            **context,
        )

    def get_metrics(self) -> Optional[LogMetrics]:
        """Get logging metrics."""
        return self.aggregator.get_metrics() if self.aggregator else None

    def get_recent_logs(self, count: int = 50, **filters) -> List[LogEntry]:
        """Get recent log entries."""
        if not self.aggregator:
            return []
        return self.aggregator.get_recent_logs(count, **filters)

    def display_log_summary(self) -> Table:
        """Display log summary as a rich table."""
        if not self.aggregator:
            return Table()

        metrics = self.aggregator.get_metrics()

        table = Table(title=f"Log Summary - {self.name}")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")

        table.add_row("Total Logs", str(metrics.total_logs))
        table.add_row("Error Rate", f"{metrics.error_rate:.2%}")
        table.add_row("Warning Rate", f"{metrics.warning_rate:.2%}")
        table.add_row("Logs/Minute", f"{metrics.avg_logs_per_minute:.1f}")

        if metrics.last_error:
            table.add_row("Last Error", metrics.last_error.strftime("%Y-%m-%d %H:%M:%S"))

        if metrics.last_critical:
            table.add_row("Last Critical", metrics.last_critical.strftime("%Y-%m-%d %H:%M:%S"))

        return table


class LoggingManager:
    """Centralized logging manager for the entire pipeline."""

    def __init__(self, base_log_dir: Optional[Path] = None):
        self.base_log_dir = base_log_dir or Path("logs")
        self.loggers: Dict[str, StructuredLogger] = {}
        self.global_aggregator = LogAggregator(window_size=5000)

        # Create main pipeline logger
        self.pipeline_logger = self.get_logger("pipeline")

    def get_logger(
        self,
        name: str,
        enable_monitoring: bool = True,
    ) -> StructuredLogger:
        """Get or create a logger for a component."""
        if name not in self.loggers:
            log_dir = self.base_log_dir / name
            self.loggers[name] = StructuredLogger(
                name=name,
                log_dir=log_dir,
                enable_monitoring=enable_monitoring,
            )
        return self.loggers[name]

    def get_global_metrics(self) -> Dict[str, Any]:
        """Get global logging metrics across all loggers."""
        all_metrics = {}

        for name, logger in self.loggers.items():
            metrics = logger.get_metrics()
            if metrics:
                all_metrics[name] = asdict(metrics)

        return all_metrics

    def shutdown(self):
        """Shutdown all loggers."""
        for logger in self.loggers.values():
            for handler in logger.python_logger.handlers:
                handler.close()


# Global logging manager instance
logging_manager = LoggingManager()


def get_logger(name: str) -> StructuredLogger:
    """Get a logger instance."""
    return logging_manager.get_logger(name)

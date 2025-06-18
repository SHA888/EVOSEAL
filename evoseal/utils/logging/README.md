# EVOSEAL Logging Module

This module provides a comprehensive logging solution for the EVOSEAL project, featuring structured logging, context tracking, and performance monitoring.

## Features

- **Structured Logging**: JSON-formatted logs for easy parsing and analysis
- **Context Tracking**: Track requests and operations across services
- **Performance Monitoring**: Built-in support for performance metrics
- **Error Handling**: Enhanced error tracking with stack traces
- **Flexible Configuration**: YAML-based configuration
- **Request Correlation**: Track requests across services with unique IDs

## Installation

The logging module is included with the EVOSEAL package. No additional installation is required.

## Configuration

Logging is configured via the `config/logging.yaml` file. The default configuration includes:

- Console output with human-readable format
- File output with JSON format
- Separate error log file
- Performance metrics logging
- Log rotation (10MB per file, 5 backups)

## Basic Usage

```python
from evoseal.utils.logging import setup_logging

# Initialize logging
logger = setup_logging()

# Log messages at different levels
logger.debug("Debug message")
logger.info("Informational message")
logger.warning("Warning message")
logger.error("Error message")
logger.critical("Critical message")

# Log exceptions with stack traces
try:
    1 / 0
except Exception as e:
    logger.exception("An error occurred")
```

## Advanced Features

### Using the LoggingMixin

```python
from evoseal.utils.logging import LoggingMixin

class MyService(LoggingMixin):
    def __init__(self):
        super().__init__()
        self.logger.info("Service initialized")

    def process(self, data):
        self.logger.info("Processing data", extra={"data_size": len(data)})
        self.log_performance("processing_time_ms", 42.5, operation="data_processing")
```

### Request Context and Correlation

```python
from evoseal.utils.logging import with_request_id, setup_logging

logger = setup_logging()

@with_request_id(logger)
def process_request(request_data):
    logger.info("Processing request", extra={"user_id": request_data.user_id})
    # Request processing logic...
    return {"status": "success"}
```

### Performance Monitoring

```python
from evoseal.utils.logging import log_execution_time

@log_execution_time(logger)
def expensive_operation():
    # Time-consuming operation
    import time
    time.sleep(1)
    return "result"
```

## Best Practices

1. **Use Structured Logging**: Include structured data in the `extra` parameter
2. **Log at Appropriate Levels**:
   - DEBUG: Detailed information for debugging
   - INFO: General operational information
   - WARNING: Potential issues
   - ERROR: Non-fatal errors
   - CRITICAL: Fatal errors
3. **Include Context**: Add request IDs, user IDs, and other relevant context
4. **Monitor Performance**: Use performance monitoring for critical operations
5. **Handle Exceptions**: Always log exceptions with full stack traces

## Log Analysis

Logs are stored in JSON format for easy analysis. You can use tools like:

- **ELK Stack** (Elasticsearch, Logstash, Kibana)
- **Graylog**
- **AWS CloudWatch Logs**
- **Google Cloud Logging**

## License

This module is part of the EVOSEAL project and is licensed under the same terms as the main project.

# Error Handling Framework

This document provides a comprehensive guide to the EVOSEAL error handling framework, which is designed to provide consistent error handling across the application.

## Table of Contents

1. [Overview](#overview)
2. [Error Types](#error-types)
   - [BaseError](#baseerror)
   - [ValidationError](#validationerror)
   - [ConfigurationError](#configurationerror)
   - [IntegrationError](#integrationerror)
   - [RetryableError](#retryableerror)
3. [Error Handling Utilities](#error-handling-utilities)
   - [log_error](#log_error)
   - [handle_errors](#handle_errors-context-manager)
   - [error_handler](#error_handler-decorator)
   - [retry_on_error](#retry_on_error-decorator)
   - [error_boundary](#error_boundary-decorator)
   - [create_error_response](#create_error_response)
4. [Best Practices](#best-practices)
5. [Examples](#examples)

## Overview

The error handling framework is built around the `BaseError` class and its subclasses, which provide a consistent way to handle and report errors throughout the application. The framework includes utilities for logging, error handling, and error response generation.

## Error Types

### BaseError

The base class for all custom exceptions in the application. Provides common functionality like error codes, categories, and context.

```python
raise BaseError(
    message="Something went wrong",
    code="CUSTOM_ERROR",
    category=ErrorCategory.RUNTIME,
    severity=ErrorSeverity.ERROR,
    context=ErrorContext(
        component="auth",
        operation="verify_token",
        details={"token": "..."},
    ),
)
```

### ValidationError

Raised when input validation fails.

```python
raise ValidationError(
    message="Invalid email format",
    field="email",
    value="invalid-email",
    details={"format": "must be a valid email address"},
)
```

### ConfigurationError

Raised when there is a configuration issue.

```python
raise ConfigurationError(
    message="Missing required configuration",
    config_key="database.url",
    details={"environment_variable": "DATABASE_URL"},
)
```

### IntegrationError

Raised when there is an error integrating with an external system.

```python
raise IntegrationError(
    message="Failed to process payment",
    system="payment_gateway",
    details={
        "status_code": 500,
        "response": {...},
    },
)
```

### RetryableError

Raised when an operation fails but can be retried.

```python
raise RetryableError(
    message="Temporary database connection failure",
    max_retries=3,
    retry_delay=1.0,
    details={"attempt": 1, "max_attempts": 3},
)
```

## Error Handling Utilities

### log_error

Log an error with contextual information.

```python
try:
    # Code that might fail
    result = 1 / 0
except Exception as e:
    log_error(
        e,
        message="Division by zero error occurred",
        extra={"numerator": 1, "denominator": 0},
    )
    raise
```

### handle_errors (context manager)

Context manager for handling errors with consistent logging.

```python
with handle_errors("auth", "verify_token", logger=logger):
    # Code that might raise an exception
    verify_token(token)
```

### error_handler (decorator)

Decorator to handle specific exceptions in a consistent way.

```python
@error_handler(ValueError, logger=logger)
def parse_number(value: str) -> int:
    return int(value)
```

### retry_on_error (decorator)

Retry a function when specified exceptions are raised.

```python
@retry_on_error(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(ConnectionError, TimeoutError),
    logger=logger,
)
def fetch_data(url: str) -> dict:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json()
```

### error_boundary (decorator)

Catch and log exceptions, returning a default value.

```python
@error_boundary(default=[], logger=logger)
def get_user_preferences(user_id: str) -> list[dict]:
    # This might raise an exception
    return fetch_preferences_from_db(user_id)
```

### create_error_response

Create a standardized error response dictionary.

```python
try:
    result = process_request(request)
    return jsonify(result), 200
except BaseError as e:
    response = create_error_response(e, status_code=400)
    return jsonify(response), 400
except Exception as e:
    response = create_error_response(
        e, 
        status_code=500,
        include_traceback=app.debug,
    )
    return jsonify(response), 500
```

## Best Practices

1. **Use Specific Error Types**: Always use the most specific error type that matches the error condition.

2. **Provide Context**: Include relevant context in error messages and details to help with debugging.

3. **Handle Errors at the Right Level**: Handle errors at the appropriate level of abstraction. Lower-level functions should raise errors, while higher-level functions should handle or transform them.

4. **Log Errors**: Always log errors with sufficient context to diagnose issues in production.

5. **Use Retry Logic for Transient Failures**: Use the `retry_on_error` decorator for operations that might fail temporarily (e.g., network requests).

6. **Document Error Conditions**: Document the exceptions that functions can raise in their docstrings.

## Examples

### Example 1: Basic Error Handling

```python
def get_user(user_id: str) -> dict:
    if not user_id:
        raise ValidationError("User ID is required", field="user_id")
    
    try:
        user = user_repository.get(user_id)
        if not user:
            raise BaseError(
                f"User not found: {user_id}",
                code="USER_NOT_FOUND",
                category=ErrorCategory.RESOURCE,
                severity=ErrorSeverity.WARNING,
            )
        return user
    except DatabaseError as e:
        raise IntegrationError(
            "Failed to fetch user from database",
            system="database",
            details={"user_id": user_id},
            cause=e,
        ) from e
```

### Example 2: Using error_handler

```python
@error_handler(
    ValidationError, 
    status_code=400,
    logger=logger
)
@error_handler(
    DatabaseError,
    status_code=503,
    logger=logger
)
@error_handler(
    Exception,
    status_code=500,
    logger=logger
)
def get_user_handler(user_id: str) -> tuple[dict, int]:
    user = get_user(user_id)
    return {"user": user}, 200
```

### Example 3: Using retry_on_error

```python
@retry_on_error(
    max_retries=3,
    delay=1.0,
    backoff=2.0,
    exceptions=(requests.RequestException,),
    logger=logger,
)
def call_external_api(url: str, data: dict) -> dict:
    response = requests.post(
        url,
        json=data,
        timeout=10,
        headers={"Authorization": f"Bearer {get_api_token()}"},
    )
    response.raise_for_status()
    return response.json()
```

### Example 4: Using error_boundary

```python
@error_boundary(default=None, logger=logger)
def get_cached_value(key: str) -> Optional[Any]:
    """Get a value from the cache, returning None on any error."""
    return cache_client.get(key)
```

---

This documentation provides a comprehensive guide to the error handling framework. For more details, refer to the source code and unit tests.

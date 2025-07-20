"""
SEAL (Self-Adapting Language Models) System Exceptions

This module defines custom exceptions for the SEAL system.
"""


class SEALError(Exception):
    """Base exception class for SEAL system errors."""

    pass


class RetryableError(SEALError):
    """Raised when an operation should be retried."""

    pass


class ValidationError(SEALError):
    """Raised when input validation fails."""

    pass


class TemplateError(SEALError):
    """Raised for template-related errors."""

    pass


class KnowledgeBaseError(SEALError):
    """Raised for knowledge base related errors."""

    pass


class SelfEditingError(SEALError):
    """Raised when self-editing operations fail."""

    pass


class RateLimitError(RetryableError):
    """Raised when rate limits are exceeded."""

    pass


class TimeoutError(RetryableError):
    """Raised when an operation times out."""

    pass

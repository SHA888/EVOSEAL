"""Unit tests for SEAL system exceptions."""

import unittest

import pytest

from evoseal.integration.seal.exceptions import (
    KnowledgeBaseError,
    RateLimitError,
    RetryableError,
    SEALError,
    SelfEditingError,
    TemplateError,
    TimeoutError,
    ValidationError,
)


class TestSEALExceptions(unittest.TestCase):
    """Test cases for SEAL system exceptions."""

    def test_seal_error_basic(self):
        """Test basic SEALError functionality."""
        with pytest.raises(SEALError) as exc_info:
            raise SEALError("Test error")
        assert str(exc_info.value) == "Test error"

    def test_exception_inheritance(self):
        """Test that exceptions inherit from the correct base classes."""
        # Test direct inheritance
        assert issubclass(RetryableError, SEALError)
        assert issubclass(ValidationError, SEALError)
        assert issubclass(TemplateError, SEALError)
        assert issubclass(KnowledgeBaseError, SEALError)
        assert issubclass(SelfEditingError, SEALError)

        # Test multi-level inheritance
        assert issubclass(RateLimitError, RetryableError)
        assert issubclass(TimeoutError, RetryableError)

        # Verify they are still subclasses of SEALError
        assert issubclass(RateLimitError, SEALError)
        assert issubclass(TimeoutError, SEALError)

    def test_retryable_error(self):
        """Test RetryableError and its subclasses."""
        # Test RetryableError
        with pytest.raises(RetryableError):
            raise RetryableError("Should retry")

        # Test RateLimitError
        with pytest.raises(RateLimitError) as exc_info:
            error = RateLimitError("Rate limit exceeded")
            error.retry_after = 60
            raise error

        assert hasattr(exc_info.value, 'retry_after')
        assert exc_info.value.retry_after == 60

        # Test TimeoutError
        with pytest.raises(TimeoutError):
            raise TimeoutError("Operation timed out")

    def test_error_messages(self):
        """Test that error messages are properly set."""
        test_cases = [
            (ValidationError("Invalid input"), "Invalid input"),
            (TemplateError("Template not found"), "Template not found"),
            (KnowledgeBaseError("Query failed"), "Query failed"),
            (SelfEditingError("Edit failed"), "Edit failed"),
        ]

        for error, expected_msg in test_cases:
            with self.subTest(error=error):
                with pytest.raises(type(error)) as exc_info:
                    raise error
                assert str(exc_info.value) == expected_msg

    def test_exception_chaining(self):
        """Test that exceptions can be chained properly."""
        try:
            try:
                raise ValueError("Original error")
            except ValueError as e:
                raise SEALError("Wrapped error") from e
        except SEALError as e:
            assert str(e) == "Wrapped error"
            assert isinstance(e.__cause__, ValueError)
            assert str(e.__cause__) == "Original error"

    def test_retryable_flag(self):
        """Test that retryable errors are properly marked."""
        # These should be retryable
        retryable_errors = [
            RetryableError("Retryable"),
            RateLimitError("Rate limit"),
            TimeoutError("Timeout"),
        ]

        # These should not be retryable
        non_retryable_errors = [
            SEALError("Base error"),
            ValidationError("Invalid"),
            TemplateError("Template"),
            KnowledgeBaseError("KB"),
            SelfEditingError("Edit"),
        ]

        for error in retryable_errors:
            with self.subTest(error=type(error).__name__):
                assert isinstance(
                    error, RetryableError
                ), f"{type(error).__name__} should be retryable"

        for error in non_retryable_errors:
            with self.subTest(error=type(error).__name__):
                assert not isinstance(
                    error, RetryableError
                ), f"{type(error).__name__} should not be retryable"


if __name__ == "__main__":
    unittest.main()

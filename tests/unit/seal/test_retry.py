"""Unit tests for the retry utility."""

import asyncio
import random
import time
import unittest
from unittest.mock import MagicMock, patch

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
from evoseal.integration.seal.utils.retry import retry


class TestRetry(unittest.TestCase):
    """Test cases for the retry decorator."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_sleep = patch("time.sleep").start()
        self.mock_random = patch("random.random", return_value=1.0).start()
        self.addCleanup(patch.stopall)

    def test_retry_success_first_attempt(self):
        """Test that a successful function returns immediately."""
        mock_func = MagicMock(return_value="success")
        decorated = retry()(mock_func)

        result = decorated()

        self.assertEqual(result, "success")
        mock_func.assert_called_once()
        self.mock_sleep.assert_not_called()

    def test_retry_success_after_retries(self):
        """Test that a function succeeds after some retries."""
        mock_func = MagicMock(side_effect=[Exception(), Exception(), "success"])
        decorated = retry(max_retries=3, initial_delay=0.1)(mock_func)

        result = decorated()

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)
        self.assertEqual(self.mock_sleep.call_count, 2)  # Sleep between retries

    def test_retry_exhausted(self):
        """Test that all retries are exhausted before success."""
        mock_func = MagicMock(side_effect=Exception("Failed"))
        decorated = retry(max_retries=2, initial_delay=0.1)(mock_func)

        with self.assertRaises(Exception) as context:
            decorated()

        self.assertEqual(str(context.exception), "Failed")
        self.assertEqual(mock_func.call_count, 3)  # Initial + 2 retries
        self.assertEqual(self.mock_sleep.call_count, 2)

    def test_retry_specific_exceptions(self):
        """Test that only specified exceptions trigger a retry."""
        mock_func = MagicMock(
            side_effect=[ValueError("Should retry"), RuntimeError("Should not retry")]
        )
        decorated = retry(exceptions=(ValueError,), max_retries=1)(mock_func)

        with self.assertRaises(RuntimeError):
            decorated()

        # Should only be called twice: once for initial call, once for retry
        self.assertEqual(mock_func.call_count, 2)

    def test_retry_rate_limit(self):
        """Test that RateLimitError respects retry_after."""
        error = RateLimitError("Too many requests")
        error.retry_after = 1.5
        mock_func = MagicMock(side_effect=[error, "success"])
        decorated = retry()(mock_func)

        result = decorated()

        self.assertEqual(result, "success")
        self.mock_sleep.assert_called_once_with(1.5)  # Should use retry_after

    def test_retry_with_backoff(self):
        """Test that exponential backoff is applied correctly."""
        with patch("random.random", return_value=0.5):  # Fixed jitter for test
            mock_func = MagicMock(side_effect=[Exception(), Exception(), "success"])
            decorated = retry(max_retries=3, initial_delay=0.1, backoff_factor=2, max_delay=1.0)(
                mock_func
            )

            result = decorated()

            self.assertEqual(result, "success")
            # Expected sleep times with jitter: delay * (0.5 + 0.5) = delay * 1.0
            # First delay: min(0.1 * 2^0, 1.0) * 1.0 = 0.1
            # Second delay: min(0.1 * 2^1, 1.0) * 1.0 = 0.2
            expected_sleeps = [0.1, 0.2]
            actual_sleeps = [call[0][0] for call in self.mock_sleep.call_args_list]
            self.assertEqual(actual_sleeps, expected_sleeps)

    async def test_async_retry(self):
        """Test that the retry decorator works with async functions."""
        mock_func = MagicMock(side_effect=[Exception(), "success"])

        @retry()
        async def async_func():
            result = mock_func()
            if isinstance(result, Exception):
                raise result
            return result

        result = await async_func()
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)

    def test_retry_with_jitter(self):
        """Test that jitter is applied to the delay."""
        with patch("random.random", return_value=0.5):  # 50% jitter
            mock_func = MagicMock(side_effect=[Exception(), "success"])
            decorated = retry(initial_delay=1.0, backoff_factor=1.0)(mock_func)

            decorated()

            # Should be initial_delay * (0.5 + 0.5) = 1.0 * 1.0 = 1.0
            self.mock_sleep.assert_called_once_with(1.0)

    def test_retry_with_custom_exceptions(self):
        """Test that custom exceptions work with the retry decorator."""
        mock_func = MagicMock(
            side_effect=[
                ValidationError("Invalid input"),
                TemplateError("Template error"),
                "success",
            ]
        )

        decorated = retry(exceptions=(ValidationError, TemplateError), max_retries=3)(mock_func)

        result = decorated()
        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 3)

    def test_retry_with_retryable_error(self):
        """Test that RetryableError triggers a retry."""
        mock_func = MagicMock(side_effect=[RetryableError("Temporary failure"), "success"])

        decorated = retry(max_retries=1)(mock_func)
        result = decorated()

        self.assertEqual(result, "success")
        self.assertEqual(mock_func.call_count, 2)

    def test_retry_with_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        mock_func = MagicMock(side_effect=ValidationError("Invalid input"))
        decorated = retry(exceptions=(RateLimitError,))(mock_func)

        with self.assertRaises(ValidationError):
            decorated()

        mock_func.assert_called_once()

    def test_retry_with_max_delay(self):
        """Test that max_delay limits the delay between retries."""
        with patch("random.random", return_value=0.5):  # Fixed jitter for test
            mock_func = MagicMock(side_effect=[Exception(), Exception(), "success"])
            decorated = retry(
                max_retries=3,
                initial_delay=1.0,
                backoff_factor=1.5,  # Reduced factor for more predictable results
                max_delay=2.0,
            )(mock_func)

            with patch("time.sleep") as mock_sleep:
                decorated()
                # First delay: 1.0 * 1.5^0 * (0.5 + 0.5) = 1.0
                # Second delay: min(1.0 * 1.5^1 * 1.0, 2.0) = 1.5
                expected_calls = [1.0, 1.5]
                actual_calls = [call[0][0] for call in mock_sleep.call_args_list]
                self.assertEqual(actual_calls, expected_calls)

    def test_retry_with_zero_retries(self):
        """Test that zero retries means no retries are attempted."""
        mock_func = MagicMock(side_effect=Exception("Fail"))
        decorated = retry(max_retries=0)(mock_func)

        with self.assertRaises(Exception):
            decorated()

        mock_func.assert_called_once()

    def test_retry_with_negative_retries(self):
        """Test that negative retries are treated as zero retries."""
        mock_func = MagicMock(side_effect=Exception("Fail"))
        decorated = retry(max_retries=-1)(mock_func)

        with self.assertRaises(Exception) as context:
            decorated()

        # The retry decorator with negative retries should fail immediately
        self.assertEqual(str(context.exception), "Retry failed but no exception was caught")


if __name__ == "__main__":
    unittest.main()

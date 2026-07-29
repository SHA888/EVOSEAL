"""Unit tests for OllamaProvider retry and backoff logic."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from evoseal.providers.ollama_provider import OllamaProvider, _OllamaServerError


@pytest.fixture
def provider(monkeypatch):
    """Create an OllamaProvider with a known model, bypassing discovery."""
    monkeypatch.setattr(
        "evoseal.providers.ollama_provider.resolve_model",
        lambda *a, **kw: "test-model:latest",
    )
    return OllamaProvider(
        base_url="http://localhost:11434",
        model="test-model:latest",
        timeout=10,
        max_retries=3,
        backoff_base=0.01,  # tiny backoff for fast tests
    )


@pytest.fixture
def provider_no_retry(monkeypatch):
    """Create an OllamaProvider with retries disabled (max_retries=0 → 1 attempt)."""
    monkeypatch.setattr(
        "evoseal.providers.ollama_provider.resolve_model",
        lambda *a, **kw: "test-model:latest",
    )
    return OllamaProvider(
        base_url="http://localhost:11434",
        model="test-model:latest",
        timeout=10,
        max_retries=0,
        backoff_base=0.01,
    )


class _MockResponse:
    """Simulates an aiohttp.ClientResponse for testing."""

    def __init__(self, status=200, payload=None, text_body=""):
        self.status = status
        self._payload = payload or {}
        self._text_body = text_body

    async def text(self):
        return self._text_body

    async def json(self):
        return self._payload

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _MockSession:
    """Simulates an aiohttp.ClientSession for testing."""

    def __init__(self, responses, timeout=None):
        self._responses = list(responses)
        self._call_count = 0
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


class _FailResponse:
    """An async context manager that raises on entry (simulates network failure)."""

    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *exc):
        return False


class _FailSession:
    """A session whose post() returns a response that raises on context entry."""

    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def post(self, url, json=None, headers=None):
        return _FailResponse(self._exc)


# -- Success path ----------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_success(provider):
    """Successful response on first attempt."""
    mock_resp = _MockResponse(200, {"response": "hello world"})
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider.submit_prompt("test prompt")

    assert result == "hello world"


@pytest.mark.asyncio
async def test_submit_prompt_success_with_system(provider):
    """System message is included in the payload."""
    captured_json = {}

    class _CaptureSession:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            captured_json.update(json)
            return _MockResponse(200, {"response": "ok"})

    with patch("aiohttp.ClientSession", return_value=_CaptureSession()):
        await provider.submit_prompt("test", system="you are helpful")

    assert captured_json["system"] == "you are helpful"


# -- Retry on transient errors ---------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_timeout(provider):
    """Retries on TimeoutError and succeeds on second attempt."""
    call_count = 0

    def _make_session(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _FailSession(asyncio.TimeoutError("read timeout"))
        else:
            return _MockSession([_MockResponse(200, {"response": "recovered"})])

    with patch("aiohttp.ClientSession", side_effect=_make_session):
        result = await provider.submit_prompt("test")

    assert result == "recovered"
    assert call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_client_error(provider):
    """Retries on aiohttp.ClientError and succeeds on second attempt."""
    call_count = 0

    def _make_session(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _FailSession(aiohttp.ClientError("connection refused"))
        else:
            return _MockSession([_MockResponse(200, {"response": "ok"})])

    with patch("aiohttp.ClientSession", side_effect=_make_session):
        result = await provider.submit_prompt("test")

    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_500_status(provider):
    """Retries on HTTP 500 and succeeds on second attempt."""
    call_count = 0

    def _make_session(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _MockSession([_MockResponse(500, text_body="internal error")])
        else:
            return _MockSession([_MockResponse(200, {"response": "ok"})])

    with patch("aiohttp.ClientSession", side_effect=_make_session):
        result = await provider.submit_prompt("test")

    assert result == "ok"
    assert call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_500_retries_with_backoff(provider):
    """5xx retries actually sleep for backoff (not immediate)."""
    call_count = 0
    sleep_durations: list[float] = []

    real_sleep = asyncio.sleep

    async def _tracking_sleep(delay):
        sleep_durations.append(delay)
        await real_sleep(0)  # yield without actual delay

    def _make_session(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _MockSession([_MockResponse(500, text_body="internal error")])
        else:
            return _MockSession([_MockResponse(200, {"response": "ok"})])

    with patch("aiohttp.ClientSession", side_effect=_make_session):
        with patch("asyncio.sleep", side_effect=_tracking_sleep):
            result = await provider.submit_prompt("test")

    assert result == "ok"
    assert len(sleep_durations) == 1, "should sleep once between retry attempts"
    assert sleep_durations[0] > 0, "backoff delay must be positive"


@pytest.mark.asyncio
async def test_submit_prompt_exhausts_retries(provider):
    """Raises after all retries exhausted."""
    sessions = [
        _FailSession(asyncio.TimeoutError("timeout")) for _ in range(provider.max_retries + 1)
    ]

    with patch("aiohttp.ClientSession", side_effect=sessions):
        with pytest.raises(Exception, match="timed out"):
            await provider.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_bad_json(provider_no_retry):
    """JSON parse errors are not retried (bad response format)."""
    mock_resp = _MockResponse(200)
    mock_resp.json = AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="Invalid response format"):
            await provider_no_retry.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_api_error(provider_no_retry):
    """Ollama-level errors (e.g., model not found) are not retried."""
    mock_resp = _MockResponse(200, {"error": "model not found"})
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="model not found"):
            await provider_no_retry.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_400(provider_no_retry):
    """HTTP 4xx (client errors) are not retried."""
    mock_resp = _MockResponse(400, text_body="bad request")
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="status 400"):
            await provider_no_retry.submit_prompt("test")


# -- _is_retryable --------------------------------------------------------


def test_is_retryable_timeout(provider):
    assert provider._is_retryable(TimeoutError("x")) is True


def test_is_retryable_asyncio_timeout(provider):
    """asyncio.TimeoutError is retryable even on Python < 3.11."""
    assert provider._is_retryable(asyncio.TimeoutError()) is True


def test_is_retryable_asyncio_timeout_empty_message(provider):
    """Bare asyncio.TimeoutError() has an empty str() on Python < 3.11."""
    exc = asyncio.TimeoutError()
    assert str(exc) == ""  # sanity: empty message
    assert provider._is_retryable(exc) is True


def test_is_retryable_client_error(provider):
    assert provider._is_retryable(aiohttp.ClientError("x")) is True


def test_is_retryable_server_error(provider):
    assert provider._is_retryable(_OllamaServerError(503, "busy")) is True


def test_is_not_retryable_generic(provider):
    assert provider._is_retryable(ValueError("bad input")) is False


def test_is_not_retryable_generic_exception_with_timed_out(provider):
    """A generic Exception with 'timed out' in the message is NOT retryable.

    This covers the case where a 4xx body or Ollama API error message
    happens to contain the substring 'timed out' — it must not be retried.
    """
    exc = Exception("Ollama API request failed with status 400: context timed out")
    assert provider._is_retryable(exc) is False


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_400_with_timed_out_body(provider_no_retry):
    """HTTP 4xx with 'timed out' in the body is NOT retried."""
    mock_resp = _MockResponse(400, text_body="context timed out loading model")
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="status 400"):
            await provider_no_retry.submit_prompt("test")


# -- Configuration ---------------------------------------------------------


def test_max_retries_configurable(monkeypatch):
    monkeypatch.setattr(
        "evoseal.providers.ollama_provider.resolve_model",
        lambda *a, **kw: "test-model:latest",
    )
    p = OllamaProvider(model="test-model:latest", max_retries=5)
    assert p.max_retries == 5


def test_max_retries_clamped_to_minimum(monkeypatch):
    """max_retries < 0 is clamped to 0 (single attempt, no retries)."""
    monkeypatch.setattr(
        "evoseal.providers.ollama_provider.resolve_model",
        lambda *a, **kw: "test-model:latest",
    )
    p = OllamaProvider(model="test-model:latest", max_retries=0)
    assert p.max_retries == 0
    p2 = OllamaProvider(model="test-model:latest", max_retries=-3)
    assert p2.max_retries == 0


def test_backoff_base_configurable(monkeypatch):
    monkeypatch.setattr(
        "evoseal.providers.ollama_provider.resolve_model",
        lambda *a, **kw: "test-model:latest",
    )
    p = OllamaProvider(model="test-model:latest", backoff_base=2.0)
    assert p.backoff_base == 2.0


def test_get_model_info_includes_retry_config(provider):
    info = provider.get_model_info()
    assert info["max_retries"] == 3
    assert info["backoff_base"] == 0.01

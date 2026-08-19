"""Unit tests for VLLMProvider retry, backoff, and response parsing."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, patch

import aiohttp
import pytest

from evoseal.providers.vllm_provider import VLLMProvider, _VLLMServerError  # noqa: F401


@pytest.fixture
def provider():
    """Create a VLLMProvider with a known model."""
    return VLLMProvider(
        base_url="http://localhost:8000",
        model="test-model",
        timeout=10,
        max_retries=3,
        backoff_base=0.01,
    )


@pytest.fixture
def provider_no_retry():
    """Create a VLLMProvider with retries disabled."""
    return VLLMProvider(
        base_url="http://localhost:8000",
        model="test-model",
        timeout=10,
        max_retries=0,
        backoff_base=0.01,
    )


class _MockResponse:
    """Simulates an aiohttp.ClientResponse."""

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
    """Simulates an aiohttp.ClientSession."""

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

    def get(self, url, headers=None):
        resp = self._responses[self._call_count]
        self._call_count += 1
        return resp


class _FailResponse:
    """Async context manager that raises on entry."""

    def __init__(self, exc):
        self._exc = exc

    async def __aenter__(self):
        raise self._exc

    async def __aexit__(self, *exc):
        return False


def _openai_response(content: str, model: str = "test-model") -> dict:
    """Build a minimal OpenAI-compatible chat completion response."""
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
    }


# -- Success path ----------------------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_success(provider):
    """Successful response on first attempt."""
    mock_resp = _MockResponse(200, _openai_response("hello world"))
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider.submit_prompt("test prompt")

    assert result == "hello world"


@pytest.mark.asyncio
async def test_submit_prompt_includes_system_message(provider):
    """System message is passed in the messages array."""
    captured_json: dict = {}

    class _CaptureSession:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            captured_json.update(json)
            return _MockResponse(200, _openai_response("ok"))

    with patch("aiohttp.ClientSession", return_value=_CaptureSession()):
        await provider.submit_prompt("test", system="you are helpful")

    assert captured_json["messages"][0] == {"role": "system", "content": "you are helpful"}
    assert captured_json["messages"][1] == {"role": "user", "content": "test"}


@pytest.mark.asyncio
async def test_submit_prompt_includes_auth_header():
    """API key is sent as Bearer token."""
    captured_headers: dict = {}

    class _CaptureSession:
        def __init__(self, timeout=None):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        def post(self, url, json=None, headers=None):
            captured_headers.update(headers or {})
            return _MockResponse(200, _openai_response("ok"))

    p = VLLMProvider(model="m", api_key="sk-test-key", max_retries=0)  # pragma: allowlist secret
    with patch("aiohttp.ClientSession", return_value=_CaptureSession()):
        await p.submit_prompt("hi")

    assert captured_headers["Authorization"] == "Bearer sk-test-key"


# -- Retry on transient errors ---------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_timeout(provider):
    """Retries on TimeoutError and succeeds on second attempt."""
    mock_session = _MockSession(
        [
            _FailResponse(asyncio.TimeoutError("read timeout")),
            _MockResponse(200, _openai_response("recovered")),
        ]
    )

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider.submit_prompt("test")

    assert result == "recovered"
    assert mock_session._call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_client_error(provider):
    """Retries on aiohttp.ClientError and succeeds on second attempt."""
    mock_session = _MockSession(
        [
            _FailResponse(aiohttp.ClientError("connection refused")),
            _MockResponse(200, _openai_response("ok")),
        ]
    )

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider.submit_prompt("test")

    assert result == "ok"
    assert mock_session._call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_retries_on_500_status(provider):
    """Retries on HTTP 500 and succeeds on second attempt."""
    mock_session = _MockSession(
        [
            _MockResponse(500, text_body="internal error"),
            _MockResponse(200, _openai_response("ok")),
        ]
    )

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider.submit_prompt("test")

    assert result == "ok"
    assert mock_session._call_count == 2


@pytest.mark.asyncio
async def test_submit_prompt_exhausts_retries(provider):
    """Raises after all retries exhausted."""
    mock_session = _MockSession(
        [_FailResponse(asyncio.TimeoutError("timeout"))] * (provider.max_retries + 1)
    )

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="timed out"):
            await provider.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_bad_json(provider_no_retry):
    """JSON parse errors are not retried."""
    mock_resp = _MockResponse(200)
    mock_resp.json = AsyncMock(side_effect=json.JSONDecodeError("bad", "", 0))
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="Invalid response format"):
            await provider_no_retry.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_api_error(provider_no_retry):
    """vLLM-level errors are not retried."""
    mock_resp = _MockResponse(200, {"error": {"message": "model not found", "type": "invalid"}})
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="model not found"):
            await provider_no_retry.submit_prompt("test")


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_400(provider_no_retry):
    """HTTP 4xx is not retried."""
    mock_resp = _MockResponse(400, text_body="bad request")
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(Exception, match="status 400"):
            await provider_no_retry.submit_prompt("test")


# -- _is_retryable --------------------------------------------------------


def test_is_retryable_timeout(provider):
    assert provider._is_retryable(TimeoutError("x")) is True


def test_is_retryable_asyncio_timeout(provider):
    assert provider._is_retryable(asyncio.TimeoutError()) is True


def test_is_retryable_client_error(provider):
    assert provider._is_retryable(aiohttp.ClientError("x")) is True


def test_is_not_retryable_content_type_error(provider):
    """ContentTypeError indicates a malformed response, not transient."""
    exc = aiohttp.ContentTypeError(
        aiohttp.RequestInfo(
            url=aiohttp.client.URL("http://localhost:8000"),
            method="GET",
            headers={},
            real_url=aiohttp.client.URL("http://localhost:8000"),
        ),
        history=(),
        message="bad content-type",
    )
    assert provider._is_retryable(exc) is False


def test_is_retryable_server_error(provider):
    assert provider._is_retryable(_VLLMServerError(503, "busy")) is True


def test_is_not_retryable_generic(provider):
    assert provider._is_retryable(ValueError("bad input")) is False


# -- Health check ----------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check_success(provider):
    """Healthy server with the model available."""
    models_response = {"data": [{"id": "test-model"}, {"id": "other-model"}]}
    mock_session = _MockSession([_MockResponse(200, models_response)])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        assert await provider.health_check() is True


@pytest.mark.asyncio
async def test_health_check_model_not_found(provider):
    """Server is up but model is not installed."""
    models_response = {"data": [{"id": "other-model"}]}
    mock_session = _MockSession([_MockResponse(200, models_response)])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_health_check_server_unreachable(provider):
    """Server is unreachable."""
    mock_session = _MockSession([_FailResponse(aiohttp.ClientError("connection refused"))])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        assert await provider.health_check() is False


@pytest.mark.asyncio
async def test_health_check_empty_model_rejected():
    """An empty model string must match a real model or fail."""
    p = VLLMProvider(model="", max_retries=0)
    models_response = {"data": [{"id": "any-model"}]}
    mock_session = _MockSession([_MockResponse(200, models_response)])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        assert await p.health_check() is False


# -- Null content safety ---------------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_null_content_returns_empty_string(provider_no_retry):
    """When vLLM returns content=null (e.g. tool-call response), degrade to empty string."""
    resp = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": None},
                "finish_reason": "stop",
            }
        ],
    }
    mock_resp = _MockResponse(200, resp)
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        result = await provider_no_retry.submit_prompt("test")

    assert result == ""


# -- ContentTypeError not retried ------------------------------------------


@pytest.mark.asyncio
async def test_submit_prompt_no_retry_on_content_type_error(provider_no_retry):
    """ContentTypeError (malformed response) is not retried."""
    mock_resp = _MockResponse(200)
    mock_resp.json = AsyncMock(
        side_effect=aiohttp.ContentTypeError(
            aiohttp.RequestInfo(
                url=aiohttp.client.URL("http://localhost:8000/v1/chat/completions"),
                method="POST",
                headers={},
                real_url=aiohttp.client.URL("http://localhost:8000/v1/chat/completions"),
            ),
            history=(),
            message="content-type mismatch",
        )
    )
    mock_session = _MockSession([mock_resp])

    with patch("aiohttp.ClientSession", return_value=mock_session):
        with pytest.raises(aiohttp.ContentTypeError):
            await provider_no_retry.submit_prompt("test")


# -- parse_response --------------------------------------------------------


@pytest.mark.asyncio
async def test_parse_response_plain_text(provider):
    result = await provider.parse_response("hello world")
    assert result["content"] == "hello world"
    assert result["provider"] == "vllm"
    assert result["contains_code"] is False
    assert result["code_blocks"] == []


@pytest.mark.asyncio
async def test_parse_response_with_code_block(provider):
    text = "Here is code:\n```python\nprint('hi')\n```\nDone."
    result = await provider.parse_response(text)
    assert result["contains_code"] is True
    assert len(result["code_blocks"]) == 1
    assert result["code_blocks"][0]["language"] == "python"
    assert "print('hi')" in result["code_blocks"][0]["code"]


# -- Configuration ---------------------------------------------------------


def test_max_retries_configurable():
    p = VLLMProvider(model="m", max_retries=5)
    assert p.max_retries == 5


def test_max_retries_clamped_to_minimum():
    p = VLLMProvider(model="m", max_retries=-3)
    assert p.max_retries == 0


def test_get_model_info(provider):
    info = provider.get_model_info()
    assert info["provider"] == "vllm"
    assert info["model"] == "test-model"
    assert info["max_retries"] == 3
    assert info["backoff_base"] == 0.01


# -- Empty model warning ---------------------------------------------------


def test_empty_model_logs_warning(caplog):
    """Initializing with an empty model should log a warning."""
    import logging

    with caplog.at_level(logging.WARNING, logger="evoseal.providers.vllm_provider"):
        VLLMProvider(model="", max_retries=0)
    assert "empty model string" in caplog.text


# -- HTTP scheme warning ---------------------------------------------------


def test_api_key_over_http_nonlocalhost_warns(caplog):
    """api_key + http:// to a non-localhost host should warn about plaintext credentials."""
    import logging

    with caplog.at_level(logging.WARNING, logger="evoseal.providers.vllm_provider"):
        VLLMProvider(
            base_url="http://remote-server:8000",
            model="m",
            api_key="test-api-key",  # pragma: allowlist secret
            max_retries=0,
        )
    assert "plain text" in caplog.text
    assert "remote-server" in caplog.text


def test_api_key_over_https_no_warning(caplog):
    """api_key + https:// should not warn about plaintext credentials."""
    import logging

    with caplog.at_level(logging.WARNING, logger="evoseal.providers.vllm_provider"):
        VLLMProvider(
            base_url="https://remote-server:8000",
            model="m",
            api_key="test-api-key",  # pragma: allowlist secret
            max_retries=0,
        )
    assert "plain text" not in caplog.text


def test_api_key_on_localhost_no_warning(caplog):
    """api_key + http://localhost should not warn."""
    import logging

    with caplog.at_level(logging.WARNING, logger="evoseal.providers.vllm_provider"):
        VLLMProvider(
            base_url="http://localhost:8000",
            model="m",
            api_key="test-api-key",  # pragma: allowlist secret
            max_retries=0,
        )
    assert "plain text" not in caplog.text


# -- Unterminated code fence -----------------------------------------------


@pytest.mark.asyncio
async def test_parse_response_unterminated_code_fence(provider):
    """An unterminated code fence should still capture the trailing block."""
    text = "Here is code:\n```python\nprint('hi')\nmore lines"
    result = await provider.parse_response(text)
    assert result["contains_code"] is True
    assert len(result["code_blocks"]) == 1
    assert result["code_blocks"][0]["language"] == "python"
    assert "print('hi')" in result["code_blocks"][0]["code"]
    assert "more lines" in result["code_blocks"][0]["code"]

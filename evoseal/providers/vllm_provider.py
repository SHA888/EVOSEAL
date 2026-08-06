"""vLLM provider for EVOSEAL.

Integrates with a local or remote vLLM server via its OpenAI-compatible API
(``/v1/chat/completions``).  vLLM is a high-throughput LLM serving engine
that supports continuous batching, PagedAttention, and quantised inference
on commodity hardware.

Typical setup::

    # Start vLLM (separate process):
    #   vllm serve deepseek-coder-6.7b-instruct --port 8000
    #
    # Then in EVOSEAL config, add a ``vllm`` provider entry pointing at
    # ``http://localhost:8000`` (or set ``EVOSEAL_VLLM_BASE_URL``).

The provider reuses the same ``SEALProvider`` interface as ``OllamaProvider``
so it can be selected, health-checked, and swapped transparently.
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from typing import Any

import aiohttp

from evoseal.providers.seal_providers import SEALProvider

logger = logging.getLogger(__name__)

#: Default vLLM OpenAI-compatible endpoint.
DEFAULT_VLLM_BASE_URL = "http://localhost:8000"

#: Default model used when none is specified and no server-side default exists.
DEFAULT_VLLM_MODEL = "default"


class _VLLMServerError(Exception):
    """Internal: raised on HTTP 5xx to unify retry logic."""

    def __init__(self, status: int, body: str):
        super().__init__(f"vLLM API request failed with status {status}: {body}")
        self.status = status


class VLLMProvider(SEALProvider):
    """vLLM provider for EVOSEAL using the OpenAI-compatible API.

    Connects to a running vLLM server and sends chat-completion requests.
    Retries transient failures (timeouts, connection errors, 5xx) with
    exponential backoff and jitter.
    """

    def __init__(
        self,
        base_url: str = DEFAULT_VLLM_BASE_URL,
        model: str = DEFAULT_VLLM_MODEL,
        timeout: int = 120,
        api_key: str | None = None,
        max_retries: int = 3,
        backoff_base: float = 1.0,
        max_backoff: float = 30.0,
        **kwargs: Any,
    ) -> None:
        """Initialize the vLLM provider.

        Args:
            base_url: Base URL of the vLLM server (default ``http://localhost:8000``).
            model: Model name to use in chat-completion requests.  When the
                server hosts a single model it may be omitted (vLLM defaults).
            timeout: Per-request timeout in seconds (default 120).
            api_key: Optional API key for authenticated vLLM servers.
                Sent as ``Authorization: Bearer <api_key>``.
            max_retries: Maximum retries for transient failures after the
                initial attempt.  Total attempts = 1 + max_retries.
            backoff_base: Base delay in seconds for exponential backoff.
            max_backoff: Upper cap on backoff delay (excluding jitter).
            **kwargs: Additional generation parameters (``temperature``,
                ``top_p``, ``max_tokens``, ``stop``).
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.api_key = api_key
        self.max_retries = max(0, max_retries)
        self.backoff_base = backoff_base
        self.max_backoff = max_backoff
        self.config = kwargs

        # Default generation parameters
        self.default_params: dict[str, Any] = {
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "max_tokens": kwargs.get("max_tokens", 2048),
        }
        if "stop" in kwargs:
            self.default_params["stop"] = kwargs["stop"]

        logger.info("Initialized vLLM provider with model %s at %s", self.model, base_url)

    def _is_retryable(self, exc: Exception) -> bool:
        """Return True if the exception represents a transient failure."""
        if isinstance(exc, (asyncio.TimeoutError, TimeoutError, aiohttp.ClientError)):
            return True
        if isinstance(exc, _VLLMServerError):
            return True
        return False

    def _headers(self) -> dict[str, str]:
        """Build request headers, including optional auth."""
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to the vLLM server via ``/v1/chat/completions``.

        Retries transient failures with exponential backoff + jitter.

        Args:
            prompt: The user prompt.
            **kwargs: Override generation parameters (``temperature``,
                ``max_tokens``, ``system``, ``stop``).

        Returns:
            The assistant message content.

        Raises:
            Exception: If the request fails after all retries.
        """
        # Build messages
        messages: list[dict[str, str]] = []
        if "system" in kwargs:
            messages.append({"role": "system", "content": kwargs["system"]})
        messages.append({"role": "user", "content": prompt})

        # Merge parameters
        params = {**self.default_params}
        if "temperature" in kwargs:
            params["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            params["max_tokens"] = kwargs["max_tokens"]
        if "stop" in kwargs:
            params["stop"] = kwargs["stop"]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **params,
        }

        last_exc: Exception | None = None
        total_attempts = self.max_retries + 1
        deadline = asyncio.get_event_loop().time() + self.timeout * total_attempts

        timeout = aiohttp.ClientTimeout(total=self.timeout, sock_read=self.timeout)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for attempt in range(total_attempts):
                remaining = deadline - asyncio.get_event_loop().time()
                if remaining < self.timeout * 0.5:
                    logger.warning(
                        "Overall deadline reached before attempt %d/%d; abandoning retries",
                        attempt + 1,
                        total_attempts,
                    )
                    break

                try:
                    logger.debug(
                        "Sending request to vLLM: %s/v1/chat/completions (attempt %d/%d)",
                        self.base_url,
                        attempt + 1,
                        total_attempts,
                    )

                    async with session.post(
                        f"{self.base_url}/v1/chat/completions",
                        json=payload,
                        headers=self._headers(),
                    ) as response:
                        if response.status >= 500:
                            error_text = await response.text()
                            raise _VLLMServerError(response.status, error_text)
                        elif response.status != 200:
                            error_text = await response.text()
                            raise Exception(
                                f"vLLM API request failed with status {response.status}: {error_text}"
                            )

                        result = await response.json()

                        # OpenAI-compatible error envelope
                        if "error" in result:
                            raise Exception(f"vLLM API error: {result['error']}")

                        content = (
                            result.get("choices", [{}])[0].get("message", {}).get("content", "")
                        )
                        logger.debug("Received response from vLLM (%d chars)", len(content))
                        return content

                except json.JSONDecodeError as e:
                    logger.error("Invalid JSON response from vLLM: %s", e)
                    raise Exception(f"Invalid response format from vLLM: {e}") from e

                except Exception as e:
                    if not self._is_retryable(e):
                        raise
                    if isinstance(e, (asyncio.TimeoutError, TimeoutError)):
                        last_exc = Exception(f"vLLM request timed out after {self.timeout} seconds")
                    elif isinstance(e, _VLLMServerError):
                        last_exc = Exception(str(e))
                    elif isinstance(e, aiohttp.ClientError):
                        last_exc = Exception(f"vLLM request failed ({type(e).__name__}): {e}")
                    else:
                        last_exc = Exception(f"vLLM request failed: {e}")
                    last_exc.__cause__ = e
                    logger.warning(
                        "Attempt %d/%d: retryable error: %s", attempt + 1, total_attempts, e
                    )

                # Back off before next attempt
                if attempt < self.max_retries:
                    delay = min(
                        self.backoff_base * (2**attempt), self.max_backoff
                    ) + random.uniform(0, 0.5)
                    logger.debug("Retrying in %.1fs...", delay)
                    await asyncio.sleep(delay)

        if last_exc is None:
            raise RuntimeError(
                f"vLLM request failed after {total_attempts} attempts "
                "but no exception was captured — this is a bug"
            )
        logger.error("vLLM request failed after %d attempts", total_attempts)
        raise last_exc

    async def parse_response(self, response: str) -> dict[str, Any]:
        """Parse the text response from vLLM.

        Args:
            response: The raw text response.

        Returns:
            A dictionary with parsed content and metadata.
        """
        parsed: dict[str, Any] = {
            "content": response.strip(),
            "model": self.model,
            "provider": "vllm",
            "length": len(response),
        }

        if "```" in response:
            parsed["contains_code"] = True
            code_blocks: list[dict[str, str]] = []
            lines = response.split("\n")
            in_block = False
            current_block: list[str] = []
            current_lang = ""

            for line in lines:
                if line.strip().startswith("```"):
                    if in_block:
                        code_blocks.append(
                            {"language": current_lang, "code": "\n".join(current_block)}
                        )
                        current_block = []
                        in_block = False
                    else:
                        current_lang = line.strip()[3:].strip()
                        in_block = True
                elif in_block:
                    current_block.append(line)

            parsed["code_blocks"] = code_blocks
        else:
            parsed["contains_code"] = False
            parsed["code_blocks"] = []

        return parsed

    async def health_check(self) -> bool:
        """Check if the vLLM server is reachable and the model is available.

        Uses ``GET /v1/models`` and verifies the configured model appears
        in the response.

        Returns:
            True if healthy, False otherwise.
        """
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
                async with session.get(
                    f"{self.base_url}/v1/models", headers=self._headers()
                ) as response:
                    if response.status != 200:
                        return False

                    data = await response.json()
                    model_ids = [m.get("id", "") for m in data.get("data", [])]

                    if self.model not in model_ids and self.model != DEFAULT_VLLM_MODEL:
                        logger.warning(
                            "Model %s not found in vLLM. Available: %s", self.model, model_ids
                        )
                        return False

                    logger.info("vLLM health check passed. Model %s is available.", self.model)
                    return True

        except Exception as e:
            logger.error("vLLM health check failed: %s", e)
            return False

    def get_model_info(self) -> dict[str, Any]:
        """Return provider configuration metadata.

        Returns:
            Dictionary with provider information.
        """
        return {
            "provider": "vllm",
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "default_params": self.default_params,
            "max_retries": self.max_retries,
            "backoff_base": self.backoff_base,
            "max_backoff": self.max_backoff,
        }

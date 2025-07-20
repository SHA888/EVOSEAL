"""
SEALInterface for EVOSEAL
-------------------------
Abstraction layer for communication with SEAL (Self-Adapting Language Models).
Supports multiple SEAL (Self-Adapting Language Models) providers, async operation, rate limiting, and retry logic.
References: /SEAL (Self-Adapting Language Models) folder, https://github.com/SHA888/SEAL (Self-Adapting Language Models)
"""

import asyncio
from collections.abc import Awaitable
from typing import Any, Callable, Optional, Protocol


class SEALProvider(Protocol):
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str: ...
    async def parse_response(self, response: str) -> Any: ...


class SEALInterface:
    def __init__(
        self,
        provider: SEALProvider,
        rate_limit_per_sec: float = 1.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        self.provider = provider
        self.rate_limit_per_sec = rate_limit_per_sec
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._lock = asyncio.Lock()
        self._last_call = 0.0

    async def submit(self, prompt: str, **kwargs: Any) -> Any:
        retries = 0
        while retries <= self.max_retries:
            async with self._lock:
                now = asyncio.get_event_loop().time()
                elapsed = now - self._last_call
                wait_time = max(0, 1.0 / self.rate_limit_per_sec - elapsed)
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                self._last_call = asyncio.get_event_loop().time()
            try:
                response = await self.provider.submit_prompt(prompt, **kwargs)
                return await self.provider.parse_response(response)
            except Exception as e:
                retries += 1
                if retries > self.max_retries:
                    raise RuntimeError(
                        f"SEALInterface failed after {self.max_retries} retries."
                    ) from e
                await asyncio.sleep(self.retry_delay)

"""
Concrete SEAL (Self-Adapting Language Models) provider stub for EVOSEAL.
Replace with real SEAL (Self-Adapting Language Models) backend integration as needed.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any


class SEALProvider(ABC):
    """Abstract base class for SEAL (Self-Adapting Language Models) providers."""

    @abstractmethod
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to the SEAL (Self-Adapting Language Models) provider.

        Args:
            prompt: The prompt to submit
            **kwargs: Additional arguments for the provider

        Returns:
            The raw response from the provider
        """
        ...

    @abstractmethod
    async def parse_response(self, response: str) -> dict[str, Any]:
        """Parse the response from the SEAL (Self-Adapting Language Models) provider.

        Args:
            response: The raw response from the provider

        Returns:
            A dictionary containing the parsed response
        """
        ...


class DummySEALProvider(SEALProvider):
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to the dummy SEAL (Self-Adapting Language Models) provider.

        Args:
            prompt: The prompt to submit
            **kwargs: Additional arguments (ignored in dummy implementation)

        Returns:
            A dummy response containing the original prompt
        """
        await asyncio.sleep(0.1)
        return f"[SEAL (Self-Adapting Language Models)-Dummy-Response] {prompt}"

    async def parse_response(self, response: str) -> dict[str, Any]:
        """Parse the response from the dummy SEAL (Self-Adapting Language Models) provider.

        Args:
            response: The raw response from the provider

        Returns:
            A dictionary containing the parsed response
        """
        return {"result": response, "parsed": True}

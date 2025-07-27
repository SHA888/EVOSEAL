"""
Unit tests for SEALInterface and DummySEALProvider.
"""

import asyncio

import pytest

from evoseal.integration.seal.seal_interface import SEALInterface
from evoseal.providers.seal_providers import DummySEALProvider


@pytest.mark.asyncio
async def test_seal_interface_submit():
    provider = DummySEALProvider()
    interface = SEALInterface(provider, rate_limit_per_sec=10.0)
    result = await interface.submit("test prompt")
    assert result["parsed"] is True
    assert "test prompt" in result["result"]


class FailingProvider:
    async def submit_prompt(self, prompt: str, **kwargs):
        raise RuntimeError("provider error")

    async def parse_response(self, response: str):
        return {}


@pytest.mark.asyncio
async def test_seal_interface_provider_failure():
    provider = FailingProvider()
    interface = SEALInterface(
        provider, rate_limit_per_sec=100.0, max_retries=1, retry_delay=0
    )
    with pytest.raises(RuntimeError, match="failed after 1 retries"):
        await interface.submit("fail prompt")


@pytest.mark.asyncio
async def test_seal_interface_empty_prompt():
    class EchoProvider:
        async def submit_prompt(self, prompt: str, **kwargs):
            return prompt

        async def parse_response(self, response: str):
            return {"parsed": bool(response)}

    provider = EchoProvider()
    interface = SEALInterface(provider)
    result = await interface.submit("")
    assert result["parsed"] is False

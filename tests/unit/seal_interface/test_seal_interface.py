"""
Unit tests for SEALInterface and DummySEALProvider.
"""

import asyncio

import pytest

from evoseal.seal_interface import SEALInterface
from evoseal.seal_providers import DummySEALProvider


@pytest.mark.asyncio
async def test_seal_interface_submit():
    provider = DummySEALProvider()
    interface = SEALInterface(provider, rate_limit_per_sec=10.0)
    result = await interface.submit("test prompt")
    assert result["parsed"] is True
    assert "test prompt" in result["result"]

"""
Concrete SEAL provider stub for EVOSEAL.
Replace with real SEAL backend integration as needed.
"""

import asyncio
from typing import Any


class DummySEALProvider:
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        await asyncio.sleep(0.1)
        return f"[SEAL-Dummy-Response] {prompt}"

    async def parse_response(self, response: str) -> Any:
        # Simulate parsing
        return {"result": response, "parsed": True}

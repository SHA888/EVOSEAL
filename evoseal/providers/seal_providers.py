"""
Concrete SEAL provider stub for EVOSEAL.
Replace with real SEAL backend integration as needed.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class SEALProvider(ABC):
    """Abstract base class for SEAL providers."""
    
    @abstractmethod
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to the SEAL provider.
        
        Args:
            prompt: The prompt to submit
            **kwargs: Additional arguments for the provider
            
        Returns:
            The raw response from the provider
        """
        pass
    
    @abstractmethod
    async def parse_response(self, response: str) -> Dict[str, Any]:
        """Parse the response from the SEAL provider.
        
        Args:
            response: The raw response from the provider
            
        Returns:
            A dictionary containing the parsed response
        """
        pass


class DummySEALProvider(SEALProvider):
    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        await asyncio.sleep(0.1)
        return f"[SEAL-Dummy-Response] {prompt}"

    async def parse_response(self, response: str) -> Any:
        # Simulate parsing
        return {"result": response, "parsed": True}

"""
Ollama provider for EVOSEAL.
Integrates with local Ollama instance for code generation and analysis.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

from evoseal.providers.seal_providers import SEALProvider

logger = logging.getLogger(__name__)


class OllamaProvider(SEALProvider):
    """Ollama provider for EVOSEAL using local Ollama instance."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "devstral:latest",
        timeout: int = 120,
        **kwargs: Any,
    ) -> None:
        """Initialize the Ollama provider.

        Args:
            base_url: Base URL for Ollama API (default: http://localhost:11434)
            model: Model name to use (default: devstral:latest)
            timeout: Request timeout in seconds (default: 120)
            **kwargs: Additional configuration options
        """
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.config = kwargs

        # Default generation parameters
        self.default_options = {
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            "top_k": kwargs.get("top_k", 40),
            "num_predict": kwargs.get("max_tokens", 2048),
            "stop": kwargs.get("stop_sequences", []),
        }

        logger.info(f"Initialized Ollama provider with model {model} at {base_url}")

    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to the Ollama instance.

        Args:
            prompt: The prompt to submit
            **kwargs: Additional options for generation

        Returns:
            The raw response from Ollama

        Raises:
            Exception: If the request fails or times out
        """
        # Merge default options with provided kwargs
        options = {**self.default_options}
        if "temperature" in kwargs:
            options["temperature"] = kwargs["temperature"]
        if "max_tokens" in kwargs:
            options["num_predict"] = kwargs["max_tokens"]
        if "stop_sequences" in kwargs:
            options["stop"] = kwargs["stop_sequences"]

        # Prepare the request payload
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,  # Get complete response
            "options": options,
        }

        # Add system message if provided
        if "system" in kwargs:
            payload["system"] = kwargs["system"]

        try:
            # Use a longer timeout for Ollama requests as they can be slow
            timeout = aiohttp.ClientTimeout(total=self.timeout, sock_read=self.timeout)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                logger.debug(f"Sending request to Ollama: {self.base_url}/api/generate")
                
                async with session.post(
                    f"{self.base_url}/api/generate",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                ) as response:
                    if response.status != 200:
                        error_text = await response.text()
                        raise Exception(
                            f"Ollama API request failed with status {response.status}: {error_text}"
                        )

                    result = await response.json()
                    
                    if "error" in result:
                        raise Exception(f"Ollama API error: {result['error']}")

                    response_text = result.get("response", "")
                    
                    logger.debug(f"Received response from Ollama ({len(response_text)} chars)")
                    return response_text

        except asyncio.TimeoutError as e:
            logger.error(f"Timeout error communicating with Ollama after {self.timeout}s: {e}")
            raise Exception(f"Ollama request timed out after {self.timeout} seconds")
        except aiohttp.ClientError as e:
            logger.error(f"Network error communicating with Ollama: {e}")
            raise Exception(f"Failed to connect to Ollama at {self.base_url}: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Ollama: {e}")
            raise Exception(f"Invalid response format from Ollama: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in Ollama request: {type(e).__name__}: {e}")
            raise

    async def parse_response(self, response: str) -> dict[str, Any]:
        """Parse the response from Ollama.

        Args:
            response: The raw response from Ollama

        Returns:
            A dictionary containing the parsed response
        """
        # Basic parsing - can be enhanced based on specific needs
        parsed = {
            "content": response.strip(),
            "model": self.model,
            "provider": "ollama",
            "length": len(response),
        }

        # Try to detect if response contains code
        if "```" in response:
            parsed["contains_code"] = True
            # Extract code blocks
            code_blocks = []
            lines = response.split("\n")
            in_code_block = False
            current_block = []
            current_language = ""

            for line in lines:
                if line.strip().startswith("```"):
                    if in_code_block:
                        # End of code block
                        code_blocks.append({
                            "language": current_language,
                            "code": "\n".join(current_block)
                        })
                        current_block = []
                        in_code_block = False
                    else:
                        # Start of code block
                        current_language = line.strip()[3:].strip()
                        in_code_block = True
                elif in_code_block:
                    current_block.append(line)

            parsed["code_blocks"] = code_blocks
        else:
            parsed["contains_code"] = False
            parsed["code_blocks"] = []

        return parsed

    async def health_check(self) -> bool:
        """Check if Ollama is healthy and the model is available.

        Returns:
            True if healthy, False otherwise
        """
        try:
            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=10)
            ) as session:
                # Check if Ollama is running
                async with session.get(f"{self.base_url}/api/tags") as response:
                    if response.status != 200:
                        return False

                    data = await response.json()
                    models = [model["name"] for model in data.get("models", [])]
                    
                    # Check if our model is available
                    if self.model not in models:
                        logger.warning(f"Model {self.model} not found in Ollama. Available: {models}")
                        return False

                    logger.info(f"Ollama health check passed. Model {self.model} is available.")
                    return True

        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model configuration.

        Returns:
            Dictionary with model information
        """
        return {
            "provider": "ollama",
            "base_url": self.base_url,
            "model": self.model,
            "timeout": self.timeout,
            "default_options": self.default_options,
        }

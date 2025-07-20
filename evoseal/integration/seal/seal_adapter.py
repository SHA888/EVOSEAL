"""
SEAL (Self-Adapting Language Models) Component Adapter for EVOSEAL Integration

This module provides the adapter for integrating SEAL (Self-Adapting Language Models)
into the EVOSEAL pipeline with proper lifecycle management, rate limiting, and provider abstraction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional, Union

from ..base_adapter import (
    BaseComponentAdapter,
    ComponentConfig,
    ComponentResult,
    ComponentState,
    ComponentType,
)
from .seal_interface import SEALInterface, SEALProvider

logger = logging.getLogger(__name__)


class DefaultSEALProvider:
    """Default SEAL (Self-Adapting Language Models) provider implementation."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.DefaultSEALProvider")

    async def submit_prompt(self, prompt: str, **kwargs: Any) -> str:
        """Submit a prompt to SEAL (Self-Adapting Language Models) and return the response."""
        # This is a placeholder implementation
        # In a real implementation, this would connect to actual SEAL (Self-Adapting Language Models) services
        self.logger.info(
            f"Submitting prompt to SEAL (Self-Adapting Language Models): {prompt[:100]}..."
        )

        # Simulate processing time
        await asyncio.sleep(0.1)

        # Return a mock response
        return f"SEAL (Self-Adapting Language Models) response to: {prompt[:50]}..."

    async def parse_response(self, response: str) -> Any:
        """Parse the SEAL (Self-Adapting Language Models) response."""
        # Simple parsing - in reality this would be more sophisticated
        return {"response": response, "timestamp": time.time(), "parsed": True}


class SEALAdapter(BaseComponentAdapter):
    """
    Adapter for integrating SEAL (Self-Adapting Language Models) into the EVOSEAL pipeline.

    Provides high-level interface for SEAL (Self-Adapting Language Models) operations including
    prompt submission, response parsing, rate limiting, and retry logic.
    """

    def __init__(self, config: ComponentConfig):
        if config.component_type != ComponentType.SEAL:
            raise ValueError("SEALAdapter requires ComponentType.SEAL")

        super().__init__(config)
        self.seal_interface: Optional[SEALInterface] = None
        self.provider: Optional[SEALProvider] = None
        self._rate_limit: float = 1.0
        self._max_retries: int = 3
        self._retry_delay: float = 1.0

    async def _initialize_impl(self) -> bool:
        """Initialize the SEAL (Self-Adapting Language Models) interface and provider."""
        try:
            # Extract configuration
            seal_config = self.config.config
            self._rate_limit = seal_config.get("rate_limit_per_sec", 1.0)
            self._max_retries = seal_config.get("max_retries", 3)
            self._retry_delay = seal_config.get("retry_delay", 1.0)

            # Initialize provider
            provider_type = seal_config.get("provider_type", "default")
            provider_config = seal_config.get("provider_config", {})

            if provider_type == "default":
                self.provider = DefaultSEALProvider(provider_config)
            else:
                # Support for custom providers
                provider_class = seal_config.get("provider_class")
                if provider_class:
                    self.provider = provider_class(provider_config)
                else:
                    raise ValueError(f"Unknown provider type: {provider_type}")

            # Initialize SEAL (Self-Adapting Language Models) interface
            self.seal_interface = SEALInterface(
                provider=self.provider,
                rate_limit_per_sec=self._rate_limit,
                max_retries=self._max_retries,
                retry_delay=self._retry_delay,
            )

            self.logger.info(
                f"SEAL (Self-Adapting Language Models) initialized with provider: {provider_type}"
            )
            return True

        except Exception as e:
            self.logger.exception("Failed to initialize SEAL (Self-Adapting Language Models)")
            self.status.error = str(e)
            return False

    async def _start_impl(self) -> bool:
        """Start SEAL (Self-Adapting Language Models) operations."""
        if not self.seal_interface:
            return False

        try:
            # Test basic SEAL (Self-Adapting Language Models) functionality
            test_response = await self.seal_interface.submit("test prompt")
            if test_response:
                self.logger.info("SEAL (Self-Adapting Language Models) started successfully")
                return True
            else:
                self.logger.error("SEAL (Self-Adapting Language Models) start test failed")
                return False

        except Exception as e:
            self.logger.exception("Failed to start SEAL (Self-Adapting Language Models)")
            self.status.error = str(e)
            return False

    async def _stop_impl(self) -> bool:
        """Stop SEAL (Self-Adapting Language Models) operations."""
        try:
            # SEAL (Self-Adapting Language Models) is stateless, so stopping is just a state change
            self.logger.info("SEAL (Self-Adapting Language Models) operations stopped")
            return True

        except Exception as e:
            self.logger.exception("Error stopping SEAL (Self-Adapting Language Models)")
            return False

    async def _pause_impl(self) -> bool:
        """Pause SEAL (Self-Adapting Language Models) operations."""
        self.logger.info("SEAL (Self-Adapting Language Models) operations paused")
        return True

    async def _resume_impl(self) -> bool:
        """Resume SEAL (Self-Adapting Language Models) operations."""
        self.logger.info("SEAL (Self-Adapting Language Models) operations resumed")
        return True

    async def execute(self, operation: str, data: Any = None, **kwargs) -> ComponentResult:
        """
        Execute a SEAL (Self-Adapting Language Models)-specific operation.

        Supported operations:
        - submit_prompt: Submit a prompt to SEAL (Self-Adapting Language Models)
        - batch_submit: Submit multiple prompts
        - analyze_code: Analyze code using SEAL (Self-Adapting Language Models)
        - generate_code: Generate code using SEAL (Self-Adapting Language Models)
        - improve_code: Improve existing code using SEAL (Self-Adapting Language Models)
        - explain_code: Get code explanations from SEAL (Self-Adapting Language Models)
        - review_code: Get code reviews from SEAL (Self-Adapting Language Models)
        - optimize_prompt: Optimize prompt for better results
        """
        if not self.seal_interface:
            return ComponentResult(
                success=False,
                error="SEAL (Self-Adapting Language Models) interface not initialized",
            )

        start_time = asyncio.get_event_loop().time()

        try:
            result_data = None

            if operation == "submit_prompt":
                result_data = await self._submit_prompt(data, **kwargs)

            elif operation == "batch_submit":
                result_data = await self._batch_submit(data, **kwargs)

            elif operation == "analyze_code":
                result_data = await self._analyze_code(data, **kwargs)

            elif operation == "generate_code":
                result_data = await self._generate_code(data, **kwargs)

            elif operation == "improve_code":
                result_data = await self._improve_code(data, **kwargs)

            elif operation == "explain_code":
                result_data = await self._explain_code(data, **kwargs)

            elif operation == "review_code":
                result_data = await self._review_code(data, **kwargs)

            elif operation == "optimize_prompt":
                result_data = await self._optimize_prompt(data, **kwargs)

            else:
                return ComponentResult(success=False, error=f"Unknown operation: {operation}")

            execution_time = asyncio.get_event_loop().time() - start_time

            return ComponentResult(success=True, data=result_data, execution_time=execution_time)

        except Exception as e:
            execution_time = asyncio.get_event_loop().time() - start_time
            self.logger.exception(
                f"Error executing SEAL (Self-Adapting Language Models) operation: {operation}"
            )

            return ComponentResult(success=False, error=str(e), execution_time=execution_time)

    async def get_metrics(self) -> Dict[str, Any]:
        """Get SEAL (Self-Adapting Language Models)-specific metrics."""
        try:
            metrics = {
                "rate_limit_per_sec": self._rate_limit,
                "max_retries": self._max_retries,
                "retry_delay": self._retry_delay,
                "provider_type": type(self.provider).__name__ if self.provider else None,
            }

            # Add provider-specific metrics if available
            if hasattr(self.provider, 'get_metrics'):
                try:
                    provider_metrics = await self.provider.get_metrics()
                    metrics["provider_metrics"] = provider_metrics
                except Exception as e:
                    metrics["provider_metrics_error"] = str(e)

            return metrics

        except Exception as e:
            return {"error": str(e)}

    # Private methods for specific operations

    async def _submit_prompt(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Submit a single prompt to SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            prompt = data
        elif isinstance(data, dict):
            prompt = data.get("prompt")
        else:
            raise ValueError("Submit prompt requires a string prompt or dict with 'prompt' key")

        if not prompt:
            raise ValueError("Prompt is required")

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {"prompt": prompt, "response": response, "success": True}

    async def _batch_submit(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Submit multiple prompts to SEAL (Self-Adapting Language Models)."""
        if not isinstance(data, list):
            raise ValueError("Batch submit requires a list of prompts")

        results = []
        for i, prompt_data in enumerate(data):
            try:
                result = await self._submit_prompt(prompt_data, **kwargs)
                results.append(result)
            except Exception as e:
                results.append({"prompt": str(prompt_data), "error": str(e), "success": False})

        return {
            "results": results,
            "total": len(data),
            "successful": sum(1 for r in results if r.get("success", False)),
            "failed": sum(1 for r in results if not r.get("success", False)),
        }

    async def _analyze_code(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Analyze code using SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            code = data
        elif isinstance(data, dict):
            code = data.get("code")
        else:
            raise ValueError("Analyze code requires code string or dict with 'code' key")

        if not code:
            raise ValueError("Code is required for analysis")

        analysis_type = kwargs.get("analysis_type", "general")

        prompt = f"""
        Please analyze the following code for {analysis_type} aspects:

        ```
        {code}
        ```

        Provide insights on:
        - Code quality and structure
        - Potential improvements
        - Performance considerations
        - Security issues (if any)
        - Best practices compliance
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {"code": code, "analysis_type": analysis_type, "analysis": response, "success": True}

    async def _generate_code(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Generate code using SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            specification = data
        elif isinstance(data, dict):
            specification = data.get("specification")
        else:
            raise ValueError(
                "Generate code requires specification string or dict with 'specification' key"
            )

        if not specification:
            raise ValueError("Specification is required for code generation")

        language = kwargs.get("language", "python")
        style = kwargs.get("style", "clean and readable")

        prompt = f"""
        Please generate {language} code based on the following specification:

        {specification}

        Requirements:
        - Code should be {style}
        - Include appropriate comments
        - Follow best practices for {language}
        - Include error handling where appropriate
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {
            "specification": specification,
            "language": language,
            "generated_code": response,
            "success": True,
        }

    async def _improve_code(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Improve existing code using SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            code = data
        elif isinstance(data, dict):
            code = data.get("code")
        else:
            raise ValueError("Improve code requires code string or dict with 'code' key")

        if not code:
            raise ValueError("Code is required for improvement")

        improvement_focus = kwargs.get("focus", "performance and readability")

        prompt = f"""
        Please improve the following code focusing on {improvement_focus}:

        ```
        {code}
        ```

        Provide:
        1. The improved code
        2. Explanation of changes made
        3. Benefits of the improvements
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {
            "original_code": code,
            "improvement_focus": improvement_focus,
            "improved_code": response,
            "success": True,
        }

    async def _explain_code(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Get code explanations from SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            code = data
        elif isinstance(data, dict):
            code = data.get("code")
        else:
            raise ValueError("Explain code requires code string or dict with 'code' key")

        if not code:
            raise ValueError("Code is required for explanation")

        detail_level = kwargs.get("detail_level", "moderate")

        prompt = f"""
        Please explain the following code with {detail_level} detail:

        ```
        {code}
        ```

        Include:
        - What the code does
        - How it works
        - Key algorithms or patterns used
        - Input/output behavior
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {
            "code": code,
            "detail_level": detail_level,
            "explanation": response,
            "success": True,
        }

    async def _review_code(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Get code reviews from SEAL (Self-Adapting Language Models)."""
        if isinstance(data, str):
            code = data
        elif isinstance(data, dict):
            code = data.get("code")
        else:
            raise ValueError("Review code requires code string or dict with 'code' key")

        if not code:
            raise ValueError("Code is required for review")

        review_type = kwargs.get("review_type", "comprehensive")

        prompt = f"""
        Please provide a {review_type} code review for the following code:

        ```
        {code}
        ```

        Review aspects:
        - Code quality and maintainability
        - Performance considerations
        - Security vulnerabilities
        - Best practices compliance
        - Suggestions for improvement
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {"code": code, "review_type": review_type, "review": response, "success": True}

    async def _optimize_prompt(self, data: Any, **kwargs) -> Dict[str, Any]:
        """Optimize prompt for better results."""
        if isinstance(data, str):
            original_prompt = data
        elif isinstance(data, dict):
            original_prompt = data.get("prompt")
        else:
            raise ValueError("Optimize prompt requires prompt string or dict with 'prompt' key")

        if not original_prompt:
            raise ValueError("Original prompt is required")

        optimization_goal = kwargs.get("goal", "clarity and effectiveness")

        prompt = f"""
        Please optimize the following prompt for {optimization_goal}:

        Original prompt:
        {original_prompt}

        Provide:
        1. The optimized prompt
        2. Explanation of improvements made
        3. Expected benefits
        """

        response = await self.seal_interface.submit(prompt, **kwargs)

        return {
            "original_prompt": original_prompt,
            "optimization_goal": optimization_goal,
            "optimized_prompt": response,
            "success": True,
        }


def create_seal_adapter(
    provider_type: str = "default",
    provider_config: Optional[Dict[str, Any]] = None,
    rate_limit_per_sec: float = 1.0,
    max_retries: int = 3,
    retry_delay: float = 1.0,
    **kwargs,
) -> SEALAdapter:
    """
    Factory function to create a SEAL (Self-Adapting Language Models) adapter with standard configuration.

    Args:
        provider_type: Type of SEAL (Self-Adapting Language Models) provider to use
        provider_config: Configuration for the provider
        rate_limit_per_sec: Rate limit for API calls
        max_retries: Maximum number of retries
        retry_delay: Delay between retries
        **kwargs: Additional configuration options

    Returns:
        Configured SEALAdapter instance
    """
    config = ComponentConfig(
        component_type=ComponentType.SEAL,
        config={
            "provider_type": provider_type,
            "provider_config": provider_config or {},
            "rate_limit_per_sec": rate_limit_per_sec,
            "max_retries": max_retries,
            "retry_delay": retry_delay,
            **kwargs,
        },
    )

    return SEALAdapter(config)

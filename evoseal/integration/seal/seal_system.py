"""
SEAL (Self-Adapting Language Models) System

This module provides the main SEALSystem class that integrates all SEAL components
for knowledge-aware language model interactions with self-editing capabilities.
"""

from __future__ import annotations

import asyncio
import functools
import hashlib
import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, TypeVar, Union, cast

from pydantic import BaseModel, Field

from evoseal.integration.seal.exceptions import (
    KnowledgeBaseError,
    RateLimitError,
    RetryableError,
    SEALError,
    SelfEditingError,
    TemplateError,
    TimeoutError,
    ValidationError,
)
from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.metrics import Metrics
from evoseal.integration.seal.prompt import (
    PromptConstructor,
    PromptStyle,
    format_context,
    format_examples,
    format_knowledge,
    format_prompt,
)
from evoseal.integration.seal.self_editor.self_editor import SelfEditor
from evoseal.integration.seal.self_editor.strategies.knowledge_aware_strategy import (
    KnowledgeAwareStrategy,
)
from evoseal.integration.seal.utils.retry import retry

# Type variable for generic typing
T = TypeVar('T')

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Metrics collection for the SEAL system."""

    request_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    processing_times: List[float] = field(default_factory=list)
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record_processing_time(self, duration: float) -> None:
        """Record processing time for a request."""
        self.processing_times.append(duration)

    def record_error(self, error: Exception) -> None:
        """Record an error that occurred."""
        self.error_count += 1
        error_type = error.__class__.__name__
        self.errors_by_type[error_type] += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a summary of collected metrics."""
        return {
            'request_count': self.request_count,
            'error_count': self.error_count,
            'success_rate': (self.request_count - self.error_count) / max(1, self.request_count),
            'cache_hit_rate': self.cache_hits / max(1, self.cache_hits + self.cache_misses),
            'avg_processing_time': (
                sum(self.processing_times) / len(self.processing_times)
                if self.processing_times
                else 0
            ),
            'errors_by_type': dict(self.errors_by_type),
        }


class SEALSystem:
    """Main SEAL system class that integrates knowledge base, self-editing, and prompt construction.

    This class provides a unified interface for processing prompts with knowledge
    integration, self-editing capabilities, and intelligent prompt construction.

    Example:
        ```python
        # Initialize the system
        knowledge_base = KnowledgeBase()
        seal = SEALSystem(
            knowledge_base=knowledge_base,
            config=SEALSystem.Config(
                enable_self_editing=True,
                prompt_style="instruction"
            )
        )

        # Process a prompt
        response = await seal.process_prompt(
            "What is the capital of France?",
            context={"user_id": "example_user"}
        )
        ```
    """

    class Config(BaseModel):
        """Configuration for the SEAL system.

        Attributes:
            knowledge_base_max_results: Maximum number of knowledge base results to include in prompts
            knowledge_base_min_score: Minimum relevance score for knowledge base results (0.0-1.0)
            enable_self_editing: Whether to enable self-editing of model outputs
            self_editing_confidence_threshold: Minimum confidence score required to apply self-edits (0.0-1.0)
            prompt_style: Default prompt style (e.g., 'instruction', 'chat', 'completion')
            enable_caching: Whether to enable caching of knowledge base results and prompts
            cache_ttl_seconds: Time-to-live for cache entries in seconds
            max_cache_size: Maximum number of cache entries to store
            enable_template_caching: Whether to cache compiled prompt templates
            max_retries: Maximum number of retry attempts for operations
            retry_delay: Initial delay between retries in seconds
            timeout_seconds: Default timeout for operations in seconds
        """

        # Knowledge base settings
        knowledge_base_max_results: int = Field(
            default=5, description="Maximum number of knowledge base results to include in prompts"
        )
        knowledge_base_min_score: float = Field(
            default=0.5,
            ge=0.0,
            le=1.0,
            description="Minimum relevance score for knowledge base results (0.0-1.0)",
        )

        # Self-editing settings
        enable_self_editing: bool = Field(
            default=True, description="Whether to enable self-editing of model outputs"
        )
        self_editing_confidence_threshold: float = Field(
            default=0.7,
            ge=0.0,
            le=1.0,
            description="Minimum confidence score required to apply self-edits (0.0-1.0)",
        )

        # Prompt construction settings
        prompt_style: str = Field(
            default="instruction",
            description="Default prompt style (e.g., 'instruction', 'chat', 'completion')",
        )
        max_prompt_length: int = Field(
            default=4000, description="Maximum length of generated prompts in characters"
        )
        include_knowledge: bool = Field(
            default=True, description="Whether to include knowledge in prompts by default"
        )
        include_examples: bool = Field(
            default=True, description="Whether to include examples in prompts by default"
        )

        # Caching settings
        enable_caching: bool = Field(
            default=True,
            description="Whether to enable caching of knowledge base results and prompts",
        )
        cache_ttl_seconds: int = Field(
            default=3600, ge=0, description="Time-to-live for cache entries in seconds"
        )
        max_cache_size: int = Field(
            default=1000, ge=1, description="Maximum number of cache entries to store"
        )
        enable_template_caching: bool = Field(
            default=True, description="Whether to cache compiled prompt templates"
        )

        # Retry and timeout settings
        max_retries: int = Field(
            default=3, ge=0, description="Maximum number of retry attempts for operations"
        )
        retry_delay: float = Field(
            default=0.1, ge=0.0, description="Initial delay between retries in seconds"
        )
        timeout_seconds: float = Field(
            default=30.0, gt=0.0, description="Default timeout for operations in seconds"
        )

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        config: Optional[Config] = None,
        prompt_constructor: Optional[PromptConstructor] = None,
        self_editor: Optional[SelfEditor] = None,
    ) -> None:
        """Initialize the SEAL system.

        Args:
            knowledge_base: The knowledge base to use for retrieving context
            config: Configuration for the SEAL system
            prompt_constructor: Optional custom prompt constructor
            self_editor: Optional custom self-editor

        Example:
            ```python
            # Initialize with default configuration
            knowledge_base = KnowledgeBase()
            seal = SEALSystem(knowledge_base)

            # Or with custom configuration
            config = SEALSystem.Config(
                enable_self_editing=True,
                prompt_style="chat",
                max_retries=5
            )
            seal = SEALSystem(knowledge_base, config=config)
            ```
        """
        self.knowledge_base = knowledge_base
        self.config = config or self.Config()
        self.prompt_constructor = prompt_constructor or PromptConstructor()
        self.self_editor = self_editor or SelfEditor(
            strategy=KnowledgeAwareStrategy(knowledge_base)
        )

        # Initialize caches and monitoring
        self._cache: Dict[str, Any] = {}
        self._template_cache: Dict[str, Any] = {}
        self._last_accessed: Dict[str, float] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0
        self.metrics = Metrics()
        self._cleanup_task: Optional[asyncio.Task] = None

        # Start background tasks if needed
        if self.config.enable_caching and self.config.cache_ttl_seconds > 0:
            self._start_background_tasks()

    def _start_background_tasks(self) -> None:
        """Start background tasks for cache cleanup and monitoring."""
        loop = asyncio.get_event_loop()
        self._cleanup_task = loop.create_task(self._periodic_cleanup())

    async def _periodic_cleanup(self) -> None:
        """Periodically clean up expired cache entries."""
        while True:
            try:
                await self._cleanup_cache()
                await asyncio.sleep(
                    min(300, self.config.cache_ttl_seconds // 2)
                )  # Cleanup at least every 5min or half TTL
            except Exception as e:
                logger.error(f"Error during cache cleanup: {e}")
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _cleanup_cache(self) -> None:
        """Remove expired cache entries."""
        if not self.config.enable_caching:
            return

        now = time.time()
        expired = []

        # Clean template cache
        expired_templates = [
            key
            for key, last_access in self._last_accessed.items()
            if now - last_access > self.config.cache_ttl_seconds
        ]

        for key in expired_templates:
            self._template_cache.pop(key, None)
            self._last_accessed.pop(key, None)

        # Clean response cache
        expired_responses = [
            key
            for key, timestamp in self._cache_timestamps.items()
            if now - timestamp > self.config.cache_ttl_seconds
        ]

        for key in expired_responses:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

        total_expired = len(expired_templates) + len(expired_responses)
        if total_expired > 0:
            logger.debug(f"Cleaned up {total_expired} expired cache entries")

    @retry(max_retries=3, initial_delay=0.1, backoff_factor=2)
    async def _get_cached_template(self, template_name: str) -> Optional[Any]:
        """Get a compiled template from cache if available and caching is enabled.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            The compiled template if found in cache and caching is enabled, else None

        Raises:
            TemplateError: If there's an error loading the template
            RateLimitError: If rate limits are exceeded
            TimeoutError: If the operation times out
        """
        try:
            if not self.config.enable_template_caching or not self.config.enable_caching:
                return None

            # Check if template is in cache and not expired
            if template_name in self._template_cache:
                self.metrics.cache_hits += 1
                self._last_accessed[template_name] = time.time()
                return self._template_cache[template_name]

            self.metrics.cache_misses += 1
            return None

        except Exception as e:
            self.metrics.record_error(e)
            if isinstance(e, (RateLimitError, TimeoutError, RetryableError)):
                raise
            raise TemplateError(f"Error getting cached template: {e}") from e

    async def _cleanup_cache(self) -> None:
        """Remove expired cache entries."""
        if not self.config.enable_caching:
            return

        now = time.time()

        # Clean template cache
        expired_templates = [
            key
            for key, last_access in self._last_accessed.items()
            if now - last_access > self.config.cache_ttl_seconds
        ]

        for key in expired_templates:
            self._template_cache.pop(key, None)
            self._last_accessed.pop(key, None)

        # Clean response cache
        expired_responses = [
            key
            for key, timestamp in self._cache_timestamps.items()
            if now - timestamp > self.config.cache_ttl_seconds
        ]

        for key in expired_responses:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)

        total_expired = len(expired_templates) + len(expired_responses)
        if total_expired > 0:
            logger.debug(f"Cleaned up {total_expired} expired cache entries")

    async def process_prompt(
        self,
        prompt_text: str,
        context: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Process a prompt with knowledge integration and optional self-editing.

        This is the main entry point for the SEAL system. It handles the full
        pipeline from prompt construction to response generation and self-editing.

        Args:
            prompt_text: The input prompt text to process
            context: Optional context dictionary for the prompt
            template_name: Optional name of the prompt template to use
            **kwargs: Additional keyword arguments for prompt construction

        Returns:
            The processed response text

        Raises:
            SEALError: For general SEAL system errors
            ValidationError: If input validation fails
            RateLimitError: If rate limits are exceeded
            TimeoutError: If the operation times out
        """
        start_time = time.time()
        self.metrics.request_count += 1

        try:
            # Validate inputs
            if not prompt_text or not isinstance(prompt_text, str):
                raise ValidationError("Prompt text must be a non-empty string")

            # Get or create context
            context = context or {}
            context.setdefault("timestamp", datetime.utcnow().isoformat())

            # Get relevant knowledge
            knowledge = await self._get_relevant_knowledge(prompt_text, context)

            # Construct the prompt
            prompt = await self.construct_prompt(
                prompt_text,
                knowledge=knowledge,
                context=context,
                template_name=template_name,
                **kwargs,
            )

            # Generate initial response
            response = await self._generate_response(prompt, context)

            # Apply self-editing if enabled
            if self.config.enable_self_editing:
                response = await self._apply_self_editing(
                    prompt_text=prompt_text, response=response, knowledge=knowledge, context=context
                )

            # Record metrics
            duration = time.time() - start_time
            self.metrics.record_processing_time(duration)

            return response

        except Exception as e:
            self.metrics.record_error(e)
            if isinstance(e, SEALError):
                raise
            raise SEALError(f"Error processing prompt: {e}") from e

    @retry(max_retries=3, initial_delay=0.1, backoff_factor=2)
    async def _get_relevant_knowledge(
        self, query: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge for a query.

        Args:
            query: The query to retrieve knowledge for
            context: Context for the query

        Returns:
            List of relevant knowledge items

        Raises:
            KnowledgeBaseError: If there's an error retrieving knowledge
            RateLimitError: If rate limits are exceeded
            TimeoutError: If the operation times out
        """
        try:
            # Check cache first if enabled
            cache_key = self._get_cache_key("knowledge", query, context)
            if self.config.enable_caching and cache_key in self._cache:
                self.metrics.cache_hits += 1
                return self._cache[cache_key]

            self.metrics.cache_misses += 1

            # Query the knowledge base
            results = await self.knowledge_base.search(
                query=query,
                max_results=self.config.knowledge_base_max_results,
                min_score=self.config.knowledge_base_min_score,
                context=context,
            )

            # Cache the results
            if self.config.enable_caching:
                self._cache[cache_key] = results
                self._cache_timestamps[cache_key] = time.time()

                # Enforce max cache size
                if len(self._cache) > self.config.max_cache_size:
                    await self._cleanup_cache()

            return results

        except Exception as e:
            self.metrics.record_error(e)
            if isinstance(e, (RateLimitError, TimeoutError, RetryableError)):
                raise
            raise KnowledgeBaseError(f"Error retrieving knowledge: {e}") from e

    async def _apply_self_editing(
        self,
        prompt_text: str,
        response: str,
        knowledge: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """Apply self-editing to the response if confidence is high enough.

        Args:
            prompt_text: The original prompt text
            response: The initial response to edit
            knowledge: Relevant knowledge for context
            context: Additional context

        Returns:
            The edited response if confidence is high enough, else the original response
        """
        try:
            # Skip if self-editing is disabled
            if not self.config.enable_self_editing:
                return response

            # Check if we should apply self-editing
            edit_result = await self.self_editor.edit(
                prompt=prompt_text, response=response, knowledge=knowledge, context=context
            )

            # Only apply the edit if confidence is above threshold
            if edit_result.confidence >= self.config.self_editing_confidence_threshold:
                return edit_result.edited_response

            return response

        except Exception as e:
            self.metrics.record_error(e)
            logger.warning(f"Error during self-editing: {e}")
            return response  # Fall back to original response on error

    def _get_cache_key(self, prefix: str, *args) -> str:
        """Generate a cache key from the given arguments."""
        key_parts = [prefix] + [str(arg) for arg in args]
        key_str = "::".join(key_parts).encode('utf-8')
        return hashlib.sha256(key_str).hexdigest()

    async def _generate_response(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate a response using the language model.

        Args:
            prompt: The prompt to generate a response for
            context: Context for the generation

        Returns:
            The generated response text

        Raises:
            SEALError: If there's an error generating the response
        """
        # This is a placeholder implementation that should be replaced with
        # actual LLM integration in a real implementation
        try:
            # In a real implementation, this would call an LLM API
            # For example:
            # response = await self.llm_client.generate(
            #     prompt=prompt,
            #     max_tokens=self.config.max_tokens,
            #     temperature=self.config.temperature,
            #     **context
            # )
            # return response.text

            # For now, just return a placeholder response
            return "This is a placeholder response. Implement LLM integration to generate actual responses."

        except Exception as e:
            self.metrics.record_error(e)
            raise SEALError(f"Error generating response: {e}") from e

    async def construct_prompt(
        self,
        prompt_text: str,
        knowledge: Optional[List[Dict[str, Any]]] = None,
        context: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Construct a prompt with knowledge and context.

        Args:
            prompt_text: The base prompt text
            knowledge: Optional list of knowledge items to include
            context: Optional context for prompt construction
            template_name: Optional name of the template to use
            **kwargs: Additional keyword arguments for prompt construction

        Returns:
            The constructed prompt as a string

        Raises:
            TemplateError: If there's an error with the template
        """
        try:
            # Get the template if specified
            template = None
            if template_name:
                template = await self._get_cached_template(template_name)
                if not template:
                    raise TemplateError(f"Template not found: {template_name}")

            # Format the knowledge if provided
            formatted_knowledge = ""
            if knowledge and self.config.include_knowledge:
                formatted_knowledge = format_knowledge(knowledge)

            # Format the context
            formatted_context = format_context(context or {})

            # Construct the prompt
            if template:
                return template.format(
                    prompt=prompt_text,
                    knowledge=formatted_knowledge,
                    context=formatted_context,
                    **kwargs,
                )
            else:
                # Default prompt construction
                return format_prompt(
                    prompt_text, knowledge=formatted_knowledge, context=formatted_context, **kwargs
                )

        except Exception as e:
            self.metrics.record_error(e)
            if isinstance(e, TemplateError):
                raise
            raise TemplateError(f"Error constructing prompt: {e}") from e


def example_usage() -> None:
    """Example usage of the SEAL system."""
    import asyncio

    from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase

    async def run_example():
        # Initialize the knowledge base
        knowledge_base = KnowledgeBase()

        # Create a SEAL system instance with default config
        seal = SEALSystem(knowledge_base)

        # Process a prompt
        try:
            response = await seal.process_prompt(
                "What is the capital of France?", context={"user_id": "example_user"}
            )
            print(f"Response: {response}")

            # Print metrics
            print("\nMetrics:")
            metrics = seal.metrics.get_metrics_summary()
            for key, value in metrics.items():
                print(f"{key}: {value}")

        except Exception as e:
            print(f"Error: {e}")

    # Run the example
    asyncio.run(run_example())


if __name__ == "__main__":
    example_usage()

    @retry(max_retries=3, initial_delay=0.1, backoff_factor=2)
    async def _get_cached_template(self, template_name: str) -> Optional[Any]:
        """Get a compiled template from cache if available and caching is enabled.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            The compiled template if found in cache and caching is enabled, else None

        Raises:
            TemplateError: If there's an error loading the template
            RateLimitError: If rate limits are exceeded
            TimeoutError: If the operation times out
        """
        try:
            if not self.config.enable_template_caching or not self.config.enable_caching:
                return None

            # Check if template is in cache and not expired
            if template_name in self._template_cache:
                self.metrics.cache_hits += 1
                self._last_accessed[template_name] = time.time()
                return self._template_cache[template_name]

            self.metrics.cache_misses += 1
            return None

        except Exception as e:
            self.metrics.record_error(e)
            if isinstance(e, (RateLimitError, TimeoutError, RetryableError)):
                raise
            raise TemplateError(f"Error getting cached template: {e}") from e

    async def process_prompt(
        self,
        prompt_text: str,
        context: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """Process a prompt with knowledge integration and optional self-editing.

        Args:
            prompt_text: The input prompt text to process
            context: Optional context dictionary for the prompt
            template_name: Optional name of the template to use
            **kwargs: Additional arguments for prompt construction

        Returns:
            Dictionary containing the response and metadata

        Example:
            ```python
            response = await seal.process_prompt(
                "What is the capital of France?",
                context={"user_id": "123"},
                template_name="qa"
            )
            print(response["response"])
            ```
        """
        start_time = time.time()
        context = context or {}

        try:
            # 1. Get relevant knowledge
            knowledge = await self._retrieve_knowledge(prompt_text, context)

            # 2. Construct the prompt
            prompt = await self._construct_prompt(
                prompt_text,
                knowledge=knowledge,
                context=context,
                template_name=template_name,
                **kwargs,
            )

            # 3. Generate initial response
            response = await self._generate_response(prompt, context)

            # 4. Apply self-editing if enabled
            if self.config.enable_self_editing:
                response = await self._apply_self_editing(prompt_text, response, knowledge, context)

            # 5. Record success metrics
            self._record_metrics("process_prompt", time.time() - start_time, success=True)

            return {
                "response": response,
                "knowledge": knowledge,
                "metadata": {
                    "processing_time": time.time() - start_time,
                    "template_used": template_name,
                    "self_edited": self.config.enable_self_editing,
                },
            }

        except Exception as e:
            self._record_metrics("process_prompt", time.time() - start_time, False, e)
            raise

    async def _retrieve_knowledge(
        self, query: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant knowledge for a query."""
        try:
            return await self.knowledge_base.search(
                query=query,
                max_results=self.config.knowledge_base_max_results,
                min_score=self.config.knowledge_base_min_score,
                **context.get("knowledge_search", {}),
            )
        except Exception as e:
            logger.warning(f"Error retrieving knowledge: {e}")
            return []

    async def _construct_prompt(
        self,
        prompt_text: str,
        knowledge: List[Dict[str, Any]],
        context: Dict[str, Any],
        template_name: Optional[str] = None,
        **kwargs,
    ) -> str:
        """Construct a prompt with knowledge and context."""
        try:
            # Get or create template
            template = None
            if template_name:
                template = await self._get_cached_template(template_name)

            # Format the prompt
            return await self.prompt_constructor.construct(
                prompt_text, knowledge=knowledge, context=context, template=template, **kwargs
            )
        except Exception as e:
            logger.error(f"Error constructing prompt: {e}")
            # Fallback to simple prompt if construction fails
            return f"{prompt_text}\n\nContext: {context}"

    async def _generate_response(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate a response using the language model."""
        # This is a placeholder - in a real implementation, this would call an LLM API
        # For example: return await self.llm_client.generate(prompt, **context)
        return f"Generated response for: {prompt[:50]}..."

    async def _apply_self_editing(
        self,
        original_prompt: str,
        response: str,
        knowledge: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> str:
        """Apply self-editing to the response if confidence is sufficient."""
        try:
            # Check if we should apply self-editing
            if not self.self_editor or not self.config.enable_self_editing:
                return response

            # Get edit suggestions
            edit_result = await self.self_editor.suggest_edits(
                prompt=original_prompt, response=response, knowledge=knowledge, context=context
            )

            # Only apply if confidence is above threshold
            if edit_result.confidence >= self.config.self_editing_confidence_threshold:
                return edit_result.edited_text

            return response

        except Exception as e:
            logger.warning(f"Error during self-editing: {e}")
            return response  # Return original response on error

        self._template_cache[template_name] = template

        # Enforce max cache size
        if len(self._template_cache) > self.config.max_cache_size:
            # Remove the oldest item
            oldest_key = next(iter(self._template_cache))
            del self._template_cache[oldest_key]

    async def construct_prompt(
        self,
        user_input: str,
        template_name: Optional[str] = None,
        knowledge: Optional[Any] = None,
        examples: Optional[Any] = None,
        context: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> str:
        """
        Construct a prompt with integrated knowledge and examples.

        Args:
            user_input: The user's input or question
            template_name: Optional name of a registered template to use
            knowledge: Optional knowledge to include in the prompt
            examples: Optional examples to include
            context: Additional context for the prompt
            **kwargs: Additional template variables

        Returns:
            Formatted prompt string
        """
        context = context or {}

        # Retrieve knowledge if not provided and knowledge inclusion is enabled
        if knowledge is None and self.config.include_knowledge:
            try:
                knowledge = await self.retrieve_relevant_knowledge(user_input)
            except Exception as e:
                logger.warning(f"Error retrieving knowledge for prompt: {str(e)}")
                knowledge = []

        # Prepare template variables
        template_vars = {
            "question": user_input,
            "user_input": user_input,
            "knowledge": knowledge,
            "examples": examples if self.config.include_examples else None,
            "context": context,
            "current_time": datetime.now().isoformat(),
            **kwargs,
        }

        # Use the specified template or default to basic instruction
        if template_name:
            try:
                # Try to get from cache first
                template = self._get_cached_template(template_name)
                if template is None:
                    template = self.prompt_constructor.get_template(template_name)
                    self._cache_template(template_name, template)

                # Format the prompt with the template
                prompt = self.prompt_constructor.create_prompt(
                    template_name,
                    **{k: v for k, v in template_vars.items() if k in template.required_fields},
                )
            except Exception as e:
                logger.warning(
                    f"Error using template '{template_name}': {str(e)}. Using default format."
                )
                prompt = user_input
        else:
            # Use default formatting
            prompt = format_prompt(
                template=user_input,
                knowledge=knowledge,
                examples=examples if self.config.include_examples else None,
                context=context,
                **kwargs,
            )

        # Ensure prompt doesn't exceed maximum length
        if len(prompt) > self.config.max_prompt_length:
            logger.warning(
                "Prompt length %d exceeds maximum length %d. Truncating...",
                len(prompt),
                self.config.max_prompt_length,
            )
            prompt = prompt[: self.config.max_prompt_length - 3] + "..."

        return prompt

    async def process_prompt(
        self,
        prompt: str,
        context: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        examples: Optional[Any] = None,
        **kwargs: Any,
    ) -> str:
        """
        Process a prompt with knowledge integration and self-editing.

        Args:
            prompt: The input prompt to process
            context: Optional context dictionary with additional information
            template_name: Optional name of a registered template to use
            examples: Optional examples to include in the prompt
            **kwargs: Additional arguments to pass to the processing pipeline

        Returns:
            The processed response
        """
        context = context or {}

        try:
            # 1. Construct the prompt with knowledge and examples
            constructed_prompt = await self.construct_prompt(
                user_input=prompt,
                template_name=template_name,
                examples=examples,
                context=context,
                **kwargs,
            )

            # 2. Generate initial response (placeholder - will be implemented in next step)
            response = f"[RESPONSE TO: {constructed_prompt}]"

            # 3. Apply self-editing if enabled
            if self.config.enable_self_editing:
                response = await self.self_edit(response, context)

            return response

        except Exception as e:
            error_msg = f"I encountered an error: {str(e)}. Please try again later."
            logger.error(f"Error processing prompt: {str(e)}", exc_info=True)
            return error_msg

    async def retrieve_relevant_knowledge(
        self,
        query: str,
        max_results: Optional[int] = None,
        min_score: Optional[float] = None,
        **kwargs: Any,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant knowledge for a query with caching.

        Args:
            query: The query to search for
            max_results: Maximum number of results to return (overrides config)
            min_score: Minimum relevance score (overrides config)
            **kwargs: Additional arguments to pass to the knowledge base

        Returns:
            List of relevant knowledge items with scores and metadata

        Example:
            ```python
            knowledge = await seal_system.retrieve_relevant_knowledge(
                "What is machine learning?",
                max_results=3
            )
            ```
        """
        # Use config values if not overridden
        max_results = max_results or self.config.knowledge_base_max_results
        min_score = min_score or self.config.knowledge_base_min_score

        # Generate cache key
        cache_key = self._generate_cache_key("knowledge", query, max_results, min_score, **kwargs)

        # Check cache first
        if self.config.enable_caching:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                self._cache_hits += 1
                return cached

        self._cache_misses += 1

        try:
            # Search the knowledge base
            results = await self.knowledge_base.search(
                query=query, limit=max_results, min_score=min_score, **kwargs
            )

            # Cache the results
            if self.config.enable_caching:
                self._add_to_cache(cache_key, results)

            return results

        except Exception as e:
            logger.error(f"Error retrieving knowledge: {str(e)}", exc_info=True)
            raise

    async def self_edit(self, content: str, context: Dict[str, Any]) -> str:
        """
        Apply self-editing to the content.

        Args:
            content: The content to edit
            context: Context for the editing process

        Returns:
            The edited content
        """
        if not content or not self.config.enable_self_editing:
            return content

        try:
            # Get editing suggestions
            suggestions = await self.self_editor.evaluate_content(
                content=content, content_id=context.get("content_id", "default"), context=context
            )

            # Apply suggestions
            edited_content = content
            for suggestion in suggestions:
                if suggestion.confidence >= self.config.min_edit_confidence:
                    edited_content = await self.self_editor.apply_edit(
                        content_id=context.get("content_id", "default"),
                        suggestion=suggestion,
                        apply=True,
                    )

            return edited_content

        except Exception as e:
            logger.error(f"Error during self-editing: {str(e)}", exc_info=True)
            return content

    def _generate_cache_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """
        Generate a cache key from the given arguments.

        Args:
            prefix: A prefix for the cache key (e.g., 'knowledge', 'prompt')
            *args: Positional arguments to include in the key
            **kwargs: Keyword arguments to include in the key

        Returns:
            A hexadecimal MD5 hash of the key components

        Example:
            ```python
            key = self._generate_cache_key("knowledge", "query", max_results=5)
            ```
        """
        key_parts = [prefix] + [str(arg) for arg in args]
        if kwargs:
            key_parts.append("".join(f"{k}={v}" for k, v in sorted(kwargs.items())))
        return hashlib.md5("".join(key_parts).encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Any:
        """
        Get a value from the cache if it exists and is not expired.

        Args:
            key: The cache key to retrieve

        Returns:
            The cached value or None if not found or expired
        """
        if key not in self._cache or key not in self._cache_timestamps:
            return None

        # Check if the entry has expired
        if time.time() - self._cache_timestamps[key] > self.config.cache_ttl_seconds:
            del self._cache[key]
            del self._cache_timestamps[key]
            return None

        return self._cache[key]

    def _add_to_cache(self, key: str, value: Any) -> None:
        """
        Add a value to the cache.

        Args:
            key: The cache key
            value: The value to cache
        """
        if not self.config.enable_caching:
            return

        # Remove oldest entries if cache is full
        if len(self._cache) >= self.config.max_cache_size:
            # Remove the oldest item
            oldest_key = next(iter(self._cache_timestamps))
            del self._cache[oldest_key]
            del self._cache_timestamps[oldest_key]

        self._cache[key] = value
        self._cache_timestamps[key] = time.time()

    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics including hits, misses, and current size
        """
        return {
            "hits": self._cache_hits,
            "misses": self._cache_misses,
            "size": len(self._cache),
            "template_cache_size": len(self._template_cache),
            "hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0
            ),
        }

    def clear_cache(self) -> None:
        """Clear the cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


# Example usage
async def example_usage():
    """Example usage of the SEAL system."""
    from pathlib import Path

    # Initialize knowledge base
    knowledge_base = KnowledgeBase(storage_path=Path("knowledge_db"))

    # Initialize SEAL system
    config = SEALConfig(auto_apply_edits=True, min_confidence=0.7, max_knowledge_items=3)
    seal = SEALSystem(knowledge_base=knowledge_base, config=config)

    # Process a prompt
    response = await seal.process_prompt(
        "What is the capital of France?", context={"user_id": "example_user"}
    )
    print(f"Response: {response}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())

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
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union, cast

from pydantic import BaseModel, Field

from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
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

logger = logging.getLogger(__name__)


class SEALSystem:
    """Main SEAL system class that integrates knowledge base, self-editing, and prompt construction.

    This class provides a unified interface for processing prompts with knowledge
    integration, self-editing capabilities, and intelligent prompt construction.
    """

    class Config(BaseModel):
        """Configuration for the SEAL system."""

        # Knowledge base settings
        knowledge_base_max_results: int = Field(
            default=5, description="Maximum number of knowledge base results to include in prompts"
        )
        knowledge_base_min_score: float = Field(
            default=0.5, description="Minimum relevance score for knowledge base results"
        )

        # Self-editing settings
        enable_self_editing: bool = Field(
            default=True, description="Whether to enable self-editing of responses"
        )
        min_edit_confidence: float = Field(
            default=0.7, description="Minimum confidence score required to apply an edit"
        )

        # Prompt settings
        prompt_style: str = Field(
            default="instruction",
            description="Default prompt style to use (instruction, chat, completion, chain_of_thought)",
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
            default=3600, description="Time-to-live for cache entries in seconds"
        )
        max_cache_size: int = Field(
            default=1000, description="Maximum number of cache entries to store"
        )
        enable_template_caching: bool = Field(
            default=True, description="Whether to cache compiled prompt templates"
        )

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        self_editor: Optional[SelfEditor] = None,
        config: Optional[Config] = None,
        prompt_constructor: Optional[PromptConstructor] = None,
    ):
        """
        Initialize the SEAL system.

        Args:
            knowledge_base: Initialized knowledge base instance
            self_editor: Optional self-editor instance. If not provided, a default
                       KnowledgeAwareStrategy will be used.
            config: Optional configuration. If not provided, defaults will be used.
            prompt_constructor: Optional prompt constructor instance. If not provided,
                             a default one will be created.
        """
        self.knowledge_base = knowledge_base
        self.self_editor = self_editor or SelfEditor(
            strategy=KnowledgeAwareStrategy(self.knowledge_base)
        )
        self.config = config or SEALConfig()
        self.prompt_constructor = prompt_constructor or PromptConstructor(
            default_style=PromptStyle(self.config.prompt_style.lower())
        )

        # Initialize caches
        self._cache: Dict[str, Any] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Template cache for compiled prompt templates
        self._template_cache: Dict[str, str] = {}

        logger.info("SEALSystem initialized with config: %s", self.config.model_dump())

    @functools.lru_cache(maxsize=1000)
    def _get_cached_template(self, template_name: str) -> Optional[PromptTemplate]:
        """Get a template from cache if available and caching is enabled.

        Args:
            template_name: Name of the template to retrieve

        Returns:
            Cached template or None if not found or caching is disabled
        """
        if not self.config.enable_template_caching or not self.config.enable_caching:
            return None

        return self._template_cache.get(template_name)

    def _cache_template(self, template_name: str, template: str) -> None:
        """Cache a template if caching is enabled.

        Args:
            template_name: Name of the template to cache
            template: Template content to cache
        """
        if not self.config.enable_template_caching or not self.config.enable_caching:
            return

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

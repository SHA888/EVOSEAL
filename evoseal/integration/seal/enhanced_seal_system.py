"""
Enhanced SEAL (Self-Adapting Language Models) System

This module provides an enhanced version of the SEALSystem with improved configuration,
lifecycle management, and performance optimizations.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (
    Optional, Dict, List, Any, Union, Deque, Callable, Awaitable, AsyncGenerator, Tuple, Set, Type, TypeVar, cast
)

from pydantic import BaseModel, Field, field_validator, ConfigDict

from evoseal.integration.seal.exceptions import SelfEditingError, ValidationError
from evoseal.integration.seal.knowledge.knowledge_base import KnowledgeBase
from evoseal.integration.seal.knowledge.mock_knowledge_base import MockKnowledgeBase
from evoseal.integration.seal.prompt import (
    PromptConstructor,
    PromptStyle,
    format_context,
    format_knowledge,
)

# Import mock implementations
from evoseal.integration.seal.self_editor.mock_self_editor import MockSelfEditor
from evoseal.integration.seal.self_editor.self_editor import SelfEditor
from evoseal.integration.seal.self_editor.strategies.knowledge_aware_strategy import (
    KnowledgeAwareStrategy,
)

# Type variable for generic typing
T = TypeVar("T")

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class Metrics:
    """Enhanced metrics collection for the SEAL system with additional tracking."""

    request_count: int = 0
    error_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    processing_times: List[float] = field(default_factory=list)
    errors_by_type: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    knowledge_retrieval_times: List[float] = field(default_factory=list)
    generation_times: List[float] = field(default_factory=list)
    self_editing_times: List[float] = field(default_factory=list)
    context_sizes: List[int] = field(default_factory=list)
    response_lengths: List[int] = field(default_factory=list)

    def record_processing_time(self, duration: float) -> None:
        """Record processing time for a request."""
        self.processing_times.append(duration)
        # Keep only the last 1000 measurements to prevent unbounded growth
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-1000:]

    def record_error(self, error: Exception) -> None:
        """Record an error that occurred."""
        self.error_count += 1
        error_type = error.__class__.__name__
        self.errors_by_type[error_type] += 1

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get a comprehensive summary of collected metrics."""

        def safe_avg(values: List[float]) -> float:
            return sum(values) / len(values) if values else 0.0

        return {
            "request_count": self.request_count,
            "error_count": self.error_count,
            "cache": {
                "hits": self.cache_hits,
                "misses": self.cache_misses,
                "hit_rate": (
                    self.cache_hits / (self.cache_hits + self.cache_misses)
                    if (self.cache_hits + self.cache_misses) > 0
                    else 0.0
                ),
            },
            "timing": {
                "avg_processing_time": safe_avg(self.processing_times),
                "avg_knowledge_retrieval_time": safe_avg(self.knowledge_retrieval_times),
                "avg_generation_time": safe_avg(self.generation_times),
                "avg_self_editing_time": safe_avg(self.self_editing_times),
            },
            "sizes": {
                "avg_context_size": (safe_avg(self.context_sizes) if self.context_sizes else 0),
                "avg_response_length": (
                    safe_avg(self.response_lengths) if self.response_lengths else 0
                ),
            },
            "errors_by_type": dict(self.errors_by_type),
        }


class SEALConfig(BaseModel):
    """Configuration for the EnhancedSEALSystem."""

    # Knowledge base configuration
    knowledge_base_path: str = "knowledge_db"
    max_knowledge_entries: int = 5
    knowledge_similarity_threshold: float = 0.3
    enable_knowledge_caching: bool = True
    knowledge_cache_ttl: int = 3600  # 1 hour

    # Self-editing configuration
    enable_self_editing: bool = True
    min_confidence_for_editing: float = 0.7
    max_self_edit_attempts: int = 3
    enable_confidence_based_editing: bool = True

    # Prompt construction
    default_prompt_style: PromptStyle = PromptStyle.INSTRUCTION
    max_context_length: int = 4000
    max_history_length: int = 10
    enable_dynamic_context: bool = True

    # Performance settings
    enable_async_processing: bool = True
    batch_size: int = 8
    max_concurrent_requests: int = 10
    request_timeout: int = 30  # seconds

    # Caching
    enable_caching: bool = True
    cache_ttl_seconds: int = 300  # 5 minutes
    max_cache_size: int = 1000

    # Monitoring and metrics
    enable_metrics: bool = True
    metrics_retention_days: int = 7

    @field_validator("knowledge_similarity_threshold")
    @classmethod
    def validate_similarity_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("knowledge_similarity_threshold must be between 0.0 and 1.0")
        return v

    @field_validator("min_confidence_for_editing")
    @classmethod
    def validate_confidence_threshold(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("min_confidence_for_editing must be between 0.0 and 1.0")
        return v


class ConversationHistory:
    """Manages conversation history for context-aware interactions."""

    def __init__(self, max_history: int = 10):
        self.max_history = max_history
        self.history: Deque[Dict[str, Any]] = deque(maxlen=max_history)
        self._current_session_id: Optional[str] = None

    def add_message(
        self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add a message to the conversation history."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.history.append(message)

    def get_history(self, max_messages: Optional[int] = None) -> List[Dict[str, Any]]:
        """Retrieve conversation history, optionally limited to a number of messages."""
        history = list(self.history)
        if max_messages is not None:
            history = history[-max_messages:]
        return history

    def clear(self) -> None:
        """Clear the conversation history."""
        self.history.clear()

    def set_session_id(self, session_id: str) -> None:
        """Set the current session ID."""
        self._current_session_id = session_id

    def get_session_id(self) -> Optional[str]:
        """Get the current session ID."""
        return self._current_session_id


class EnhancedSEALSystem:
    """
    Enhanced SEAL system with improved configuration, lifecycle management,
    and performance optimizations.
    """

    def __init__(
        self,
        config: Optional[Union[Dict[str, Any], SEALConfig]] = None,
        knowledge_base: Optional[Any] = None,  # Use Any to accept both real and mock
        prompt_constructor: Optional[PromptConstructor] = None,
        self_editor: Optional[Any] = None,  # Use Any to accept both real and mock
    ) -> None:
        """
        Initialize the EnhancedSEALSystem.

        Args:
            config: Configuration dictionary or SEALConfig instance
            knowledge_base: Optional pre-initialized KnowledgeBase instance or mock
            prompt_constructor: Optional custom PromptConstructor
            self_editor: Optional custom SelfEditor instance or mock
        """
        # Initialize configuration
        self.config = config if isinstance(config, SEALConfig) else SEALConfig(**(config or {}))

        # Initialize core components with mock implementations by default
        self.knowledge_base = knowledge_base or MockKnowledgeBase()
        self.self_editor = self_editor or MockSelfEditor()
        self.prompt_constructor = prompt_constructor or PromptConstructor()

        # Initialize conversation management
        self.conversation_history = ConversationHistory(max_history=self.config.max_history_length)

        # Initialize metrics and monitoring
        self.metrics = Metrics() if self.config.enable_metrics else None
        self._startup_time = datetime.now(timezone.utc)

        # Initialize caches
        self._cache: Dict[str, Any] = {}
        self._template_cache: Dict[str, Any] = {}
        self._last_accessed: Dict[str, float] = {}
        self._cache_timestamps: Dict[str, float] = {}

        # Background tasks
        self._background_tasks: List[asyncio.Task] = []
        self._shutdown_event = asyncio.Event()
        self._is_running = False

        # Performance optimization
        self._request_semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)
        self._batch_queue: asyncio.Queue = asyncio.Queue()

        logger.info("EnhancedSEALSystem initialized with config: %s", self.config.model_dump())

    async def start(self) -> None:
        """Start the SEAL system and any background tasks."""
        if self._is_running:
            logger.warning("SEAL system is already running")
            return

        self._is_running = True
        self._shutdown_event.clear()

        # Start background tasks
        if self.config.enable_async_processing:
            self._background_tasks.append(asyncio.create_task(self._process_batch_queue()))

        logger.info("EnhancedSEALSystem started")

    async def stop(self) -> None:
        """Stop the SEAL system and clean up resources."""
        if not self._is_running:
            return

        self._is_running = False
        self._shutdown_event.set()

        # Cancel all background tasks
        for task in self._background_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self._background_tasks.clear()
        logger.info("EnhancedSEALSystem stopped")

    async def __aenter__(self) -> "EnhancedSEALSystem":
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Async context manager exit."""
        await self.stop()

    async def process_prompt(
        self,
        prompt_text: str,
        context: Optional[Dict[str, Any]] = None,
        template_name: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Process a prompt with knowledge integration and optional self-editing.

        Args:
            prompt_text: The input prompt text to process
            context: Optional context dictionary for the prompt
            template_name: Optional name of the template to use
            **kwargs: Additional arguments for prompt construction

        Returns:
            Dictionary containing the response and metadata

        Raises:
            ValueError: If prompt_text is empty or contains only whitespace
        """
        # Input validation
        if not prompt_text or not prompt_text.strip():
            if self.metrics:
                self.metrics.request_count += 1
                self.metrics.record_error(ValueError("Empty prompt text"))
            raise ValueError("Prompt text cannot be empty")

        context = context or {}
        start_time = time.time()

        try:

            # Check cache if enabled
            cache_key = self._generate_cache_key(
                "prompt", prompt_text, context or {}, template_name or "default"
            )
            if self.config.enable_caching:
                cached = self._get_from_cache(cache_key)
                if cached is not None:
                    if self.metrics:
                        self.metrics.cache_hits += 1
                    # Return a copy to prevent modification of cached data
                    return {
                        "response": cached["response"],
                        "metadata": {**cached["metadata"], "cached": True},
                    }

            # Retrieve relevant knowledge
            knowledge_start = time.time()
            knowledge = await self.retrieve_relevant_knowledge(prompt_text, context or {})
            knowledge_time = time.time() - knowledge_start

            # Record knowledge retrieval metrics
            if self.metrics:
                self.metrics.knowledge_retrieval_times.append(knowledge_time)

            # Construct the prompt
            prompt = await self._construct_prompt(
                prompt_text,
                knowledge,
                context or {},
                template_name=template_name,
                **{k: v for k, v in kwargs.items() if k != "template"},
            )

            # Generate response
            gen_start = time.time()
            response = await self._generate_response(prompt, context or {})
            gen_time = time.time() - gen_start

            # Apply self-editing if enabled
            edits_applied = False
            edits = []
            if self.config.enable_self_editing:
                edit_start = time.time()
                edit_result = await self._apply_self_editing(
                    prompt_text, response, knowledge, context or {}
                )
                if isinstance(edit_result, tuple) and len(edit_result) == 2:
                    response, edits = edit_result
                    edits_applied = len(edits) > 0
                else:
                    # Handle case where _apply_self_editing returns just the response
                    response = edit_result
                if self.metrics:
                    self.metrics.self_editing_times.append(time.time() - edit_start)

            # Ensure response is a string for metrics and history
            if asyncio.iscoroutine(response):
                response = await response

            # Calculate total processing time
            processing_time = time.time() - start_time

            # Update metrics
            if self.metrics:
                self.metrics.request_count += 1
                self.metrics.processing_times.append(processing_time)
                self.metrics.generation_times.append(gen_time)
                self.metrics.context_sizes.append(len(str(context or {})))
                self.metrics.response_lengths.append(len(str(response)))

            # Prepare the result
            result = {
                "response": response,
                "metadata": {
                    "knowledge_used": [k.get("id") for k in knowledge],
                    "self_edits_applied": edits_applied,
                    "success": True,
                    "processing_time": processing_time,
                    "generation_time": gen_time,
                    "cached": False,  # Explicitly set cached flag
                },
            }

            # Add to conversation history
            self.conversation_history.add_message(
                "assistant",
                response,
                {
                    "knowledge_used": [k.get("id") for k in knowledge],
                    "edits_applied": edits,
                },
            )

            # Cache the result if enabled and not already cached
            if self.config.enable_caching and not result["metadata"].get("cached", False):
                # Create a cache entry without the cached flag
                cache_entry = {
                    "response": result["response"],
                    "metadata": {k: v for k, v in result["metadata"].items() if k != "cached"},
                }
                self._add_to_cache(cache_key, cache_entry)

            return result

        except Exception as e:
            logger.error(f"Error processing prompt: {e}", exc_info=True)
            if self.metrics:
                self.metrics.record_error(e)

            # Return error response
            return {
                "response": "An error occurred while processing your request.",
                "metadata": {"success": False, "error": str(e), "cached": False},
            }

    async def retrieve_relevant_knowledge(
        self,
        query: str,
        context: Dict[str, Any],
        max_results: Optional[int] = None,
        min_score: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant knowledge for a query with caching and context awareness.
        """
        max_results = max_results or self.config.max_knowledge_entries
        min_score = min_score or self.config.knowledge_similarity_threshold

        # Generate cache key
        cache_key = self._generate_cache_key("knowledge", query, max_results, min_score)

        # Check cache
        if self.config.enable_knowledge_caching:
            cached = self._get_from_cache(cache_key)
            if cached is not None:
                if self.metrics:
                    self.metrics.cache_hits += 1
                return cached

        try:
            # Call knowledge base
            knowledge = await self.knowledge_base.search(
                query=query,
                max_results=max_results,
                min_score=min_score,
                context=context,
            )

            # Cache the result
            if self.config.enable_knowledge_caching:
                self._add_to_cache(cache_key, knowledge, ttl=self.config.knowledge_cache_ttl)

            return knowledge

        except Exception as e:
            logger.error(f"Error retrieving knowledge: {e}")
            if self.metrics:
                self.metrics.record_error(e)
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
            # Get template if specified
            template = None
            if template_name:
                template = await self._get_cached_template(template_name)

            # Format knowledge and context
            formatted_knowledge = format_knowledge(knowledge)
            formatted_context = format_context(context)

            # Construct the prompt - ensure prompt_text is passed as 'text' parameter
            prompt = format_prompt(
                template=template if template else "{text}",
                text=prompt_text,
                knowledge=formatted_knowledge,
                context=formatted_context,
                **{
                    k: v for k, v in kwargs.items() if k != "template"
                },  # Avoid duplicate 'template' parameter
            )

            return prompt

        except Exception as e:
            logger.error(f"Error constructing prompt: {e}")
            if self.metrics:
                self.metrics.record_error(e)
            raise

    async def _generate_response(self, prompt: str, context: Dict[str, Any]) -> str:
        """Generate a response using the configured language model."""
        # This is a placeholder implementation
        # In a real implementation, this would call an LLM API
        return f"Generated response for: {prompt[:50]}..."

    async def _apply_self_editing(
        self,
        original_prompt: str,
        response: str,
        knowledge: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """Apply self-editing to the response if confidence is sufficient."""
        if not self.config.enable_self_editing:
            return response, []

        try:
            # Ensure response is a string before processing
            if asyncio.iscoroutine(response):
                response = await response

            # Get suggested edits
            edit_suggestions = await self.self_editor.suggest_edits(
                prompt=original_prompt,
                response=response,
                knowledge=knowledge,
                context=context,
            )

            if not edit_suggestions:
                return response, []

            # Apply edits with sufficient confidence
            applied_edits = []
            for edit in edit_suggestions:
                if not isinstance(edit, dict):
                    continue

                confidence = edit.get("confidence", 0.0)
                if confidence >= self.config.min_confidence_for_editing:
                    try:
                        # Ensure we await the coroutine if apply_edit is async
                        edit_result = self.self_editor.apply_edit(
                            text=response,
                            edit_suggestion=edit,
                            **{"context": context},  # Pass context as a keyword argument
                        )
                        if asyncio.iscoroutine(edit_result):
                            response = await edit_result
                        else:
                            response = edit_result

                        applied_edits.append(edit)
                        if len(applied_edits) >= self.config.max_self_edit_attempts:
                            break
                    except Exception as e:
                        logger.error(f"Failed to apply edit {edit.get('type', 'unknown')}: {e}")
                        continue

            return response, applied_edits

        except Exception as e:
            logger.error(f"Error in self-editing: {e}", exc_info=True)
            return response, []

    async def _process_batch_queue(self) -> None:
        """Process queued requests in batches for better throughput."""
        while not self._shutdown_event.is_set():
            try:
                # Wait for batch to be ready or shutdown
                batch = []
                while len(batch) < self.config.batch_size and not self._shutdown_event.is_set():
                    try:
                        # Wait for next item with timeout
                        item = await asyncio.wait_for(
                            self._batch_queue.get(),
                            timeout=0.1,  # Small timeout to check shutdown
                        )
                        batch.append(item)
                    except asyncio.TimeoutError:
                        if batch:  # If we have items, process them
                            break

                if not batch:
                    continue

                # Process the batch
                await self._process_batch(batch)

            except Exception as e:
                logger.error(f"Error in batch processing: {e}")
                if self.metrics:
                    self.metrics.record_error(e)
                await asyncio.sleep(1)  # Prevent tight loop on errors

    async def _process_batch(self, batch: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process a batch of requests with proper error handling and progress tracking.

        Args:
            batch: List of request dictionaries, each containing at least 'prompt_text' and 'context'

        Returns:
            List of processed responses with the same order as input batch

        Each request in the batch should have the following structure:
            {
                'prompt_text': str,  # The input text to process
                'context': Dict[str, Any],  # Context for the prompt
                'template_name': Optional[str],  # Optional template name
                'metadata': Dict[str, Any]  # Additional metadata for tracking
            }

        Returns responses in the format:
            {
                'success': bool,  # Whether processing was successful
                'response': Optional[str],  # The processed response if successful
                'error': Optional[str],  # Error message if processing failed
                'metadata': Dict[str, Any]  # Any additional metadata from processing
            }
        """
        if not batch:
            return []

        results = []

        for item in batch:
            try:
                # Extract request parameters with defaults
                prompt_text = item.get('prompt_text', '').strip()
                if not prompt_text:
                    raise ValueError("Empty prompt_text in batch item")

                context = item.get('context', {})
                template_name = item.get('template_name')
                metadata = item.get('metadata', {})

                # Process the prompt using the main processing pipeline
                result = await self.process_prompt(
                    prompt_text=prompt_text,
                    context=context,
                    template_name=template_name,
                    **metadata,
                )

                # Record successful processing
                results.append(
                    {
                        'success': True,
                        'response': result.get('response'),
                        'metadata': {
                            **result.get('metadata', {}),
                            'processed_at': datetime.now(timezone.utc).isoformat(),
                            'batch_size': len(batch),
                        },
                    }
                )

            except Exception as e:
                # Log the error and record metrics
                error_msg = str(e)
                logger.error(
                    "Error processing batch item: %s - %s",
                    type(e).__name__,
                    error_msg,
                    exc_info=logger.isEnabledFor(logging.DEBUG),
                )

                if self.metrics:
                    self.metrics.record_error(e)

                results.append(
                    {
                        'success': False,
                        'response': None,
                        'error': error_msg,
                        'metadata': {
                            'error_type': type(e).__name__,
                            'processed_at': datetime.now(timezone.utc).isoformat(),
                            'batch_size': len(batch),
                        },
                    }
                )

        return results

    def _generate_cache_key(self, prefix: str, *args: Any, **kwargs: Any) -> str:
        """Generate a cache key from the given arguments."""
        # Convert args and kwargs to a stable string representation
        parts = [prefix]
        parts.extend(str(arg) for arg in args)
        parts.extend(f"{k}={v}" for k, v in sorted(kwargs.items()))

        # Create a hash of the key components
        key_str = ":".join(parts).encode("utf-8")
        key_hash = hashlib.md5(key_str).hexdigest()

        return f"seal:{key_hash}"

    def _get_from_cache(self, key: str) -> Any:
        """Get a value from the cache if it exists and is not expired."""
        if not self.config.enable_caching or key not in self._cache:
            if self.metrics:
                self.metrics.cache_misses += 1
            return None

        # Check if the cache entry has expired
        current_time = time.time()
        if key in self._cache_timestamps:
            ttl = self.config.cache_ttl_seconds
            if current_time - self._cache_timestamps[key] > ttl:
                # Entry has expired
                del self._cache[key]
                del self._cache_timestamps[key]
                if self.metrics:
                    self.metrics.cache_misses += 1
                return None

        # Update last accessed time for LRU
        self._last_accessed[key] = current_time

        if self.metrics:
            self.metrics.cache_hits += 1

        return self._cache.get(key)

    def _add_to_cache(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Add a value to the cache, evicting if necessary."""
        if not self.config.enable_caching:
            return

        # Check if we need to evict entries
        if len(self._cache) >= self.config.max_cache_size:
            # Find the least recently used key
            if self._last_accessed:
                lru_key = min(self._last_accessed, key=self._last_accessed.get)  # type: ignore
                del self._cache[lru_key]
                if lru_key in self._cache_timestamps:
                    del self._cache_timestamps[lru_key]
                if lru_key in self._last_accessed:
                    del self._last_accessed[lru_key]

        # Add to cache
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
        self._last_accessed[key] = time.time()

    async def _get_cached_template(self, template_name: str) -> Any:
        """Get a compiled template from cache or load it."""
        if not self.config.enable_caching:
            return None

        if template_name in self._template_cache:
            self._last_accessed[template_name] = time.time()
            if self.metrics:
                self.metrics.cache_hits += 1
            return self._template_cache[template_name]

        # Try to get the template from the prompt constructor
        try:
            template = self.prompt_constructor.get_template(template_name)
            self._template_cache[template_name] = template
            self._last_accessed[template_name] = time.time()
            return template
        except ValueError:
            # Template not found in the constructor
            return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        if not self.config.enable_metrics or self.metrics is None:
            return {"error": "Metrics collection is disabled"}

        return self.metrics.get_metrics_summary()

    def clear_cache(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._template_cache.clear()
        self._cache_timestamps.clear()
        self._last_accessed.clear()
        logger.info("All caches cleared")

    def get_status(self) -> Dict[str, Any]:
        """Get system status information."""
        return {
            "status": "running" if self._is_running else "stopped",
            "uptime_seconds": (
                (datetime.now(timezone.utc) - self._startup_time).total_seconds()
                if self._is_running
                else 0
            ),
            "cache_size": len(self._cache),
            "template_cache_size": len(self._template_cache),
            "conversation_history_size": len(self.conversation_history.history),
            "background_tasks": len(self._background_tasks),
            "metrics_enabled": self.config.enable_metrics,
            "caching_enabled": self.config.enable_caching,
        }


# Example usage
async def example_usage():
    """Example usage of the EnhancedSEALSystem."""
    # Create a system with default configuration
    system = EnhancedSEALSystem()

    # Use async context manager for automatic startup/shutdown
    async with system:
        # Process a prompt
        result = await system.process_prompt(
            "What is the capital of France?", context={"user_id": "test_user"}
        )

        print(f"Response: {result['response']}")
        print(f"Metadata: {json.dumps(result['metadata'], indent=2)}")

        # Get metrics
        metrics = system.get_metrics()
        print(f"\nMetrics: {json.dumps(metrics, indent=2)}")

        # Get status
        status = system.get_status()
        print(f"\nStatus: {json.dumps(status, indent=2)}")


if __name__ == "__main__":
    asyncio.run(example_usage())

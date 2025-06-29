"""
FewShotLearner module for handling few-shot learning capabilities in EVOSEAL.

This module provides a flexible interface for few-shot learning that can be used
with various language models and adapters. It supports:

1. Multiple example selection strategies (first_k, random, similarity-based)
2. Various similarity metrics (cosine, euclidean, jaccard)
3. Fine-grained example management
4. Model fine-tuning with LoRA
5. Prompt formatting and generation

Example usage:
    ```python
    from evoseal.integration.seal.few_shot import FewShotLearner, FewShotExample

    # Initialize the learner
    learner = FewShotLearner()

    # Add examples
    learner.add_example({
        'input': 'How do I reset my password?',
        'output': 'You can reset your password by...',
        'metadata': {'source': 'faq', 'category': 'account'}
    })

    # Get relevant examples for a query
    examples = learner.get_relevant_examples(
        'I forgot my password',
        strategy='similarity',
        similarity_metric='cosine',
        k=3
    )

    # Generate a response
    response = learner.generate('How can I recover my account?')
    ```
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

import numpy as np
import torch
from datasets import Dataset
from peft import LoraConfig, get_peft_model
from tqdm import tqdm
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    PreTrainedModel,
    PreTrainedTokenizer,
    Trainer,
    TrainingArguments,
)

# Set up logging
logger = logging.getLogger(__name__)


@dataclass
class FewShotExample:
    """Represents a single few-shot example with input-output pairs.

    Attributes:
        input_data: The input data for the example (text, structured data, etc.)
        output_data: The expected output data
        metadata: Optional metadata dictionary for additional information
    """

    input_data: Any
    output_data: Any
    metadata: dict[str, Any] = field(default_factory=dict)


class FewShotLearner:
    """A class to handle few-shot learning capabilities for language models.

    This class provides functionality to:
    1. Store and manage few-shot examples
    2. Select relevant examples based on input context
    3. Format examples for inclusion in prompts
    4. Fine-tune models using few-shot examples
    5. Generate responses using few-shot learning
    """

    def __init__(
        self,
        base_model_name: str = "gpt2",
        lora_config: dict[str, Any] | None = None,
        device: str | None = None,
        cache_dir: str | Path | None = None,
    ) -> None:
        """Initialize the FewShotLearner.

        Args:
            base_model_name: Name or path of the base model to use
            lora_rank: Rank for LoRA adapters
            lora_alpha: Alpha parameter for LoRA
            lora_dropout: Dropout rate for LoRA layers
            device: Device to run the model on ('cuda', 'cpu', or None for auto)
            cache_dir: Directory to cache model files
        """
        self.base_model_name = base_model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_dir = str(cache_dir) if cache_dir else None

        # Default LoRA configuration for GPT-2
        self.lora_config = lora_config or {
            "r": 16,
            "lora_alpha": 32,
            "lora_dropout": 0.05,
            "bias": "none",
            "task_type": "CAUSAL_LM",
            "target_modules": ["c_attn", "c_proj"],  # Target attention layers for GPT-2
        }

        # Initialize storage for examples
        self.examples: list[FewShotExample] = []

        # Will be initialized when needed
        self.model: PreTrainedModel | None = None
        self.tokenizer: PreTrainedTokenizer | None = None
        self.is_initialized = False

    def _initialize_model(self) -> None:
        """Initialize the model and tokenizer if not already done.

        This method initializes the tokenizer and model with the specified configuration,
        and sets up LoRA for parameter-efficient fine-tuning.

        Raises:
            ImportError: If required packages are not installed
            OSError: If model files cannot be loaded
            RuntimeError: If there's an error during model initialization
            ValueError: If the model configuration is invalid
        """
        if self.is_initialized:
            return

        logger.info(f"Initializing model: {self.base_model_name}")

        try:
            # Initialize tokenizer
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(
                    self.base_model_name, cache_dir=self.cache_dir, padding_side="left"
                )

                if not self.tokenizer.pad_token:
                    self.tokenizer.pad_token = self.tokenizer.eos_token

            except Exception as e:
                logger.error(f"Failed to initialize tokenizer: {str(e)}")
                raise RuntimeError(f"Failed to initialize tokenizer: {str(e)}") from e

            # Initialize model
            try:
                self.model = AutoModelForCausalLM.from_pretrained(
                    self.base_model_name,
                    torch_dtype=(torch.bfloat16 if torch.cuda.is_available() else torch.float32),
                    device_map="auto" if torch.cuda.is_available() else None,
                    cache_dir=self.cache_dir,
                    trust_remote_code=True,
                )
            except ImportError as e:
                logger.error(f"Missing required dependencies: {str(e)}")
                raise ImportError(
                    f"Failed to load model {self.base_model_name}. "
                    "Make sure all required dependencies are installed."
                ) from e
            except OSError as e:
                logger.error(f"Model files not found: {str(e)}")
                raise OSError(
                    f"Could not find model files for {self.base_model_name}. "
                    "Check if the model name is correct and you have an internet connection."
                ) from e

            # Initialize LoRA
            try:
                lora_config = LoraConfig(
                    r=self.lora_config["r"],
                    lora_alpha=self.lora_config["lora_alpha"],
                    lora_dropout=self.lora_config["lora_dropout"],
                    bias="none",
                    task_type=self.lora_config["task_type"],
                    target_modules=["c_attn", "c_proj"],  # For GPT-2 architecture
                )

                self.model = get_peft_model(self.model, lora_config)

                # Log trainable parameters
                trainable_params = sum(
                    p.numel() for p in self.model.parameters() if p.requires_grad
                )
                total_params = sum(p.numel() for p in self.model.parameters())
                logger.info(
                    f"Trainable params: {trainable_params:,} || "
                    f"All params: {total_params:,} || "
                    f"Trainable%: {100 * trainable_params / total_params:.2f}%"
                )

                self.is_initialized = True

            except Exception as e:
                logger.error(f"Failed to initialize LoRA: {str(e)}")
                raise RuntimeError(
                    f"Failed to initialize LoRA adapters: {str(e)}. "
                    "Check if the target modules are correct for your model architecture."
                ) from e

        except Exception as e:
            self.model = None
            self.tokenizer = None
            self.is_initialized = False
            logger.error(f"Model initialization failed: {str(e)}")
            raise

    def add_example(self, example: dict[str, Any] | FewShotExample) -> None:
        """Add a new few-shot example to the learner.

        Args:
            example: The FewShotExample or dictionary with 'input' and 'output' keys to add

        Raises:
            ValueError: If the example format is invalid
        """
        if isinstance(example, dict):
            if "input" not in example or "output" not in example:
                raise ValueError("Example must contain 'input' and 'output' keys")
            example = FewShotExample(
                input_data=example["input"],
                output_data=example["output"],
                metadata=example.get("metadata", {}),
            )
        elif not isinstance(example, FewShotExample):
            raise ValueError(
                "Example must be a FewShotExample or a dictionary with 'input' and 'output' keys"
            )

        self.examples.append(example)

    def remove_example(self, index: int) -> None:
        """Remove a few-shot example by index.

        Args:
            index: Index of the example to remove

        Raises:
            IndexError: If index is out of range
        """
        if 0 <= index < len(self.examples):
            self.examples.pop(index)
        else:
            raise IndexError(
                f"Index {index} out of range for examples list (length: {len(self.examples)})"
            )

    def clear_examples(self) -> None:
        """Remove all stored examples."""
        self.examples = []

    def get_example(self, index: int) -> FewShotExample:
        """Get a specific example by index.

        Args:
            index: Index of the example to retrieve

        Returns:
            The requested FewShotExample

        Raises:
            IndexError: If index is out of range
        """
        if 0 <= index < len(self.examples):
            return self.examples[index]
        raise IndexError(
            f"Index {index} out of range for examples list (length: {len(self.examples)})"
        )

    def update_example(self, index: int, new_example: dict[str, Any] | FewShotExample) -> None:
        """Update an existing example.

        Args:
            index: Index of the example to update
            new_example: New example data to replace the existing one

        Raises:
            IndexError: If index is out of range
            ValueError: If the new example format is invalid
        """
        if isinstance(new_example, dict):
            if "input" not in new_example or "output" not in new_example:
                raise ValueError("Example must contain 'input' and 'output' keys")
            new_example = FewShotExample(
                input_data=new_example["input"],
                output_data=new_example["output"],
                metadata=new_example.get("metadata", {}),
            )
        elif not isinstance(new_example, FewShotExample):
            raise ValueError(
                "Example must be a FewShotExample or a dictionary with 'input' and 'output' keys"
            )

        if 0 <= index < len(self.examples):
            self.examples[index] = new_example
        else:
            raise IndexError(
                f"Index {index} out of range for examples list (length: {len(self.examples)})"
            )

    def find_examples(
        self, query: str, field: str = "input_data", case_sensitive: bool = False
    ) -> list[int]:
        """Find examples containing the query string in the specified field.

        Args:
            query: String to search for
            field: Field to search in ('input_data', 'output_data', or 'metadata')
            case_sensitive: Whether the search should be case sensitive

        Returns:
            List of indices of matching examples

        Raises:
            ValueError: If field is not valid
        """
        if field not in ["input_data", "output_data", "metadata"]:
            raise ValueError("Field must be one of: 'input_data', 'output_data', 'metadata'")

        query = query if case_sensitive else query.lower()
        matches: list[int] = []

        for i, example in enumerate(self.examples):
            value = getattr(example, field)
            if field == "metadata":
                # Convert metadata dict to string for searching
                value = str(value)
            elif not isinstance(value, str):
                value = str(value)

            if not case_sensitive:
                value = value.lower()

            if query in value:
                matches.append(i)

        return matches

    def get_relevant_examples(
        self,
        query: str,
        k: int = 5,
        strategy: str = "first_k",
        similarity_metric: str = "cosine",
        **kwargs: Any,
    ) -> list[FewShotExample]:
        """Retrieve the k most relevant examples for the given query.

        Args:
            query: The input query to find relevant examples for
            k: Maximum number of examples to return
            strategy: Strategy for selecting examples ('first_k', 'random', 'similarity')
            similarity_metric: The similarity metric to use for 'similarity' strategy
                             ('cosine', 'euclidean', or 'jaccard')
            **kwargs: Additional arguments for the similarity function

        Returns:
            List of relevant FewShotExample objects

        Raises:
            ValueError: If an invalid strategy or similarity metric is provided
        """
        if not self.examples or k <= 0:
            return []

        # Limit k to the number of available examples
        k = min(k, len(self.examples))

        if strategy == "first_k":
            # Return the first k examples (default behavior)
            return self.examples[:k]

        if strategy == "random":
            # Return k random examples
            import random

            return random.sample(self.examples, k)

        if strategy == "similarity":
            # Import required libraries only when needed
            try:
                import numpy as np
                from sklearn.feature_extraction.text import TfidfVectorizer
                from sklearn.metrics import jaccard_score
                from sklearn.metrics.pairwise import cosine_similarity, euclidean_distances
            except ImportError as e:
                logger.warning(
                    f"scikit-learn not installed: {e}. Falling back to 'first_k' strategy. "
                    "Install with: pip install scikit-learn"
                )
                return self.examples[:k]

            # Prepare texts for similarity comparison
            texts = [str(ex.input_data) for ex in self.examples]
            texts = [query] + texts  # Add query as first element

            # Create TF-IDF vectors
            vectorizer = TfidfVectorizer()
            try:
                tfidf_matrix = vectorizer.fit_transform(texts)
            except ValueError as e:
                logger.warning(f"TF-IDF vectorization failed: {e}. Falling back to 'first_k'")
                return self.examples[:k]

            # Calculate similarities
            query_vector = tfidf_matrix[0:1]
            example_vectors = tfidf_matrix[1:]

            if similarity_metric == "cosine":
                similarities = cosine_similarity(query_vector, example_vectors).flatten()
            elif similarity_metric == "euclidean":
                distances = euclidean_distances(query_vector, example_vectors).flatten()
                # Convert distances to similarities (higher is better)
                similarities = 1 / (1 + distances)
            elif similarity_metric == "jaccard":
                # Convert to binary features for Jaccard
                binary_matrix = (tfidf_matrix > 0).astype(int)
                query_binary = binary_matrix[0:1].toarray()
                examples_binary = binary_matrix[1:].toarray()
                similarities = np.array(
                    [
                        jaccard_score(query_binary[0], ex_binary, average="micro")
                        for ex_binary in examples_binary
                    ]
                )
            else:
                raise ValueError(
                    f"Unsupported similarity metric: {similarity_metric}. "
                    "Must be one of: 'cosine', 'euclidean', 'jaccard'"
                )

            # Get indices of top k most similar examples
            top_indices = np.argsort(similarities)[-k:][::-1]
            return [self.examples[i] for i in top_indices]

        raise ValueError(
            f"Unknown strategy: {strategy}. " "Must be one of: 'first_k', 'random', 'similarity'"
        )

    def generate(
        self,
        query: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **generation_kwargs: Any,
    ) -> str:
        """Generate a response using few-shot learning.

        Args:
            query: The input query
            max_new_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
            top_p: Nucleus sampling parameter
            **generation_kwargs: Additional generation parameters

        Returns:
            Generated text response
        """
        if not self.is_initialized:
            self._initialize_model()

        # Ensure model is on the correct device
        if self.model is not None and self.tokenizer is not None:
            self.model.to(self.device)

            # Get relevant examples
            examples = self.get_relevant_examples(query)

            # Format prompt
            prompt = self.format_prompt(query, examples)

            # Tokenize input
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                padding=True,
                truncation=True,
                max_length=4096,  # Adjust based on model context length
                return_attention_mask=True,
            ).to(self.device)

            # Generate response
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_new_tokens=max_new_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    do_sample=True,
                    pad_token_id=self.tokenizer.eos_token_id,
                    **generation_kwargs,
                )

            # Decode and return the response
            response: str = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
            )
            return response.strip()

        return ""

    def fine_tune(
        self,
        output_dir: str | Path,
        training_config: dict[str, Any] | None = None,
        **training_kwargs: Any,
    ) -> None:
        """Fine-tune the model on the stored examples.

        Args:
            output_dir: Directory to save the fine-tuned model
            training_config: Dictionary containing training configuration
            **training_kwargs: Additional training arguments
        """
        training_config = training_config or {}
        num_epochs = training_config.get("num_epochs", 3)
        per_device_train_batch_size = training_config.get("per_device_train_batch_size", 4)
        learning_rate = training_config.get("learning_rate", 2e-5)
        warmup_steps = training_config.get("warmup_steps", 100)
        logging_steps = training_config.get("logging_steps", 10)
        save_steps = training_config.get("save_steps", 200)
        if not self.examples:
            logger.warning("No examples available for fine-tuning")
            return

        if not self.is_initialized:
            self._initialize_model()

        if self.model is None or self.tokenizer is None:
            raise ValueError("Model and tokenizer must be initialized")

        def tokenize_function(examples: dict[str, list[Any]]) -> dict[str, torch.Tensor]:
            """Tokenize examples for model training.

            Args:
                examples: Dictionary containing 'input', 'output', and 'system_prompt' lists

            Returns:
                Dictionary with tokenized inputs and attention masks
            """
            if self.tokenizer is None:
                raise RuntimeError("Tokenizer not initialized")

            texts = []
            for i in range(len(examples["input"])):
                prompt = self.format_prompt(
                    query=examples["input"][i],
                    examples=[],  # Don't include other examples in each training example
                    system_prompt=examples.get("system_prompt", [""])[i]
                    or "You are a helpful AI assistant.",
                )
                texts.append(f"{prompt}{examples['output'][i]}{self.tokenizer.eos_token}")

            tokenized: dict[str, torch.Tensor] = self.tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=2048,  # Adjust based on model context length
                return_tensors="pt",
            )
            return tokenized

        # Create dataset
        dataset_dict = {
            "input": [str(ex.input_data) for ex in self.examples],
            "output": [str(ex.output_data) for ex in self.examples],
            "system_prompt": [ex.metadata.get("system_prompt", "") for ex in self.examples],
        }

        dataset = Dataset.from_dict(dataset_dict)
        if self.tokenizer is None:
            raise RuntimeError("Tokenizer not initialized")

        tokenized_datasets = dataset.map(
            lambda x: self._tokenize_examples(x, self.tokenizer),
            batched=True,
            remove_columns=dataset.column_names,
        )

        # Set up training arguments
        training_args = TrainingArguments(
            output_dir=str(output_dir),
            num_train_epochs=num_epochs,
            per_device_train_batch_size=per_device_train_batch_size,
            learning_rate=learning_rate,
            warmup_steps=warmup_steps,
            logging_steps=logging_steps,
            save_steps=save_steps,
            save_total_limit=3,
            # Disable load_best_model_at_end since we're not doing evaluation
            load_best_model_at_end=False,
            # Set save strategy to steps
            save_strategy="steps",
            # Set logging strategy to steps
            logging_strategy="steps",
            logging_dir=f"{output_dir}/logs",
            **training_kwargs,
        )

        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_datasets,
            data_collator=DataCollatorForLanguageModeling(tokenizer=self.tokenizer, mlm=False),
        )

        # Train the model
        trainer.train()

        # Save the final model
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)

        logger.info(f"Model saved to {output_dir}")

    def save_examples(self, filepath: str | Path) -> None:
        """Save examples to a JSON file.

        Args:
            filepath: Path to save the examples to
        """
        data = [
            {
                "input": str(ex.input_data),
                "output": str(ex.output_data),
                "metadata": ex.metadata,
            }
            for ex in self.examples
        ]

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    @classmethod
    def load_examples(cls, filepath: str | Path) -> list[FewShotExample]:
        """Load examples from a JSON file.

        Args:
            filepath: Path to the JSON file containing examples

        Returns:
            List of FewShotExample objects
        """
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)

        return [
            FewShotExample(
                input_data=item["input"],
                output_data=item["output"],
                metadata=item.get("metadata", {}),
            )
            for item in data
        ]

    def _tokenize_examples(
        self,
        examples: dict[str, list[Any]],
        tokenizer: PreTrainedTokenizer,
    ) -> dict[str, torch.Tensor]:
        """Tokenize examples for model training.

        Args:
            examples: Dictionary containing 'input', 'output', and 'system_prompt' lists
            tokenizer: Tokenizer to use for tokenization

        Returns:
            Dictionary with tokenized inputs and attention masks
        """
        texts: list[str] = []
        system_prompts = examples.get("system_prompt", [""] * len(examples["input"]))

        for i, (input_text, output_text) in enumerate(zip(examples["input"], examples["output"])):
            prompt = self.format_prompt(
                query=input_text,
                examples=[],  # Don't include other examples in each training example
                system_prompt=system_prompts[i] or "You are a helpful AI assistant.",
            )
            texts.append(f"{prompt}{output_text}{tokenizer.eos_token}")

        tokenized: dict[str, torch.Tensor] = tokenizer(
            texts,
            padding="max_length",
            truncation=True,
            max_length=2048,  # Adjust based on model context length
            return_tensors="pt",
        )
        return tokenized

    def format_prompt(
        self,
        query: str,
        examples: list[FewShotExample] | None = None,
        system_prompt: str = "You are a helpful AI assistant.",
        example_separator: str | None = None,
    ) -> str:
        """Format the input query and examples into a prompt for the language model.

        This method creates a structured prompt that includes an optional system message,
        followed by few-shot examples, and finally the user's query. The format is designed
        to be compatible with instruction-following language models.

        Args:
            query: The user's input query to be included in the prompt
            examples: List of FewShotExample objects to include as examples.
                     If None, uses self.examples.
            system_prompt: The system message to include at the beginning of the prompt
            example_separator: String to separate different examples in the prompt
            include_system_prompt: Whether to include the system prompt in the output

        Returns:
            str: Formatted prompt string ready for the language model

        Example:
            ```python
            learner = FewShotLearner()
            learner.add_example({
                'input': 'What is the capital of France?',
                'output': 'The capital of France is Paris.'
            })
            prompt = learner.format_prompt(
                'What is the capital of Germany?',
                system_prompt='You are a helpful geography assistant.'
            )
            ```
        """
        example_sep = "\n\n---\n\n" if example_separator is None else example_separator
        if examples is None:
            examples = self.examples

        # Start with system prompt
        prompt_parts = [f"System: {system_prompt.strip()}"] if system_prompt else []

        # Add examples if provided
        if examples:
            for i, example in enumerate(examples, 1):
                example_str = (
                    f"Example {i}:\n"
                    f"Input: {str(example.input_data).strip()}\n"
                    f"Output: {str(example.output_data).strip()}"
                )
                if example.metadata:
                    example_str += f"\nMetadata: {json.dumps(example.metadata, ensure_ascii=False)}"
                prompt_parts.append(example_str)

        # Add the current query
        prompt_parts.append(f"Input: {query.strip()}\nOutput:")

        return example_sep.join(part for part in prompt_parts if part)

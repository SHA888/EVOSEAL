"""
FewShotLearner module for handling few-shot learning capabilities in EVOSEAL.

This module provides a flexible interface for few-shot learning that can be used
with various language models and adapters.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union, Callable
from pathlib import Path
import json
import os
import torch
import numpy as np
from tqdm import tqdm
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    PreTrainedTokenizer,
    PreTrainedModel,
    TrainingArguments,
    Trainer,
    DataCollatorForLanguageModeling
)
from datasets import Dataset
import logging

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
    metadata: Dict[str, Any] = field(default_factory=dict)


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
        lora_rank: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.05,
        device: Optional[str] = None,
        cache_dir: Optional[Union[str, Path]] = None,
    ):
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
        self.lora_config = {
            "r": lora_rank,
            "lora_alpha": lora_alpha,
            "lora_dropout": lora_dropout,
            "bias": "none",
            "task_type": "CAUSAL_LM",
            "target_modules": ["c_attn", "c_proj"],  # Target attention layers for GPT-2
        }
        
        # Initialize storage for examples
        self.examples: List[FewShotExample] = []
        
        # Will be initialized when needed
        self.model: Optional[PreTrainedModel] = None
        self.tokenizer: Optional[PreTrainedTokenizer] = None
        self.is_initialized = False
    
    def _initialize_model(self) -> None:
        """Initialize the model and tokenizer if not already done."""
        if self.is_initialized:
            return
            
        logger.info(f"Initializing model: {self.base_model_name}")
        
        # Initialize tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(
            self.base_model_name,
            cache_dir=self.cache_dir,
            padding_side="left"
        )
        
        if not self.tokenizer.pad_token:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        # Initialize model
        self.model = AutoModelForCausalLM.from_pretrained(
            self.base_model_name,
            torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
            device_map="auto",
            cache_dir=self.cache_dir,
            trust_remote_code=True
        )
        
        # Initialize LoRA
        lora_config = LoraConfig(
            r=self.lora_config["r"],
            lora_alpha=self.lora_config["lora_alpha"],
            lora_dropout=self.lora_config["lora_dropout"],
            bias="none",
            task_type=self.lora_config["task_type"],
            target_modules=["q_proj", "v_proj"]  # Common for LLaMA models
        )
        
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        self.is_initialized = True
    
    def add_example(self, example: Union[Dict[str, Any], FewShotExample]) -> None:
        """Add a new few-shot example to the learner.
        
        Args:
            example: The FewShotExample or dictionary with 'input' and 'output' keys to add
            
        Raises:
            ValueError: If the example format is invalid
        """
        if isinstance(example, dict):
            if 'input' not in example or 'output' not in example:
                raise ValueError("Example must contain 'input' and 'output' keys")
            example = FewShotExample(
                input_data=example['input'],
                output_data=example['output'],
                metadata=example.get('metadata', {})
            )
        elif not isinstance(example, FewShotExample):
            raise ValueError("Example must be a FewShotExample or a dictionary with 'input' and 'output' keys")
            
        self.examples.append(example)
    
    def remove_example(self, index: int) -> None:
        """Remove a few-shot example by index.
        
        Args:
            index: Index of the example to remove
            
        Raises:
            IndexError: If index is out of range
        """
        if 0 <= index < len(self.examples):
            del self.examples[index]
        else:
            raise IndexError(f"Index {index} out of range for examples list (length: {len(self.examples)})")
    
    def clear_examples(self) -> None:
        """Remove all stored examples."""
        self.examples = []
    
    def get_relevant_examples(
        self, 
        query: str, 
        k: int = 5,
        similarity_metric: str = "cosine",
        **kwargs
    ) -> List[FewShotExample]:
        """Retrieve the k most relevant examples for the given query.
        
        Args:
            query: The input query to find relevant examples for
            k: Maximum number of examples to return
            similarity_metric: The similarity metric to use ('cosine' or 'euclidean')
            **kwargs: Additional arguments for the similarity function
            
        Returns:
            List of relevant FewShotExample objects
        """
        if not self.examples:
            return []
            
        # For now, return the first k examples
        # In a production system, you'd want to implement proper semantic search here
        return self.examples[:min(k, len(self.examples))]
    
    def format_prompt(
        self, 
        query: str, 
        examples: Optional[List[FewShotExample]] = None,
        system_prompt: str = "You are a helpful AI assistant.",
        format_func: Optional[Callable[[str, List[FewShotExample]], str]] = None
    ) -> str:
        """Format the prompt with examples and query.
        
        Args:
            query: The input query
            examples: List of examples to include (defaults to all examples if None)
            system_prompt: System prompt to use
            format_func: Custom formatting function (input: query, examples)
            
        Returns:
            Formatted prompt string
        """
        if examples is None:
            examples = self.examples
            
        if format_func:
            return format_func(query, examples)
            
        # Default formatting using LLaMA 3 chat template
        messages = [{"role": "system", "content": system_prompt}]
        
        for example in examples:
            messages.extend([
                {"role": "user", "content": str(example.input_data)},
                {"role": "assistant", "content": str(example.output_data)}
            ])
        
        # Add the current query
        messages.append({"role": "user", "content": query})
        
        if self.tokenizer and hasattr(self.tokenizer, 'apply_chat_template'):
            return self.tokenizer.apply_chat_template(
                messages,
                tokenize=False,
                add_generation_prompt=True
            )
        else:
            # Fallback formatting if tokenizer doesn't support chat templates
            formatted = []
            for msg in messages:
                role = msg["role"]
                content = msg["content"]
                formatted.append(f"<|{role}|>\n{content}</s>")
            return "\n".join(formatted)
    
    def generate(
        self,
        query: str,
        max_new_tokens: int = 256,
        temperature: float = 0.7,
        top_p: float = 0.9,
        **generation_kwargs
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
                return_attention_mask=True
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
                    **generation_kwargs
                )
            
            # Decode and return the response
            response = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:], 
                skip_special_tokens=True
            )
            return response.strip()
        
        return ""
    
    def fine_tune(
        self,
        output_dir: Union[str, Path],
        num_epochs: int = 3,
        per_device_train_batch_size: int = 4,
        learning_rate: float = 2e-5,
        warmup_steps: int = 100,
        logging_steps: int = 10,
        save_steps: int = 200,
        **training_kwargs
    ) -> None:
        """Fine-tune the model on the stored examples.
        
        Args:
            output_dir: Directory to save the fine-tuned model
            num_epochs: Number of training epochs
            per_device_train_batch_size: Batch size per device
            learning_rate: Learning rate for training
            warmup_steps: Number of warmup steps
            logging_steps: Log loss every N steps
            save_steps: Save model every N steps
            **training_kwargs: Additional training arguments
        """
        if not self.examples:
            logger.warning("No examples available for fine-tuning")
            return
            
        if not self.is_initialized:
            self._initialize_model()
            
        if self.model is None or self.tokenizer is None:
            raise ValueError("Model and tokenizer must be initialized")
        
        # Prepare data
        def tokenize_function(examples):
            # Tokenize the examples
            texts = []
            for ex in examples:
                prompt = self.format_prompt(
                    query=ex["input"],
                    examples=[],  # Don't include other examples in each training example
                    system_prompt=ex.get("system_prompt", "You are a helpful AI assistant.")
                )
                texts.append(prompt + ex["output"] + self.tokenizer.eos_token)
            
            return self.tokenizer(
                texts,
                padding="max_length",
                truncation=True,
                max_length=2048,  # Adjust based on model context length
                return_tensors="pt"
            )
        
        # Create dataset
        dataset_dict = {
            "input": [str(ex.input_data) for ex in self.examples],
            "output": [str(ex.output_data) for ex in self.examples],
            "system_prompt": [ex.metadata.get("system_prompt", "") for ex in self.examples]
        }
        
        dataset = Dataset.from_dict(dataset_dict)
        tokenized_datasets = dataset.map(
            tokenize_function,
            batched=True,
            remove_columns=dataset.column_names
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
            **training_kwargs
        )
        
        # Initialize trainer
        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=tokenized_datasets,
            data_collator=DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False
            ),
        )
        
        # Train the model
        trainer.train()
        
        # Save the final model
        trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        logger.info(f"Model saved to {output_dir}")
    
    def save_examples(self, filepath: Union[str, Path]) -> None:
        """Save examples to a JSON file.
        
        Args:
            filepath: Path to save the examples to
        """
        data = [
            {
                "input": str(ex.input_data),
                "output": str(ex.output_data),
                "metadata": ex.metadata
            }
            for ex in self.examples
        ]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    @classmethod
    def load_examples(cls, filepath: Union[str, Path]) -> List[FewShotExample]:
        """Load examples from a JSON file.
        
        Args:
            filepath: Path to the JSON file containing examples
            
        Returns:
            List of FewShotExample objects
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return [
            FewShotExample(
                input_data=item["input"],
                output_data=item["output"],
                metadata=item.get("metadata", {})
            )
            for item in data
        ]
    
    def load_pretrained(self, model_path: Union[str, Path]) -> None:
        """Load a fine-tuned model from disk.
        
        Args:
            model_path: Path to the fine-tuned model
        """
        if not self.is_initialized:
            self._initialize_model()
            
        if self.model is not None and self.tokenizer is not None:
            # Load the fine-tuned model
            self.model = AutoModelForCausalLM.from_pretrained(
                str(model_path),
                torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
                device_map="auto",
                trust_remote_code=True
            )
            self.tokenizer = AutoTokenizer.from_pretrained(
                str(model_path),
                padding_side="left"
            )
            
            if not self.tokenizer.pad_token:
                self.tokenizer.pad_token = self.tokenizer.eos_token
            
            logger.info(f"Loaded fine-tuned model from {model_path}")

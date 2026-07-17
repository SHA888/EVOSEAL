"""
Weight-level model fine-tuner using LoRA/QLoRA (GPU-only).

This module handles the fine-tuning of a local coding model with evolution
patterns collected from EVOSEAL, enabling bidirectional improvement. The model is
model-agnostic: by default it targets whichever coder model is discovered from
Ollama (see :mod:`evoseal.providers.local_models`). Requires a CUDA GPU; on a
CPU-only host use the prompt-level path in :mod:`evoseal.prompt_evolution`.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import torch
    import transformers
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        DataCollatorForLanguageModeling,
        Trainer,
        TrainingArguments,
    )

    TRANSFORMERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Transformers dependencies not available: {e}")
    TRANSFORMERS_AVAILABLE = False

    # Define dummy Dataset class for fallback
    class Dataset:
        pass


from ..providers.local_models import AgentRole, resolve_model


class ModelFineTuner:
    """
    Fine-tuner for a local coding model using LoRA/QLoRA.

    This class handles the fine-tuning process using Parameter-Efficient
    Fine-Tuning (PEFT) techniques like LoRA. It is model-agnostic: when
    ``model_name`` is not given it targets the discovered coder model.
    """

    def __init__(
        self,
        model_name: str | None = None,
        base_model_path: str | None = None,
        output_dir: Path | None = None,
        use_lora: bool = True,
        use_qlora: bool = False,
    ):
        """
        Initialize the fine-tuner.

        Args:
            model_name: Name of the model to fine-tune. When ``None``, the coder
                model is discovered from the installed Ollama models.
            base_model_path: Path to base model (if using local model)
            output_dir: Directory to save fine-tuned models
            use_lora: Whether to use LoRA fine-tuning
            use_qlora: Whether to use QLoRA (quantized LoRA)
        """
        self.model_name = model_name or resolve_model(AgentRole.CODER)
        self.base_model_path = base_model_path
        self.output_dir = output_dir or Path("models/fine_tuned")
        self.use_lora = use_lora
        self.use_qlora = use_qlora

        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Model components
        self.tokenizer = None
        self.model = None
        self.peft_model = None

        # Training state
        self.is_initialized = False
        self.current_training = None

        # Check dependencies
        if not TRANSFORMERS_AVAILABLE:
            logger.warning("Transformers not available. Fine-tuning will be limited.")

        logger.info(f"ModelFineTuner initialized for {self.model_name}")

    #: Map an Ollama model *family* (substring) to a Hugging Face base repo for PEFT.
    HF_BASE_MODEL_BY_FAMILY: dict[str, str] = {
        "deepseek-coder": "deepseek-ai/deepseek-coder-6.7b-instruct",
        "qwen2.5-coder": "Qwen/Qwen2.5-Coder-7B-Instruct",
        "codellama": "codellama/CodeLlama-7b-Instruct-hf",
        "devstral": "mistralai/Mistral-7B-Instruct-v0.2",
        "mistral": "mistralai/Mistral-7B-Instruct-v0.2",
    }

    def _resolve_hf_base_model(self) -> str:
        """Pick a Hugging Face base repo for the configured (Ollama) model family."""
        if self.base_model_path:
            return self.base_model_path
        name = self.model_name.lower()
        for family, hf_repo in self.HF_BASE_MODEL_BY_FAMILY.items():
            if family in name:
                logger.info("Using base model %s for %s fine-tuning", hf_repo, self.model_name)
                return hf_repo
        # Unknown family: fall back to the model name itself (may be a valid HF repo).
        logger.warning(
            "No HF base mapping for %s; using it directly as the base model", self.model_name
        )
        return self.model_name

    def _check_gpu_availability(self) -> bool:
        """
        Check if GPU is available for training.

        Returns:
            True if GPU is available, False otherwise
        """
        if not TRANSFORMERS_AVAILABLE:
            return False

        try:
            import torch

            return torch.cuda.is_available() and torch.cuda.device_count() > 0
        except ImportError:
            return False

    async def initialize_model(self) -> bool:
        """
        Initialize the model and tokenizer for fine-tuning.

        Returns:
            True if initialization successful, False otherwise
        """
        if not TRANSFORMERS_AVAILABLE:
            logger.error("Transformers library not available for fine-tuning")
            return False

        try:
            logger.info("Initializing model and tokenizer...")

            # Ollama tags are not HF repos, so map the discovered model's family to a
            # compatible Hugging Face base model for PEFT fine-tuning. Extend this map
            # as new coder families are used.
            base_model = self._resolve_hf_base_model()

            # Load tokenizer. Base model is operator-configured; revision pinning is
            # left to the caller via base_model_path.
            self.tokenizer = AutoTokenizer.from_pretrained(  # nosec B615
                base_model, trust_remote_code=True, padding_side="right"
            )

            # Add pad token if missing
            if self.tokenizer.pad_token is None:
                self.tokenizer.pad_token = self.tokenizer.eos_token

            # Load model
            model_kwargs = {
                "trust_remote_code": True,
                "torch_dtype": (torch.float16 if torch.cuda.is_available() else torch.float32),
                "device_map": "auto" if torch.cuda.is_available() else None,
            }

            # Revision pinning is left to the caller (see note above).
            self.model = AutoModelForCausalLM.from_pretrained(  # nosec B615
                base_model, **model_kwargs
            )

            # Configure for training
            self.model.config.use_cache = False
            self.model.config.pretraining_tp = 1

            self.is_initialized = True
            logger.info("Model initialization complete")
            return True

        except Exception as e:
            logger.error(f"Error initializing model: {e}")
            return False

    async def prepare_training_data(self, data_file: Path) -> dict[str, Any]:
        """
        Prepare training data for fine-tuning.

        Args:
            data_file: Path to training data JSON file

        Returns:
            Preparation results
        """
        try:
            logger.info(f"Preparing training data from {data_file}")

            # Load training data
            with open(data_file) as f:
                training_data = json.load(f)

            examples = training_data.get("examples", [])
            if not examples:
                return {"success": False, "error": "No training examples found"}

            # If transformers not available, create fallback data
            if not TRANSFORMERS_AVAILABLE or not self.is_initialized:
                logger.warning("Creating fallback training data (transformers not available)")

                # Create simple text format for fallback
                fallback_data = []
                for example in examples:
                    text = f"Instruction: {example['instruction']}\nInput: {example.get('input', '')}\nOutput: {example['output']}"
                    fallback_data.append(text)

                # Save fallback data
                fallback_file = self.output_dir / "fallback_training_data.txt"
                with open(fallback_file, "w") as f:
                    f.write("\n\n---\n\n".join(fallback_data))

                return {
                    "success": True,
                    "fallback_mode": True,
                    "prepared_data_path": str(fallback_file),
                    "examples_count": len(examples),
                    "format": "text",
                }

            # Prepare data for transformers
            formatted_examples = []
            for example in examples:
                # Format as instruction-following format
                text = f"<s>[INST] {example['instruction']}\n{example.get('input', '')} [/INST] {example['output']}</s>"
                formatted_examples.append({"text": text})

            # Create dataset
            dataset = Dataset.from_list(formatted_examples)

            # Tokenize dataset
            def tokenize_function(examples):
                return self.tokenizer(
                    examples["text"],
                    truncation=True,
                    padding=False,
                    max_length=512,
                    return_overflowing_tokens=False,
                )

            tokenized_dataset = dataset.map(
                tokenize_function,
                batched=True,
                remove_columns=dataset.column_names,
            )

            # Save prepared dataset
            prepared_data_path = self.output_dir / "prepared_training_data"
            tokenized_dataset.save_to_disk(str(prepared_data_path))

            logger.info(f"Training data prepared: {len(examples)} examples")

            return {
                "success": True,
                "fallback_mode": False,
                "prepared_data_path": str(prepared_data_path),
                "examples_count": len(examples),
                "format": "huggingface_dataset",
            }

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return {"success": False, "error": str(e)}

    async def fine_tune_model(
        self,
        training_data_path: str | None = None,
        epochs: int = 3,
        learning_rate: float = 2e-4,
        batch_size: int = 4,
        max_length: int = 512,
    ) -> dict[str, Any]:
        """
        Fine-tune the model using LoRA/QLoRA.

        Args:
            training_data_path: Path to prepared training data
            epochs: Number of training epochs
            learning_rate: Learning rate for training
            batch_size: Training batch size
            max_length: Maximum sequence length

        Returns:
            Fine-tuning results
        """
        try:
            logger.info("Starting model fine-tuning...")

            if not training_data_path:
                return {"success": False, "error": "No training data path provided"}

            # Check if we're in fallback mode
            if not TRANSFORMERS_AVAILABLE or not self.is_initialized:
                logger.warning("Running in fallback mode - creating training script")

                # Create a training script for external use
                script_content = f"""#!/bin/bash
# Fine-tuning script for {self.model_name}
# Generated on {datetime.now().isoformat()}

echo "Fine-tuning {self.model_name} model..."
echo "Training data: {training_data_path}"
echo "Epochs: {epochs}"
echo "Learning rate: {learning_rate}"
echo "Batch size: {batch_size}"

# This script would normally run fine-tuning with:
# - LoRA/QLoRA configuration
# - Training data from {training_data_path}
# - Model: {self.model_name}

echo "Note: Transformers library not available. Manual fine-tuning required."
echo "Training data prepared at: {training_data_path}"
"""

                script_path = self.output_dir / "fine_tune_script.sh"
                with open(script_path, "w") as f:
                    f.write(script_content)

                # Generated helper script must be executable by its owner only.
                os.chmod(script_path, 0o700)  # nosec B103

                return {
                    "success": True,
                    "fallback_mode": True,
                    "script_path": str(script_path),
                    "training_data_path": training_data_path,
                    "message": "Training script created for manual execution",
                }

            # Load prepared dataset
            from datasets import load_from_disk

            dataset = load_from_disk(training_data_path)

            # Set up LoRA configuration
            lora_config = LoraConfig(
                task_type=TaskType.CAUSAL_LM,
                r=16,
                lora_alpha=32,
                lora_dropout=0.1,
                target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
            )

            # Apply LoRA to model
            self.peft_model = get_peft_model(self.model, lora_config)

            # Training arguments
            training_args = TrainingArguments(
                output_dir=str(self.output_dir / "training_output"),
                num_train_epochs=epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=learning_rate,
                logging_steps=10,
                save_steps=100,
                save_total_limit=2,
                remove_unused_columns=False,
                dataloader_drop_last=True,
            )

            # Data collator
            data_collator = DataCollatorForLanguageModeling(
                tokenizer=self.tokenizer,
                mlm=False,
            )

            # Trainer
            trainer = Trainer(
                model=self.peft_model,
                args=training_args,
                train_dataset=dataset,
                data_collator=data_collator,
            )

            # Start training
            logger.info("Starting training...")
            train_result = trainer.train()

            # Save model
            model_save_path = (
                self.output_dir / f"fine_tuned_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            )
            trainer.save_model(str(model_save_path))

            logger.info(f"Fine-tuning completed. Model saved to {model_save_path}")

            return {
                "success": True,
                "fallback_mode": False,
                "model_save_path": str(model_save_path),
                "train_loss": train_result.training_loss,
                "training_examples_count": len(dataset),
                "epochs": epochs,
                "learning_rate": learning_rate,
            }

        except Exception as e:
            logger.error(f"Error during fine-tuning: {e}")
            return {"success": False, "error": str(e)}


# Backwards-compatible alias (deprecated): the fine-tuner is no longer Devstral-specific.
DevstralFineTuner = ModelFineTuner

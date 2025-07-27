"""
Training data builder for converting evolution patterns into fine-tuning datasets.

This module converts successful evolution patterns into high-quality training
examples that can be used to fine-tune Devstral.
"""

import json
import logging
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .models import EvolutionResult, ImprovementType, TrainingExample
from .pattern_analyzer import PatternAnalyzer

logger = logging.getLogger(__name__)


class TrainingDataBuilder:
    """
    Builds training datasets from evolution patterns.

    This class converts successful evolution results into structured training
    examples suitable for fine-tuning Devstral using various training formats.
    """

    def __init__(
        self,
        min_quality_score: float = 0.8,
        max_examples_per_pattern: int = 50,
        include_negative_examples: bool = False,
    ):
        """
        Initialize the training data builder.

        Args:
            min_quality_score: Minimum quality score for training examples
            max_examples_per_pattern: Maximum examples per pattern type
            include_negative_examples: Whether to include negative examples
        """
        self.min_quality_score = min_quality_score
        self.max_examples_per_pattern = max_examples_per_pattern
        self.include_negative_examples = include_negative_examples

        # Training example storage
        self.training_examples: List[TrainingExample] = []
        self.examples_by_pattern: Dict[str, List[TrainingExample]] = defaultdict(list)

        # Quality filters
        self.quality_filters = [
            self._filter_code_length,
            self._filter_syntax_validity,
            self._filter_meaningful_changes,
            self._filter_improvement_clarity,
        ]

        logger.info("Training data builder initialized")

    def build_training_data(
        self,
        evolution_results: List[EvolutionResult],
        pattern_analysis: Optional[Dict[str, Any]] = None,
    ) -> List[TrainingExample]:
        """
        Build training data from evolution results.

        Args:
            evolution_results: List of evolution results to convert
            pattern_analysis: Optional pattern analysis results

        Returns:
            List of training examples
        """
        logger.info(
            f"Building training data from {len(evolution_results)} evolution results"
        )

        # Filter high-quality results
        high_quality_results = self._filter_high_quality_results(evolution_results)
        logger.info(f"Found {len(high_quality_results)} high-quality results")

        # Generate training examples
        examples = []
        for result in high_quality_results:
            example = self._create_training_example(result)
            if example and self._validate_example(example):
                examples.append(example)

                # Categorize by pattern
                pattern_type = self._identify_pattern_type(result)
                self.examples_by_pattern[pattern_type].append(example)

        # Balance examples across patterns
        balanced_examples = self._balance_examples(examples)

        # Add instruction variations
        varied_examples = self._add_instruction_variations(balanced_examples)

        self.training_examples = varied_examples
        logger.info(f"Generated {len(varied_examples)} training examples")

        return varied_examples

    def _filter_high_quality_results(
        self, results: List[EvolutionResult]
    ) -> List[EvolutionResult]:
        """Filter results for high-quality training examples."""
        high_quality = []

        for result in results:
            if (
                result.success
                and result.fitness_score >= self.min_quality_score
                and result.improvement_percentage > 10.0
            ):  # Significant improvement

                # Apply quality filters
                if all(filter_func(result) for filter_func in self.quality_filters):
                    high_quality.append(result)

        return high_quality

    def _filter_code_length(self, result: EvolutionResult) -> bool:
        """Filter based on code length (not too short or too long)."""
        orig_lines = len(result.original_code.split("\n"))
        imp_lines = len(result.improved_code.split("\n"))

        # Reasonable length bounds
        return (
            5 <= orig_lines <= 100
            and 5 <= imp_lines <= 150
            and abs(orig_lines - imp_lines) <= 50
        )

    def _filter_syntax_validity(self, result: EvolutionResult) -> bool:
        """Filter for syntactically valid code."""
        try:
            compile(result.original_code, "<string>", "exec")
            compile(result.improved_code, "<string>", "exec")
            return True
        except SyntaxError:
            return False

    def _filter_meaningful_changes(self, result: EvolutionResult) -> bool:
        """Filter for meaningful changes (not just whitespace)."""
        orig_normalized = "".join(result.original_code.split())
        imp_normalized = "".join(result.improved_code.split())

        # Must have actual content changes
        return orig_normalized != imp_normalized

    def _filter_improvement_clarity(self, result: EvolutionResult) -> bool:
        """Filter for clear improvements."""
        # Avoid cases where the improvement is unclear
        if result.fitness_score < 0.75:
            return False

        # Check for common improvement indicators
        improvements = [
            "import " in result.improved_code and "import " not in result.original_code,
            "def " in result.improved_code and "def " not in result.original_code,
            "try:" in result.improved_code and "try:" not in result.original_code,
            '"""' in result.improved_code and '"""' not in result.original_code,
            len(result.improved_code.split("\n"))
            < len(result.original_code.split("\n")) * 0.9,
        ]

        return any(improvements)

    def _create_training_example(
        self, result: EvolutionResult
    ) -> Optional[TrainingExample]:
        """Create a training example from an evolution result."""
        try:
            # Generate instruction based on improvement types
            instruction = self._generate_instruction(result)

            # Create context
            context = self._generate_context(result)

            # Calculate quality score
            quality_score = self._calculate_quality_score(result)

            example = TrainingExample(
                instruction=instruction,
                input_code=result.original_code.strip(),
                output_code=result.improved_code.strip(),
                context=context,
                quality_score=quality_score,
                source_evolution_id=result.id,
            )

            return example

        except Exception as e:
            logger.warning(f"Error creating training example: {e}")
            return None

    def _generate_instruction(self, result: EvolutionResult) -> str:
        """Generate an instruction for the training example."""
        improvement_types = [
            t.value.replace("_", " ").title() for t in result.improvement_types
        ]

        # Base instruction templates
        templates = [
            "Improve this code to enhance {improvements}:",
            "Refactor the following code to improve {improvements}:",
            "Optimize this code focusing on {improvements}:",
            "Enhance the code below by improving {improvements}:",
            "Rewrite this code to better handle {improvements}:",
        ]

        # Specific instruction templates based on patterns
        if ImprovementType.PERFORMANCE in result.improvement_types:
            templates.extend(
                [
                    "Optimize this code for better performance:",
                    "Improve the efficiency of this code:",
                    "Make this code run faster:",
                ]
            )

        if ImprovementType.READABILITY in result.improvement_types:
            templates.extend(
                [
                    "Make this code more readable and maintainable:",
                    "Improve the clarity of this code:",
                    "Refactor this code for better readability:",
                ]
            )

        if ImprovementType.ERROR_HANDLING in result.improvement_types:
            templates.extend(
                [
                    "Add proper error handling to this code:",
                    "Make this code more robust with error handling:",
                    "Improve error handling in this code:",
                ]
            )

        # Select template and format
        template = random.choice(templates)
        if "{improvements}" in template:
            improvements_text = ", ".join(improvement_types[:2])  # Limit to 2 types
            instruction = template.format(improvements=improvements_text.lower())
        else:
            instruction = template

        return instruction

    def _generate_context(self, result: EvolutionResult) -> str:
        """Generate context for the training example."""
        context_parts = []

        if result.task_description:
            context_parts.append(f"Task: {result.task_description}")

        context_parts.append(
            f"Strategy: {result.strategy.value.replace('_', ' ').title()}"
        )
        context_parts.append(f"Improvement: {result.improvement_percentage:.1f}%")

        if result.improvement_types:
            types_text = ", ".join(
                [t.value.replace("_", " ").title() for t in result.improvement_types]
            )
            context_parts.append(f"Focus areas: {types_text}")

        return " | ".join(context_parts)

    def _calculate_quality_score(self, result: EvolutionResult) -> float:
        """Calculate quality score for the training example."""
        # Base score from fitness
        base_score = result.fitness_score

        # Bonus for significant improvement
        improvement_bonus = min(0.2, result.improvement_percentage / 100)

        # Bonus for multiple improvement types
        diversity_bonus = min(0.1, len(result.improvement_types) * 0.03)

        # Penalty for very short or very long code
        orig_lines = len(result.original_code.split("\n"))
        length_penalty = 0.0
        if orig_lines < 5 or orig_lines > 80:
            length_penalty = 0.1

        quality_score = (
            base_score + improvement_bonus + diversity_bonus - length_penalty
        )
        return max(0.0, min(1.0, quality_score))

    def _validate_example(self, example: TrainingExample) -> bool:
        """Validate a training example."""
        # Quality threshold
        if example.quality_score < self.min_quality_score:
            return False

        # Length checks
        if (
            len(example.input_code) < 20
            or len(example.output_code) < 20
            or len(example.input_code) > 5000
            or len(example.output_code) > 7500
        ):
            return False

        # Content checks
        if example.input_code.strip() == example.output_code.strip():
            return False

        return True

    def _identify_pattern_type(self, result: EvolutionResult) -> str:
        """Identify the primary pattern type for an evolution result."""
        if ImprovementType.PERFORMANCE in result.improvement_types:
            return "performance_optimization"
        elif ImprovementType.ERROR_HANDLING in result.improvement_types:
            return "error_handling"
        elif ImprovementType.READABILITY in result.improvement_types:
            return "readability_improvement"
        elif ImprovementType.EFFICIENCY in result.improvement_types:
            return "efficiency_improvement"
        elif ImprovementType.DOCUMENTATION in result.improvement_types:
            return "documentation_addition"
        else:
            return "general_improvement"

    def _balance_examples(
        self, examples: List[TrainingExample]
    ) -> List[TrainingExample]:
        """Balance examples across different pattern types."""
        if len(examples) <= self.max_examples_per_pattern:
            return examples

        # Group by pattern type
        pattern_groups = defaultdict(list)
        for example in examples:
            # Get pattern type from source evolution result
            pattern_type = "general_improvement"  # Default
            for pattern, pattern_examples in self.examples_by_pattern.items():
                if example in pattern_examples:
                    pattern_type = pattern
                    break
            pattern_groups[pattern_type].append(example)

        # Balance across patterns
        balanced = []
        examples_per_pattern = self.max_examples_per_pattern // max(
            1, len(pattern_groups)
        )

        for pattern, pattern_examples in pattern_groups.items():
            # Sort by quality and take top examples
            sorted_examples = sorted(
                pattern_examples, key=lambda x: x.quality_score, reverse=True
            )
            balanced.extend(sorted_examples[:examples_per_pattern])

        return balanced

    def _add_instruction_variations(
        self, examples: List[TrainingExample]
    ) -> List[TrainingExample]:
        """Add variations to instructions for better training diversity."""
        varied_examples = []

        for example in examples:
            # Original example
            varied_examples.append(example)

            # Create variations (limit to avoid explosion)
            if len(varied_examples) < len(examples) * 2:  # Max 2x original
                # Variation 1: More specific instruction
                specific_instruction = self._make_instruction_specific(
                    example.instruction
                )
                if specific_instruction != example.instruction:
                    varied_example = TrainingExample(
                        instruction=specific_instruction,
                        input_code=example.input_code,
                        output_code=example.output_code,
                        context=example.context,
                        quality_score=example.quality_score * 0.95,  # Slightly lower
                        source_evolution_id=example.source_evolution_id,
                    )
                    varied_examples.append(varied_example)

        return varied_examples

    def _make_instruction_specific(self, instruction: str) -> str:
        """Make an instruction more specific."""
        specific_variations = {
            "Improve this code": "Analyze and improve this Python code",
            "Refactor": "Carefully refactor",
            "Optimize": "Systematically optimize",
            "Enhance": "Thoughtfully enhance",
            "code": "Python code",
        }

        specific_instruction = instruction
        for generic, specific in specific_variations.items():
            if generic in instruction and specific not in instruction:
                specific_instruction = instruction.replace(generic, specific, 1)
                break

        return specific_instruction

    def save_training_data(
        self, output_dir: Path, format_type: str = "alpaca", split_ratio: float = 0.8
    ) -> Dict[str, Path]:
        """
        Save training data in various formats.

        Args:
            output_dir: Directory to save training data
            format_type: Format type ('alpaca', 'chat', 'jsonl')
            split_ratio: Train/validation split ratio

        Returns:
            Dictionary of saved file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Split data
        random.shuffle(self.training_examples)
        split_idx = int(len(self.training_examples) * split_ratio)
        train_examples = self.training_examples[:split_idx]
        val_examples = self.training_examples[split_idx:]

        saved_files = {}

        if format_type == "alpaca":
            saved_files.update(
                self._save_alpaca_format(output_dir, train_examples, val_examples)
            )
        elif format_type == "chat":
            saved_files.update(
                self._save_chat_format(output_dir, train_examples, val_examples)
            )
        elif format_type == "jsonl":
            saved_files.update(
                self._save_jsonl_format(output_dir, train_examples, val_examples)
            )

        # Save metadata
        metadata_file = output_dir / "metadata.json"
        metadata = {
            "total_examples": len(self.training_examples),
            "train_examples": len(train_examples),
            "val_examples": len(val_examples),
            "format_type": format_type,
            "created_at": datetime.now().isoformat(),
            "pattern_distribution": {
                pattern: len(examples)
                for pattern, examples in self.examples_by_pattern.items()
            },
        }

        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        saved_files["metadata"] = metadata_file

        logger.info(f"Saved training data to {output_dir}")
        return saved_files

    def _save_alpaca_format(
        self,
        output_dir: Path,
        train_examples: List[TrainingExample],
        val_examples: List[TrainingExample],
    ) -> Dict[str, Path]:
        """Save in Alpaca instruction format."""

        def convert_to_alpaca(examples):
            return [example.to_alpaca_format() for example in examples]

        train_file = output_dir / "train_alpaca.json"
        val_file = output_dir / "val_alpaca.json"

        with open(train_file, "w") as f:
            json.dump(convert_to_alpaca(train_examples), f, indent=2)

        with open(val_file, "w") as f:
            json.dump(convert_to_alpaca(val_examples), f, indent=2)

        return {"train_alpaca": train_file, "val_alpaca": val_file}

    def _save_chat_format(
        self,
        output_dir: Path,
        train_examples: List[TrainingExample],
        val_examples: List[TrainingExample],
    ) -> Dict[str, Path]:
        """Save in chat format."""

        def convert_to_chat(examples):
            return [example.to_chat_format() for example in examples]

        train_file = output_dir / "train_chat.json"
        val_file = output_dir / "val_chat.json"

        with open(train_file, "w") as f:
            json.dump(convert_to_chat(train_examples), f, indent=2)

        with open(val_file, "w") as f:
            json.dump(convert_to_chat(val_examples), f, indent=2)

        return {"train_chat": train_file, "val_chat": val_file}

    def _save_jsonl_format(
        self,
        output_dir: Path,
        train_examples: List[TrainingExample],
        val_examples: List[TrainingExample],
    ) -> Dict[str, Path]:
        """Save in JSONL format."""
        train_file = output_dir / "train.jsonl"
        val_file = output_dir / "val.jsonl"

        with open(train_file, "w") as f:
            for example in train_examples:
                f.write(json.dumps(example.to_dict()) + "\n")

        with open(val_file, "w") as f:
            for example in val_examples:
                f.write(json.dumps(example.to_dict()) + "\n")

        return {"train_jsonl": train_file, "val_jsonl": val_file}

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about the training data."""
        if not self.training_examples:
            return {"error": "No training examples available"}

        quality_scores = [ex.quality_score for ex in self.training_examples]
        input_lengths = [len(ex.input_code) for ex in self.training_examples]
        output_lengths = [len(ex.output_code) for ex in self.training_examples]

        return {
            "total_examples": len(self.training_examples),
            "pattern_distribution": {
                pattern: len(examples)
                for pattern, examples in self.examples_by_pattern.items()
            },
            "quality_stats": {
                "avg_quality": sum(quality_scores) / len(quality_scores),
                "min_quality": min(quality_scores),
                "max_quality": max(quality_scores),
            },
            "length_stats": {
                "avg_input_length": sum(input_lengths) / len(input_lengths),
                "avg_output_length": sum(output_lengths) / len(output_lengths),
                "max_input_length": max(input_lengths),
                "max_output_length": max(output_lengths),
            },
        }

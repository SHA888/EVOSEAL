"""
Pattern analyzer for extracting generalizable knowledge from evolution results.

This module analyzes successful evolution patterns to identify common
improvement strategies that can be used to train Devstral.
"""

import ast
import difflib
import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import EvolutionResult, EvolutionStrategy, ImprovementType, PatternMatch

logger = logging.getLogger(__name__)


@dataclass
class CodeTransformation:
    """Represents a specific code transformation pattern."""

    name: str
    description: str
    before_pattern: str
    after_pattern: str
    frequency: int
    confidence: float
    examples: List[Tuple[str, str]]  # (before, after) pairs


class PatternAnalyzer:
    """
    Analyzes evolution patterns to extract generalizable knowledge.

    This class identifies common patterns in successful code transformations
    that can be used to create training data for fine-tuning Devstral.
    """

    def __init__(self, min_pattern_frequency: int = 3, min_confidence: float = 0.7):
        """
        Initialize the pattern analyzer.

        Args:
            min_pattern_frequency: Minimum occurrences for a pattern to be considered
            min_confidence: Minimum confidence score for pattern validity
        """
        self.min_pattern_frequency = min_pattern_frequency
        self.min_confidence = min_confidence

        # Pattern storage
        self.detected_patterns: List[PatternMatch] = []
        self.transformations: List[CodeTransformation] = []

        # Analysis caches
        self._ast_cache: Dict[str, ast.AST] = {}
        self._diff_cache: Dict[Tuple[str, str], List[str]] = {}

        logger.info("Pattern analyzer initialized")

    def analyze_patterns(self, results: List[EvolutionResult]) -> Dict[str, Any]:
        """Alias for analyze_results for backward compatibility."""
        return self.analyze_results(results)

    def analyze_results(self, results: List[EvolutionResult]) -> Dict[str, Any]:
        """
        Analyze a collection of evolution results to extract patterns.

        Args:
            results: List of evolution results to analyze

        Returns:
            Dictionary containing analysis results and detected patterns
        """
        logger.info(f"Analyzing {len(results)} evolution results for patterns")

        # Filter successful results
        successful_results = [r for r in results if r.success]
        logger.info(f"Found {len(successful_results)} successful results to analyze")

        if not successful_results:
            return {"error": "No successful results to analyze"}

        analysis = {
            "summary": self._generate_summary(successful_results),
            "transformation_patterns": self._analyze_transformations(
                successful_results
            ),
            "strategy_effectiveness": self._analyze_strategies(successful_results),
            "improvement_types": self._analyze_improvement_types(successful_results),
            "code_patterns": self._analyze_code_patterns(successful_results),
            "common_fixes": self._identify_common_fixes(successful_results),
            "detected_patterns": [p.to_dict() for p in self.detected_patterns],
        }

        logger.info(
            f"Pattern analysis complete. Found {len(self.detected_patterns)} patterns"
        )
        return analysis

    def _generate_summary(self, results: List[EvolutionResult]) -> Dict[str, Any]:
        """Generate summary statistics."""
        fitness_scores = [r.fitness_score for r in results]
        improvements = [r.improvement_percentage for r in results]

        return {
            "total_results": len(results),
            "avg_fitness": sum(fitness_scores) / len(fitness_scores),
            "max_fitness": max(fitness_scores),
            "min_fitness": min(fitness_scores),
            "avg_improvement": sum(improvements) / len(improvements),
            "max_improvement": max(improvements),
            "timespan_days": (
                max(r.timestamp for r in results) - min(r.timestamp for r in results)
            ).days,
        }

    def _analyze_transformations(
        self, results: List[EvolutionResult]
    ) -> Dict[str, int]:
        """Analyze common code transformations."""
        transformations = Counter()

        for result in results:
            original = result.original_code.strip()
            improved = result.improved_code.strip()

            # Detect specific transformation patterns
            patterns = self._detect_transformation_patterns(original, improved)
            for pattern in patterns:
                transformations[pattern] += 1

        # Store as transformation objects
        for pattern, count in transformations.items():
            if count >= self.min_pattern_frequency:
                self._create_transformation_pattern(pattern, count, results)

        return dict(transformations.most_common(20))

    def _detect_transformation_patterns(
        self, original: str, improved: str
    ) -> List[str]:
        """Detect specific transformation patterns between code versions."""
        patterns = []

        # Line count changes
        orig_lines = len(original.split("\n"))
        imp_lines = len(improved.split("\n"))

        if imp_lines < orig_lines * 0.8:
            patterns.append("significant_code_reduction")
        elif imp_lines > orig_lines * 1.2:
            patterns.append("significant_code_expansion")

        # Specific code patterns
        if "for " in original and any(
            comp in improved for comp in ["[", "comprehension"]
        ):
            patterns.append("for_loop_to_comprehension")

        if "if __name__" not in original and "if __name__" in improved:
            patterns.append("add_main_guard")

        if "try:" not in original and "try:" in improved:
            patterns.append("add_error_handling")

        if "import " not in original and "import " in improved:
            patterns.append("add_imports")

        if "def " not in original and "def " in improved:
            patterns.append("extract_functions")

        if "class " not in original and "class " in improved:
            patterns.append("introduce_classes")

        if '"""' not in original and '"""' in improved:
            patterns.append("add_docstrings")

        if "logging" not in original and "logging" in improved:
            patterns.append("add_logging")

        if "assert " not in original and "assert " in improved:
            patterns.append("add_assertions")

        # Type hints
        if "->" not in original and "->" in improved:
            patterns.append("add_type_hints")

        # Performance patterns
        if ".join(" in improved and "+" in original:
            patterns.append("string_concatenation_optimization")

        if "enumerate(" in improved and "range(len(" in original:
            patterns.append("use_enumerate")

        return patterns

    def _create_transformation_pattern(
        self, pattern_name: str, frequency: int, results: List[EvolutionResult]
    ):
        """Create a transformation pattern object."""
        examples = []

        # Find examples of this pattern
        for result in results:
            if pattern_name in self._detect_transformation_patterns(
                result.original_code, result.improved_code
            ):
                examples.append(
                    (result.original_code[:200], result.improved_code[:200])
                )
                if len(examples) >= 5:  # Limit examples
                    break

        transformation = CodeTransformation(
            name=pattern_name,
            description=self._get_pattern_description(pattern_name),
            before_pattern="",  # Could be filled with regex patterns
            after_pattern="",  # Could be filled with replacement patterns
            frequency=frequency,
            confidence=min(1.0, frequency / len(results)),
            examples=examples,
        )

        self.transformations.append(transformation)

    def _get_pattern_description(self, pattern_name: str) -> str:
        """Get human-readable description for a pattern."""
        descriptions = {
            "significant_code_reduction": "Significantly reduced code length while maintaining functionality",
            "significant_code_expansion": "Added substantial code for improved functionality or clarity",
            "for_loop_to_comprehension": "Converted for loops to list/dict comprehensions",
            "add_main_guard": 'Added if __name__ == "__main__" guard',
            "add_error_handling": "Added try-except error handling",
            "add_imports": "Added necessary import statements",
            "extract_functions": "Extracted code into separate functions",
            "introduce_classes": "Introduced classes for better organization",
            "add_docstrings": "Added documentation strings",
            "add_logging": "Added logging statements",
            "add_assertions": "Added assertion statements for validation",
            "add_type_hints": "Added type hints for better code clarity",
            "string_concatenation_optimization": "Optimized string concatenation using join()",
            "use_enumerate": "Replaced range(len()) with enumerate()",
        }
        return descriptions.get(
            pattern_name, f"Pattern: {pattern_name.replace('_', ' ').title()}"
        )

    def _analyze_strategies(
        self, results: List[EvolutionResult]
    ) -> Dict[str, Dict[str, float]]:
        """Analyze effectiveness of different evolution strategies."""
        strategy_scores = defaultdict(list)

        for result in results:
            strategy_scores[result.strategy].append(result.fitness_score)

        strategy_effectiveness = {}
        for strategy, scores in strategy_scores.items():
            strategy_effectiveness[str(strategy)] = {
                "count": len(scores),
                "avg_fitness": sum(scores) / len(scores),
                "max_fitness": max(scores),
                "min_fitness": min(scores),
                "std_dev": self._calculate_std_dev(scores),
            }

        return strategy_effectiveness

    def _calculate_std_dev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5

    def _analyze_improvement_types(
        self, results: List[EvolutionResult]
    ) -> Dict[str, int]:
        """Analyze types of improvements made."""
        improvement_counts = Counter()

        for result in results:
            for improvement_type in result.improvement_types:
                improvement_counts[str(improvement_type)] += 1

        return dict(improvement_counts)

    def _analyze_code_patterns(self, results: List[EvolutionResult]) -> Dict[str, Any]:
        """Analyze code-level patterns using AST analysis."""
        patterns = {
            "function_extraction": 0,
            "class_introduction": 0,
            "import_additions": 0,
            "complexity_reduction": 0,
            "documentation_addition": 0,
        }

        for result in results:
            try:
                orig_ast = self._get_ast(result.original_code)
                imp_ast = self._get_ast(result.improved_code)

                if orig_ast and imp_ast:
                    # Count functions
                    orig_funcs = len(
                        [
                            n
                            for n in ast.walk(orig_ast)
                            if isinstance(n, ast.FunctionDef)
                        ]
                    )
                    imp_funcs = len(
                        [n for n in ast.walk(imp_ast) if isinstance(n, ast.FunctionDef)]
                    )

                    if imp_funcs > orig_funcs:
                        patterns["function_extraction"] += 1

                    # Count classes
                    orig_classes = len(
                        [n for n in ast.walk(orig_ast) if isinstance(n, ast.ClassDef)]
                    )
                    imp_classes = len(
                        [n for n in ast.walk(imp_ast) if isinstance(n, ast.ClassDef)]
                    )

                    if imp_classes > orig_classes:
                        patterns["class_introduction"] += 1

                    # Count imports
                    orig_imports = len(
                        [
                            n
                            for n in ast.walk(orig_ast)
                            if isinstance(n, (ast.Import, ast.ImportFrom))
                        ]
                    )
                    imp_imports = len(
                        [
                            n
                            for n in ast.walk(imp_ast)
                            if isinstance(n, (ast.Import, ast.ImportFrom))
                        ]
                    )

                    if imp_imports > orig_imports:
                        patterns["import_additions"] += 1

            except Exception as e:
                logger.debug(f"Error in AST analysis: {e}")
                continue

        return patterns

    def _get_ast(self, code: str) -> Optional[ast.AST]:
        """Get AST for code with caching."""
        if code in self._ast_cache:
            return self._ast_cache[code]

        try:
            tree = ast.parse(code)
            self._ast_cache[code] = tree
            return tree
        except SyntaxError:
            self._ast_cache[code] = None
            return None

    def _identify_common_fixes(
        self, results: List[EvolutionResult]
    ) -> List[Dict[str, Any]]:
        """Identify common fixes applied across results."""
        fixes = []
        fix_patterns = Counter()

        for result in results:
            # Use diff to identify specific changes
            diff = list(
                difflib.unified_diff(
                    result.original_code.splitlines(),
                    result.improved_code.splitlines(),
                    lineterm="",
                )
            )

            # Analyze diff for common patterns
            for line in diff:
                if line.startswith("+") and not line.startswith("+++"):
                    added_line = line[1:].strip()

                    # Common fix patterns
                    if "try:" in added_line:
                        fix_patterns["add_error_handling"] += 1
                    elif "import " in added_line:
                        fix_patterns["add_imports"] += 1
                    elif "def " in added_line:
                        fix_patterns["extract_function"] += 1
                    elif '"""' in added_line or "'''" in added_line:
                        fix_patterns["add_documentation"] += 1
                    elif "logging." in added_line:
                        fix_patterns["add_logging"] += 1
                    elif "assert " in added_line:
                        fix_patterns["add_validation"] += 1

        # Convert to structured format
        for fix_type, count in fix_patterns.most_common(10):
            fixes.append(
                {
                    "type": fix_type,
                    "count": count,
                    "frequency": count / len(results),
                    "description": self._get_fix_description(fix_type),
                }
            )

        return fixes

    def _get_fix_description(self, fix_type: str) -> str:
        """Get description for a fix type."""
        descriptions = {
            "add_error_handling": "Added try-except blocks for error handling",
            "add_imports": "Added necessary import statements",
            "extract_function": "Extracted code into separate functions",
            "add_documentation": "Added docstrings and comments",
            "add_logging": "Added logging statements for debugging",
            "add_validation": "Added assertion statements for input validation",
        }
        return descriptions.get(
            fix_type, f"Applied fix: {fix_type.replace('_', ' ').title()}"
        )

    def get_training_patterns(self) -> List[Dict[str, Any]]:
        """Get patterns suitable for training data generation."""
        training_patterns = []

        for transformation in self.transformations:
            if (
                transformation.frequency >= self.min_pattern_frequency
                and transformation.confidence >= self.min_confidence
            ):

                training_patterns.append(
                    {
                        "name": transformation.name,
                        "description": transformation.description,
                        "frequency": transformation.frequency,
                        "confidence": transformation.confidence,
                        "examples": transformation.examples[:3],  # Limit examples
                    }
                )

        return training_patterns

    def clear_cache(self) -> None:
        """Clear analysis caches."""
        self._ast_cache.clear()
        self._diff_cache.clear()
        logger.info("Pattern analyzer caches cleared")

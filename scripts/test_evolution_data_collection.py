#!/usr/bin/env python3
"""
Test script for Phase 1: Evolution Data Collection

This script tests the evolution data collection system by creating
sample evolution results and verifying the data collection pipeline.
"""

import asyncio
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from evoseal.evolution import (
    EvolutionDataCollector,
    PatternAnalyzer,
    TrainingDataBuilder,
)
from evoseal.evolution.data_collector import create_evolution_result
from evoseal.evolution.models import EvolutionStrategy, ImprovementType

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_sample_evolution_results():
    """Create sample evolution results for testing."""
    logger.info("Creating sample evolution results...")

    sample_results = []

    # Sample 1: For loop to list comprehension
    original_code_1 = """
def process_numbers(numbers):
    result = []
    for num in numbers:
        if num > 0:
            result.append(num * 2)
    return result
"""

    improved_code_1 = """
def process_numbers(numbers):
    \"\"\"Process positive numbers by doubling them.\"\"\"
    return [num * 2 for num in numbers if num > 0]
"""

    result_1 = create_evolution_result(
        original_code=original_code_1.strip(),
        improved_code=improved_code_1.strip(),
        fitness_score=0.85,
        strategy=EvolutionStrategy.GENETIC_ALGORITHM,
        task_description="Optimize number processing function",
        generation=1,
        iteration=5,
    )
    result_1.improvement_types = [
        ImprovementType.EFFICIENCY,
        ImprovementType.READABILITY,
    ]
    sample_results.append(result_1)

    # Sample 2: Add error handling
    original_code_2 = """
def divide_numbers(a, b):
    return a / b
"""

    improved_code_2 = """
def divide_numbers(a, b):
    \"\"\"Safely divide two numbers.\"\"\"
    try:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
    except TypeError:
        raise TypeError("Both arguments must be numbers")
"""

    result_2 = create_evolution_result(
        original_code=original_code_2.strip(),
        improved_code=improved_code_2.strip(),
        fitness_score=0.92,
        strategy=EvolutionStrategy.HILL_CLIMBING,
        task_description="Add error handling to division function",
        generation=2,
        iteration=3,
    )
    result_2.improvement_types = [
        ImprovementType.ERROR_HANDLING,
        ImprovementType.DOCUMENTATION,
    ]
    sample_results.append(result_2)

    # Sample 3: Extract function
    original_code_3 = """
def analyze_data(data):
    # Validate data
    if not data:
        return None
    if not isinstance(data, list):
        return None
    
    # Process data
    total = 0
    count = 0
    for item in data:
        if isinstance(item, (int, float)):
            total += item
            count += 1
    
    if count == 0:
        return None
    
    average = total / count
    return average
"""

    improved_code_3 = """
def validate_data(data):
    \"\"\"Validate input data.\"\"\"
    if not data:
        raise ValueError("Data cannot be empty")
    if not isinstance(data, list):
        raise TypeError("Data must be a list")

def calculate_average(data):
    \"\"\"Calculate average of numeric values in data.\"\"\"
    numeric_values = [item for item in data if isinstance(item, (int, float))]
    
    if not numeric_values:
        raise ValueError("No numeric values found in data")
    
    return sum(numeric_values) / len(numeric_values)

def analyze_data(data):
    \"\"\"Analyze data and return average of numeric values.\"\"\"
    validate_data(data)
    return calculate_average(data)
"""

    result_3 = create_evolution_result(
        original_code=original_code_3.strip(),
        improved_code=improved_code_3.strip(),
        fitness_score=0.88,
        strategy=EvolutionStrategy.SIMULATED_ANNEALING,
        task_description="Refactor data analysis function",
        generation=3,
        iteration=8,
    )
    result_3.improvement_types = [
        ImprovementType.MAINTAINABILITY,
        ImprovementType.DOCUMENTATION,
        ImprovementType.ERROR_HANDLING,
    ]
    sample_results.append(result_3)

    # Sample 4: Add imports and logging
    original_code_4 = """
def process_file(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    lines = content.split('\\n')
    processed_lines = []
    
    for line in lines:
        if line.strip():
            processed_lines.append(line.upper())
    
    return processed_lines
"""

    improved_code_4 = """
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def process_file(filename):
    \"\"\"Process a text file by converting non-empty lines to uppercase.\"\"\"
    file_path = Path(filename)
    
    if not file_path.exists():
        logger.error(f"File not found: {filename}")
        raise FileNotFoundError(f"File not found: {filename}")
    
    try:
        logger.info(f"Processing file: {filename}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        processed_lines = [
            line.upper() 
            for line in content.split('\\n') 
            if line.strip()
        ]
        
        logger.info(f"Processed {len(processed_lines)} lines")
        return processed_lines
        
    except Exception as e:
        logger.error(f"Error processing file {filename}: {e}")
        raise
"""

    result_4 = create_evolution_result(
        original_code=original_code_4.strip(),
        improved_code=improved_code_4.strip(),
        fitness_score=0.91,
        strategy=EvolutionStrategy.HYBRID,
        task_description="Improve file processing with logging and error handling",
        generation=1,
        iteration=12,
    )
    result_4.improvement_types = [
        ImprovementType.ERROR_HANDLING,
        ImprovementType.DOCUMENTATION,
        ImprovementType.EFFICIENCY,
    ]
    sample_results.append(result_4)

    # Sample 5: Failed result (for testing)
    result_5 = create_evolution_result(
        original_code="print('hello')",
        improved_code="print('hello world')",
        fitness_score=0.45,  # Below threshold
        strategy=EvolutionStrategy.RANDOM_SEARCH,
        task_description="Simple print improvement",
        generation=1,
        iteration=1,
    )
    result_5.success = False
    result_5.improvement_types = [ImprovementType.STYLE]
    sample_results.append(result_5)

    logger.info(f"Created {len(sample_results)} sample evolution results")
    return sample_results


async def test_data_collector():
    """Test the evolution data collector."""
    logger.info("Testing Evolution Data Collector...")

    # Create test directory
    test_dir = Path("test_data/evolution_results")
    test_dir.mkdir(parents=True, exist_ok=True)

    # Initialize collector
    collector = EvolutionDataCollector(
        data_dir=test_dir, min_fitness_threshold=0.7, auto_save_interval=3
    )

    # Create sample results
    sample_results = create_sample_evolution_results()

    # Collect results
    for result in sample_results:
        await collector.collect_result(result)

    # Force save
    await collector.save_data(force=True)

    # Get statistics
    stats = collector.get_statistics()
    logger.info(f"Collection statistics: {json.dumps(stats, indent=2, default=str)}")

    # Test training candidates
    candidates = collector.get_training_candidates(min_samples=2)
    logger.info(f"Found {len(candidates)} training candidates")

    return collector, sample_results


def test_pattern_analyzer(sample_results):
    """Test the pattern analyzer."""
    logger.info("Testing Pattern Analyzer...")

    analyzer = PatternAnalyzer(min_pattern_frequency=1, min_confidence=0.5)

    # Analyze patterns
    analysis = analyzer.analyze_patterns(sample_results)
    logger.info(
        f"Pattern analysis results: {json.dumps(analysis, indent=2, default=str)}"
    )

    # Get training patterns
    training_patterns = analyzer.get_training_patterns()
    logger.info(f"Found {len(training_patterns)} training patterns")

    return analyzer, analysis


def test_training_data_builder(sample_results, analysis):
    """Test the training data builder."""
    logger.info("Testing Training Data Builder...")

    builder = TrainingDataBuilder(min_quality_score=0.7, max_examples_per_pattern=10)

    # Build training data
    training_examples = builder.build_training_data(sample_results, analysis)
    logger.info(f"Generated {len(training_examples)} training examples")

    # Show sample examples
    for i, example in enumerate(training_examples[:2]):
        logger.info(f"Sample training example {i+1}:")
        logger.info(f"  Instruction: {example.instruction}")
        logger.info(f"  Quality Score: {example.quality_score:.3f}")
        logger.info(f"  Input Code Length: {len(example.input_code)} chars")
        logger.info(f"  Output Code Length: {len(example.output_code)} chars")

    # Save training data
    output_dir = Path("test_data/training_data")
    saved_files = builder.save_training_data(output_dir, format_type="alpaca")
    logger.info(f"Saved training data files: {list(saved_files.keys())}")

    # Get statistics
    stats = builder.get_statistics()
    logger.info(f"Training data statistics: {json.dumps(stats, indent=2, default=str)}")

    return builder, training_examples


async def main():
    """Main test function."""
    logger.info("Starting Phase 1 Evolution Data Collection Tests")
    logger.info("=" * 60)

    try:
        # Test 1: Data Collector
        logger.info("TEST 1: Evolution Data Collector")
        collector, sample_results = await test_data_collector()
        logger.info("✅ Data Collector test passed")
        print()

        # Test 2: Pattern Analyzer
        logger.info("TEST 2: Pattern Analyzer")
        analyzer, analysis = test_pattern_analyzer(sample_results)
        logger.info("✅ Pattern Analyzer test passed")
        print()

        # Test 3: Training Data Builder
        logger.info("TEST 3: Training Data Builder")
        builder, training_examples = test_training_data_builder(
            sample_results, analysis
        )
        logger.info("✅ Training Data Builder test passed")
        print()

        # Summary
        logger.info("PHASE 1 TEST SUMMARY")
        logger.info("=" * 40)
        logger.info(
            f"✅ Evolution Data Collector: {collector.stats['total_collected']} results collected"
        )
        logger.info(
            f"✅ Pattern Analyzer: {len(analyzer.detected_patterns)} patterns detected"
        )
        logger.info(
            f"✅ Training Data Builder: {len(training_examples)} training examples generated"
        )
        logger.info("✅ All Phase 1 components working correctly!")

        # Show file outputs
        logger.info("\nGenerated Files:")
        test_data_dir = Path("test_data")
        if test_data_dir.exists():
            for file_path in test_data_dir.rglob("*"):
                if file_path.is_file():
                    logger.info(f"  📄 {file_path}")

        return True

    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

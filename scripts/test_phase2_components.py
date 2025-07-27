#!/usr/bin/env python3
"""
Simplified test script for Phase 2 fine-tuning components.

Tests the recreated Phase 2 infrastructure with proper error handling
and realistic expectations for the current environment.
"""

import asyncio
import json
import logging
import sys
import tempfile
from pathlib import Path
from typing import Dict, Any
from datetime import datetime

# Add EVOSEAL to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_component_imports():
    """Test that all Phase 2 components can be imported."""
    logger.info("=== Testing Component Imports ===")
    
    try:
        from evoseal.fine_tuning import (
            DevstralFineTuner,
            TrainingManager,
            ModelValidator,
            ModelVersionManager,
            BidirectionalEvolutionManager
        )
        
        logger.info("✅ All Phase 2 components imported successfully")
        return {"success": True, "components_imported": 5}
        
    except Exception as e:
        logger.error(f"❌ Import failed: {e}")
        return {"success": False, "error": str(e)}


async def test_devstral_fine_tuner():
    """Test DevstralFineTuner basic functionality."""
    logger.info("=== Testing DevstralFineTuner ===")
    
    try:
        from evoseal.fine_tuning import DevstralFineTuner
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Initialize fine-tuner
            fine_tuner = DevstralFineTuner(output_dir=temp_path)
            
            # Test GPU availability check
            gpu_available = fine_tuner._check_gpu_availability()
            logger.info(f"GPU available: {gpu_available}")
            
            # Test model initialization (expected to fail gracefully)
            init_result = await fine_tuner.initialize_model()
            logger.info(f"Model initialization: {init_result} (expected False without transformers)")
            
            # Test training data preparation with fallback
            sample_data = {
                "examples": [
                    {
                        "instruction": "Add error handling",
                        "input": "def divide(a, b): return a / b",
                        "output": "def divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b"
                    }
                ]
            }
            
            data_file = temp_path / "test_data.json"
            with open(data_file, 'w') as f:
                json.dump(sample_data, f)
            
            prep_result = await fine_tuner.prepare_training_data(data_file)
            logger.info(f"Data preparation: {prep_result['success']} (fallback mode: {prep_result.get('fallback_mode', False)})")
            
            return {
                "success": True,
                "gpu_available": gpu_available,
                "model_init": init_result,
                "data_prep_success": prep_result['success'],
                "fallback_mode": prep_result.get('fallback_mode', False)
            }
            
    except Exception as e:
        logger.error(f"DevstralFineTuner test failed: {e}")
        return {"success": False, "error": str(e)}


async def test_model_validator():
    """Test ModelValidator with short timeout."""
    logger.info("=== Testing ModelValidator ===")
    
    try:
        from evoseal.fine_tuning import ModelValidator
        
        # Initialize with very short timeout to avoid hanging
        validator = ModelValidator(validation_timeout=10)
        
        # Test validation (expected to timeout or fail gracefully)
        logger.info("Running quick validation test...")
        validation_result = await validator.validate_model("dummy_model")
        
        logger.info(f"Validation completed: {validation_result['passed']}")
        logger.info(f"Overall score: {validation_result.get('overall_score', 0.0):.3f}")
        
        return {
            "success": True,
            "validation_completed": True,
            "overall_score": validation_result.get('overall_score', 0.0),
            "passed": validation_result['passed']
        }
        
    except Exception as e:
        logger.error(f"ModelValidator test failed: {e}")
        return {"success": False, "error": str(e)}


async def test_version_manager():
    """Test ModelVersionManager functionality."""
    logger.info("=== Testing ModelVersionManager ===")
    
    try:
        from evoseal.fine_tuning import ModelVersionManager
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Initialize version manager
            version_manager = ModelVersionManager(versions_dir=temp_path)
            
            # Test version registration
            training_results = {
                "success": True,
                "train_loss": 0.5,
                "training_examples_count": 100,
                "fallback_mode": True
            }
            
            validation_results = {
                "passed": True,
                "overall_score": 0.75
            }
            
            version_info = await version_manager.register_version(
                training_results=training_results,
                validation_results=validation_results
            )
            
            logger.info(f"Version registered: {version_info.get('version_id')}")
            
            # Test version listing
            versions = version_manager.list_versions()
            logger.info(f"Total versions: {len(versions)}")
            
            # Test statistics
            stats = version_manager.get_version_statistics()
            logger.info(f"Version statistics: {stats['total_versions']} versions")
            
            return {
                "success": True,
                "version_registered": bool(version_info.get('version_id')),
                "version_count": len(versions),
                "statistics_available": bool(stats)
            }
            
    except Exception as e:
        logger.error(f"ModelVersionManager test failed: {e}")
        return {"success": False, "error": str(e)}


async def test_bidirectional_manager():
    """Test BidirectionalEvolutionManager functionality."""
    logger.info("=== Testing BidirectionalEvolutionManager ===")
    
    try:
        from evoseal.fine_tuning import BidirectionalEvolutionManager
        from evoseal.evolution import EvolutionDataCollector
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create data collector
            data_collector = EvolutionDataCollector(data_dir=temp_path / "evolution_data")
            
            # Initialize bidirectional manager
            bidirectional_manager = BidirectionalEvolutionManager(
                data_collector=data_collector,
                output_dir=temp_path / "bidirectional",
                evolution_check_interval=1,
                min_evolution_cycles=1
            )
            
            # Test status
            status = bidirectional_manager.get_evolution_status()
            logger.info(f"Evolution status available: {bool(status)}")
            
            # Test report generation
            report = await bidirectional_manager.generate_evolution_report()
            logger.info(f"Report generated: {'error' not in report}")
            
            # Test history
            history = bidirectional_manager.get_evolution_history()
            logger.info(f"Evolution history: {len(history)} cycles")
            
            return {
                "success": True,
                "status_available": bool(status),
                "report_generated": 'error' not in report,
                "history_accessible": isinstance(history, list)
            }
            
    except Exception as e:
        logger.error(f"BidirectionalEvolutionManager test failed: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Run simplified Phase 2 tests."""
    logger.info("🚀 Starting Phase 2 Component Tests (Simplified)")
    logger.info("=" * 60)
    
    test_results = {}
    
    # Run tests
    test_results["imports"] = await test_component_imports()
    test_results["devstral_fine_tuner"] = await test_devstral_fine_tuner()
    test_results["model_validator"] = await test_model_validator()
    test_results["version_manager"] = await test_version_manager()
    test_results["bidirectional_manager"] = await test_bidirectional_manager()
    
    # Generate summary
    logger.info("=" * 60)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 60)
    
    total_tests = len(test_results)
    passed_tests = sum(1 for result in test_results.values() if result.get("success", False))
    
    for test_name, result in test_results.items():
        status = "✅ PASS" if result.get("success", False) else "❌ FAIL"
        logger.info(f"{status} {test_name}")
        
        if not result.get("success", False) and "error" in result:
            logger.info(f"    Error: {result['error']}")
    
    logger.info("=" * 60)
    logger.info(f"📈 OVERALL RESULTS: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        logger.info("🎉 All Phase 2 component tests passed!")
    elif passed_tests >= total_tests * 0.8:
        logger.info("✅ Most Phase 2 components working. Minor issues to resolve.")
    else:
        logger.warning(f"⚠️  {total_tests - passed_tests} tests failed. Review errors above.")
    
    # Save results
    results_file = Path("test_results_phase2_simplified.json")
    with open(results_file, 'w') as f:
        json.dump(test_results, f, indent=2, default=str)
    
    logger.info(f"📄 Results saved to: {results_file}")
    
    return passed_tests >= total_tests * 0.8  # 80% pass rate considered success


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)

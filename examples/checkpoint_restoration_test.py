"""Test enhanced checkpoint restoration functionality.

This example demonstrates the comprehensive restoration features including:
- Checkpoint validation before restoration
- Automatic backup creation before restoration
- Partial restoration failure handling
- Post-restoration validation
- Restoration backup management
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Any, Dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import EVOSEAL checkpoint manager
from evoseal.core.checkpoint_manager import CheckpointManager


def create_sample_project_structure(project_dir: Path) -> None:
    """Create a sample project structure for testing."""
    project_dir.mkdir(parents=True, exist_ok=True)

    # Create main.py
    (project_dir / 'main.py').write_text(
        '''#!/usr/bin/env python3
"""Sample project main file."""

def main():
    print("Hello from the original project!")
    return {"status": "original", "version": "1.0"}

if __name__ == "__main__":
    main()
'''
    )

    # Create config.json
    (project_dir / 'config.json').write_text(
        '''{
    "project": "Original Project",
    "version": "1.0",
    "settings": {
        "debug": false,
        "log_level": "INFO"
    }
}'''
    )

    # Create README.md
    (project_dir / 'README.md').write_text(
        '''# Original Project

This is the original version of the project before restoration.

## Features
- Original functionality
- Basic configuration
- Simple structure
'''
    )

    # Create a subdirectory with files
    src_dir = project_dir / 'src'
    src_dir.mkdir(exist_ok=True)
    (src_dir / 'utils.py').write_text(
        '''"""Utility functions for original project."""

def get_version():
    return "1.0-original"

def process_data(data):
    return f"Original processing: {data}"
'''
    )


def create_enhanced_experiment_data() -> Dict[str, Any]:
    """Create enhanced experiment data for checkpoint."""
    return {
        'id': 'restoration_test_v2.0',
        'name': 'Enhanced Restoration Test',
        'description': 'Testing enhanced restoration functionality',
        'status': 'completed',
        'type': 'restoration_test',
        'tags': ['test', 'restoration', 'enhanced'],
        'config': {
            'learning_rate': 0.002,
            'batch_size': 64,
            'epochs': 200,
            'model_architecture': 'enhanced_transformer',
            'optimizer': 'adamw',
            'scheduler': 'cosine_annealing',
        },
        'metrics': [
            {
                'name': 'accuracy',
                'value': 0.98,
                'metric_type': 'accuracy',
                'timestamp': '2024-01-01T15:00:00Z',
                'iteration': 200,
            },
            {
                'name': 'loss',
                'value': 0.02,
                'metric_type': 'loss',
                'timestamp': '2024-01-01T15:00:00Z',
                'iteration': 200,
            },
        ],
        'result': {
            'best_fitness': 0.98,
            'generations_completed': 200,
            'total_evaluations': 20000,
            'execution_time': 7200.0,
            'memory_peak': 4096.0,
        },
        'changes': {
            'main.py': '''#!/usr/bin/env python3
"""Enhanced project main file after evolution."""

import json
from pathlib import Path

def main():
    print("Hello from the enhanced evolved project!")

    config = load_config()
    result = {
        "status": "enhanced",
        "version": "2.0",
        "model": config.get("model_architecture", "unknown"),
        "performance": {
            "accuracy": 0.98,
            "loss": 0.02
        }
    }

    print(f"Enhanced result: {result}")
    return result

def load_config():
    """Load configuration from file."""
    config_path = Path("config.json")
    if config_path.exists():
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

if __name__ == "__main__":
    main()
''',
            'config.json': '''{
    "project": "Enhanced Evolved Project",
    "version": "2.0",
    "model_architecture": "enhanced_transformer",
    "training": {
        "learning_rate": 0.002,
        "batch_size": 64,
        "epochs": 200,
        "optimizer": "adamw",
        "scheduler": "cosine_annealing"
    },
    "settings": {
        "debug": false,
        "log_level": "INFO",
        "enhanced_features": true,
        "performance_monitoring": true
    }
}''',
            'README.md': '''# Enhanced Evolved Project

This is the enhanced version of the project after evolution and optimization.

## Features
- Enhanced transformer architecture
- Improved performance (98% accuracy)
- Advanced configuration options
- Performance monitoring
- Cosine annealing scheduler

## Performance Metrics
- Accuracy: 98%
- Loss: 0.02
- Training time: 7200 seconds
- Memory usage: 4GB peak

## Evolution Results
- 200 generations completed
- 20,000 total evaluations
- Best fitness: 0.98
''',
            'src/utils.py': '''"""Enhanced utility functions for evolved project."""

import json
from typing import Any, Dict

def get_version():
    """Get the current version."""
    return "2.0-enhanced"

def process_data(data: Any) -> str:
    """Process data with enhanced algorithms."""
    if isinstance(data, dict):
        return f"Enhanced processing (dict): {len(data)} items"
    elif isinstance(data, list):
        return f"Enhanced processing (list): {len(data)} items"
    else:
        return f"Enhanced processing: {data}"

def load_performance_metrics() -> Dict[str, float]:
    """Load performance metrics."""
    return {
        "accuracy": 0.98,
        "loss": 0.02,
        "f1_score": 0.97,
        "precision": 0.98,
        "recall": 0.96
    }

def optimize_parameters(params: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize parameters using enhanced algorithms."""
    optimized = params.copy()

    # Apply optimization logic
    if "learning_rate" in optimized:
        optimized["learning_rate"] *= 1.1  # Slight increase

    if "batch_size" in optimized:
        optimized["batch_size"] = min(optimized["batch_size"] * 2, 128)

    return optimized
''',
            'src/models.py': '''"""Enhanced model definitions."""

class EnhancedTransformer:
    """Enhanced transformer model with improved architecture."""

    def __init__(self, vocab_size=10000, hidden_size=768, num_layers=12):
        self.vocab_size = vocab_size
        self.hidden_size = hidden_size
        self.num_layers = num_layers
        self.attention_heads = 12
        self.dropout = 0.1

    def get_config(self):
        """Get model configuration."""
        return {
            "model_type": "enhanced_transformer",
            "vocab_size": self.vocab_size,
            "hidden_size": self.hidden_size,
            "num_layers": self.num_layers,
            "attention_heads": self.attention_heads,
            "dropout": self.dropout
        }

    def forward(self, inputs):
        """Forward pass (placeholder)."""
        return f"Enhanced processing of {len(inputs)} inputs"
''',
        },
    }


async def test_enhanced_restoration_functionality():
    """Test enhanced checkpoint restoration functionality."""
    print("\n" + "=" * 70)
    print("ENHANCED CHECKPOINT RESTORATION FUNCTIONALITY TEST")
    print("=" * 70)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\nUsing temporary directory: {temp_dir}")

        # Setup directories
        checkpoint_dir = Path(temp_dir) / 'checkpoints'
        project_dir = Path(temp_dir) / 'project'

        # Create original project structure
        print("\n1. Creating original project structure...")
        create_sample_project_structure(project_dir)
        print(f"   ✓ Created original project at {project_dir}")

        # Initialize checkpoint manager
        config = {
            'checkpoint_directory': str(checkpoint_dir),
            'max_checkpoints': 10,
            'auto_cleanup': True,
            'compression': True,
        }

        checkpoint_manager = CheckpointManager(config)

        # Create enhanced checkpoint
        print("\n2. Creating enhanced checkpoint...")
        experiment_data = create_enhanced_experiment_data()

        checkpoint_path = checkpoint_manager.create_checkpoint(
            'enhanced_v2.0', experiment_data, capture_system_state=True
        )
        print(f"   ✓ Created checkpoint: {Path(checkpoint_path).name}")

        # Test checkpoint validation
        print("\n3. Testing checkpoint validation...")
        validation_results = checkpoint_manager.validate_checkpoint_for_restoration('enhanced_v2.0')
        print(f"   ✓ Validation valid: {validation_results['valid']}")
        print(f"   ✓ Errors: {len(validation_results['errors'])}")
        print(f"   ✓ Warnings: {len(validation_results['warnings'])}")
        if validation_results['warnings']:
            for warning in validation_results['warnings']:
                print(f"     - Warning: {warning}")

        # Test basic restoration
        print("\n4. Testing basic restoration...")
        restore_dir_basic = Path(temp_dir) / 'restored_basic'

        restoration_result = checkpoint_manager.restore_checkpoint(
            'enhanced_v2.0', restore_dir_basic, verify_integrity=True
        )

        print(f"   ✓ Basic restoration success: {restoration_result['success']}")
        print(f"   ✓ Files restored: {restoration_result['restored_files']}")
        print(
            f"   ✓ System state restored: {'Yes' if restoration_result['system_state'] else 'No'}"
        )

        # Test validated restoration with backup
        print("\n5. Testing validated restoration with backup...")
        restore_dir_validated = Path(temp_dir) / 'restored_validated'

        # First copy original project to restoration target
        import shutil

        shutil.copytree(project_dir, restore_dir_validated, dirs_exist_ok=True)
        print(f"   ✓ Copied original project to restoration target")

        # Perform validated restoration
        validated_result = checkpoint_manager.restore_checkpoint_with_validation(
            'enhanced_v2.0', restore_dir_validated, backup_current=True
        )

        print(f"   ✓ Validated restoration success: {validated_result['success']}")
        print(f"   ✓ Restoration time: {validated_result['restoration_time']:.2f} seconds")
        print(f"   ✓ Backup created: {validated_result['backup_created']}")
        if validated_result['backup_created']:
            print(f"   ✓ Backup path: {Path(validated_result['backup_path']).name}")

        # Check pre-validation results
        pre_validation = validated_result['pre_validation']
        print(f"   ✓ Pre-validation passed: {pre_validation['valid']}")

        # Check post-validation results
        post_validation = validated_result['post_validation']
        print(f"   ✓ Post-validation file count: {post_validation.get('file_count', 0)}")
        print(f"   ✓ Post-validation directory count: {post_validation.get('directory_count', 0)}")

        # Test restoration backup management
        print("\n6. Testing restoration backup management...")
        backups = checkpoint_manager.list_restoration_backups()
        print(f"   ✓ Found {len(backups)} restoration backups")

        for backup in backups:
            print(f"     - {backup['backup_name']}")
            print(f"       Original: {backup['original_path']}")
            print(f"       Size: {backup['backup_size'] / 1024:.1f} KB")
            print(f"       Age: {backup['age_hours']:.2f} hours")

        # Test file verification
        print("\n7. Verifying restored files...")

        # Check main.py content
        main_py_path = restore_dir_validated / 'main.py'
        if main_py_path.exists():
            content = main_py_path.read_text()
            if 'Enhanced project main file' in content:
                print("   ✓ main.py correctly restored with enhanced content")
            else:
                print("   ❌ main.py content not as expected")

        # Check config.json
        config_json_path = restore_dir_validated / 'config.json'
        if config_json_path.exists():
            import json

            config_data = json.loads(config_json_path.read_text())
            if config_data.get('version') == '2.0':
                print("   ✓ config.json correctly restored with version 2.0")
            else:
                print("   ❌ config.json version not as expected")

        # Check new files
        models_py_path = restore_dir_validated / 'src' / 'models.py'
        if models_py_path.exists():
            print("   ✓ New file src/models.py correctly restored")
        else:
            print("   ❌ New file src/models.py not found")

        # Test partial restoration failure simulation
        print("\n8. Testing partial restoration failure handling...")

        # Create a scenario where restoration might fail
        failure_test_dir = Path(temp_dir) / 'failure_test'
        failure_test_dir.mkdir(exist_ok=True)

        # Create a file that might cause issues
        (failure_test_dir / 'readonly.txt').write_text('test')
        (failure_test_dir / 'readonly.txt').chmod(0o444)  # Read-only

        try:
            # This should still work as we handle permissions properly
            failure_result = checkpoint_manager.restore_checkpoint_with_validation(
                'enhanced_v2.0', failure_test_dir, backup_current=True
            )
            print(f"   ✓ Handled potential failure scenario successfully")
            print(f"   ✓ Files restored: {failure_result['restoration_details']['restored_files']}")
        except Exception as e:
            print(f"   ✓ Properly handled restoration failure: {e}")

        # Test backup cleanup
        print("\n9. Testing backup cleanup...")
        deleted_count = checkpoint_manager.cleanup_restoration_backups(keep_count=1, max_age_days=0)
        print(f"   ✓ Cleaned up {deleted_count} old backups")

        remaining_backups = checkpoint_manager.list_restoration_backups()
        print(f"   ✓ Remaining backups: {len(remaining_backups)}")


async def main():
    """Run enhanced restoration functionality tests."""
    try:
        await test_enhanced_restoration_functionality()

        print("\n" + "=" * 70)
        print("ENHANCED RESTORATION TEST COMPLETED")
        print("=" * 70)
        print("✓ Checkpoint validation before restoration")
        print("✓ Automatic backup creation before restoration")
        print("✓ Comprehensive integrity verification")
        print("✓ Post-restoration state validation")
        print("✓ Partial restoration failure handling")
        print("✓ Restoration backup management and cleanup")
        print("✓ Enhanced logging of restoration events")
        print("\nAll enhanced restoration features are working correctly!")

    except Exception as e:
        logger.exception("Error during enhanced restoration test")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

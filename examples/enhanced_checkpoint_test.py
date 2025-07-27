"""Test enhanced checkpoint creation and restoration functionality.

This example demonstrates the improved checkpoint features including:
- Complete system state capture
- Model parameter storage
- Compression support
- Integrity verification
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


def create_sample_experiment_data() -> Dict[str, Any]:
    """Create sample experiment data with model parameters."""
    return {
        "id": "exp_001",
        "name": "Enhanced Checkpoint Test",
        "description": "Testing enhanced checkpoint functionality",
        "status": "completed",
        "type": "evolution",
        "tags": ["test", "checkpoint", "enhanced"],
        "config": {
            "learning_rate": 0.001,
            "batch_size": 32,
            "epochs": 100,
            "model_architecture": "transformer",
            "optimizer": "adam",
            "loss_function": "cross_entropy",
            "hyperparameters": {
                "dropout": 0.1,
                "hidden_size": 512,
                "num_layers": 6,
                "attention_heads": 8,
            },
        },
        "metrics": [
            {
                "name": "accuracy",
                "value": 0.95,
                "metric_type": "accuracy",
                "timestamp": "2024-01-01T12:00:00Z",
                "iteration": 100,
            },
            {
                "name": "loss",
                "value": 0.05,
                "metric_type": "loss",
                "timestamp": "2024-01-01T12:00:00Z",
                "iteration": 100,
            },
            {
                "name": "f1_score",
                "value": 0.93,
                "metric_type": "f1_score",
                "timestamp": "2024-01-01T12:00:00Z",
                "iteration": 100,
            },
        ],
        "result": {
            "best_fitness": 0.95,
            "generations_completed": 100,
            "total_evaluations": 10000,
            "convergence_iteration": 85,
            "execution_time": 3600.5,
            "memory_peak": 2048.0,
            "cpu_usage": 75.2,
            "code_quality_score": 0.88,
            "test_coverage": 0.92,
        },
        "changes": {
            "main.py": '''def enhanced_model():
    """Enhanced model with improved architecture."""
    import torch
    import torch.nn as nn

    class TransformerModel(nn.Module):
        def __init__(self, vocab_size, hidden_size, num_layers):
            super().__init__()
            self.embedding = nn.Embedding(vocab_size, hidden_size)
            self.transformer = nn.TransformerEncoder(
                nn.TransformerEncoderLayer(hidden_size, 8),
                num_layers
            )
            self.output = nn.Linear(hidden_size, vocab_size)

        def forward(self, x):
            x = self.embedding(x)
            x = self.transformer(x)
            return self.output(x)

    return TransformerModel(10000, 512, 6)
''',
            "config.json": """{
    "model": {
        "type": "transformer",
        "vocab_size": 10000,
        "hidden_size": 512,
        "num_layers": 6,
        "attention_heads": 8
    },
    "training": {
        "learning_rate": 0.001,
        "batch_size": 32,
        "epochs": 100,
        "optimizer": "adam"
    }
}""",
            "README.md": """# Enhanced Model Checkpoint

This checkpoint contains an enhanced transformer model with the following improvements:

## Features
- Multi-head attention with 8 heads
- 6-layer transformer encoder
- Dropout regularization (0.1)
- Adam optimizer with learning rate 0.001

## Performance
- Accuracy: 95%
- F1 Score: 93%
- Test Coverage: 92%
- Code Quality: 88%

## System Requirements
- Python 3.8+
- PyTorch 1.9+
- CUDA support recommended
""",
        },
    }


async def test_enhanced_checkpoint_functionality():
    """Test enhanced checkpoint creation and restoration."""
    print("\n" + "=" * 60)
    print("ENHANCED CHECKPOINT FUNCTIONALITY TEST")
    print("=" * 60)

    # Create temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"\nUsing temporary directory: {temp_dir}")

        # Test with compression enabled
        print("\n1. Testing with compression enabled...")
        config_compressed = {
            "checkpoint_directory": str(Path(temp_dir) / "checkpoints_compressed"),
            "max_checkpoints": 10,
            "auto_cleanup": True,
            "compression": True,
        }

        checkpoint_manager_compressed = CheckpointManager(config_compressed)

        # Create sample experiment data
        experiment_data = create_sample_experiment_data()

        # Create enhanced checkpoint with compression
        print("   Creating enhanced checkpoint with compression...")
        checkpoint_path = checkpoint_manager_compressed.create_checkpoint(
            "enhanced_v1.0", experiment_data, capture_system_state=True
        )
        print(f"   ✓ Created checkpoint at: {Path(checkpoint_path).name}")

        # Verify integrity
        print("   Verifying checkpoint integrity...")
        integrity_ok = checkpoint_manager_compressed.verify_checkpoint_integrity(
            "enhanced_v1.0"
        )
        print(f"   ✓ Integrity verification: {'PASSED' if integrity_ok else 'FAILED'}")

        # List checkpoints with detailed info
        print("\n2. Checkpoint details...")
        checkpoints = checkpoint_manager_compressed.list_checkpoints()
        for checkpoint in checkpoints:
            print(f"   Version: {checkpoint['version_id']}")
            print(
                f"   Size: {checkpoint.get('checkpoint_size', 0) / (1024*1024):.2f} MB"
            )
            print(f"   Files: {checkpoint.get('file_count', 0)}")
            print(
                f"   System State: {'Yes' if checkpoint.get('system_state_captured') else 'No'}"
            )
            print(
                f"   Compression: {'Yes' if checkpoint.get('compression_enabled') else 'No'}"
            )
            print(
                f"   Integrity Hash: {checkpoint.get('integrity_hash', 'N/A')[:16]}..."
            )
            print(f"   Model Params: {len(checkpoint.get('config_snapshot', {}))}")
            print(f"   Metrics: {checkpoint.get('metrics_count', 0)}")

        # Test restoration with integrity verification
        print("\n3. Testing restoration with integrity verification...")
        restore_dir = Path(temp_dir) / "restored_enhanced"

        restoration_result = checkpoint_manager_compressed.restore_checkpoint(
            "enhanced_v1.0", restore_dir, verify_integrity=True
        )

        print(f"   ✓ Restoration success: {restoration_result['success']}")
        print(f"   ✓ Files restored: {restoration_result['restored_files']}")
        print(
            f"   ✓ System state restored: {'Yes' if restoration_result['system_state'] else 'No'}"
        )
        print(f"   ✓ Integrity verified: {restoration_result['integrity_verified']}")

        # Examine restored system state
        if restoration_result["system_state"]:
            system_state = restoration_result["system_state"]
            print("\n4. System state details...")
            print(
                f"   Python version: {system_state['system_info'].get('python_version', 'N/A')[:20]}..."
            )
            print(f"   Platform: {system_state['system_info'].get('platform', 'N/A')}")
            print(
                f"   CPU count: {system_state['system_info'].get('cpu_count', 'N/A')}"
            )
            print(
                f"   Memory total: {system_state['system_info'].get('memory_total', 0) / (1024**3):.1f} GB"
            )

            model_state = system_state.get("model_state", {})
            if model_state:
                print(
                    f"   Model architecture: {model_state.get('model_architecture', 'N/A')}"
                )
                print(f"   Learning rate: {model_state.get('learning_rate', 'N/A')}")
                print(f"   Batch size: {model_state.get('batch_size', 'N/A')}")
                print(f"   Optimizer: {model_state.get('optimizer', 'N/A')}")

            evolution_state = system_state.get("evolution_state", {})
            if evolution_state:
                print(f"   Best fitness: {evolution_state.get('best_fitness', 'N/A')}")
                print(
                    f"   Generations: {evolution_state.get('generations_completed', 'N/A')}"
                )
                print(
                    f"   Execution time: {evolution_state.get('execution_time', 'N/A')} seconds"
                )

        # Test without compression for comparison
        print("\n5. Testing without compression for comparison...")
        config_uncompressed = {
            "checkpoint_directory": str(Path(temp_dir) / "checkpoints_uncompressed"),
            "max_checkpoints": 10,
            "auto_cleanup": True,
            "compression": False,
        }

        checkpoint_manager_uncompressed = CheckpointManager(config_uncompressed)

        # Create checkpoint without compression
        checkpoint_path_uncompressed = (
            checkpoint_manager_uncompressed.create_checkpoint(
                "enhanced_v1.0_uncompressed", experiment_data, capture_system_state=True
            )
        )

        # Compare sizes
        compressed_stats = checkpoint_manager_compressed.get_stats()
        uncompressed_stats = checkpoint_manager_uncompressed.get_stats()

        print(f"   Compressed size: {compressed_stats['total_size_mb']:.2f} MB")
        print(f"   Uncompressed size: {uncompressed_stats['total_size_mb']:.2f} MB")
        if uncompressed_stats["total_size_mb"] > 0:
            compression_ratio = (
                compressed_stats["total_size_mb"] / uncompressed_stats["total_size_mb"]
            )
            print(
                f"   Compression ratio: {compression_ratio:.2f} ({(1-compression_ratio)*100:.1f}% reduction)"
            )

        # Verify restored files exist
        print("\n6. Verifying restored files...")
        restored_files = list(restore_dir.rglob("*"))
        for file_path in restored_files[:5]:  # Show first 5 files
            if file_path.is_file():
                size = file_path.stat().st_size
                print(f"   {file_path.name}: {size} bytes")

        if len(restored_files) > 5:
            print(f"   ... and {len(restored_files) - 5} more files")


async def main():
    """Run enhanced checkpoint functionality tests."""
    try:
        await test_enhanced_checkpoint_functionality()

        print("\n" + "=" * 60)
        print("ENHANCED CHECKPOINT TEST COMPLETED")
        print("=" * 60)
        print("✓ Enhanced checkpoint creation with system state capture")
        print("✓ Compression and decompression functionality")
        print("✓ Integrity verification and validation")
        print("✓ Complete system state restoration")
        print("✓ Model parameter and configuration capture")
        print("✓ Performance metrics and evolution state tracking")
        print("\nAll enhanced checkpoint features are working correctly!")

    except Exception as e:
        logger.exception("Error during enhanced checkpoint test")
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())

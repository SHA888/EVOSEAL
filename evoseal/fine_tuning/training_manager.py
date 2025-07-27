"""
Training manager for coordinating the fine-tuning pipeline.

This module orchestrates the complete training workflow from data preparation
to model validation and versioning.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..evolution import EvolutionDataCollector
from .model_fine_tuner import DevstralFineTuner
from .model_validator import ModelValidator
from .version_manager import ModelVersionManager

logger = logging.getLogger(__name__)


class TrainingManager:
    """
    Manages the complete training pipeline.

    This class coordinates data preparation, fine-tuning, validation,
    and versioning in a unified workflow.
    """

    def __init__(
        self,
        data_collector: Optional[EvolutionDataCollector] = None,
        fine_tuner: Optional[DevstralFineTuner] = None,
        validator: Optional[ModelValidator] = None,
        version_manager: Optional[ModelVersionManager] = None,
        output_dir: Optional[Path] = None,
        min_training_samples: int = 100,
    ):
        """
        Initialize the training manager.

        Args:
            data_collector: Evolution data collector instance
            fine_tuner: Model fine-tuner instance
            validator: Model validator instance
            version_manager: Version manager instance
            output_dir: Output directory for training artifacts
            min_training_samples: Minimum samples required for training
        """
        self.output_dir = output_dir or Path("data/training")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.data_collector = data_collector
        self.fine_tuner = fine_tuner or DevstralFineTuner(
            output_dir=self.output_dir / "models"
        )
        self.validator = validator or ModelValidator()
        self.version_manager = version_manager or ModelVersionManager(
            versions_dir=self.output_dir / "versions"
        )

        # Training configuration
        self.min_training_samples = min_training_samples

        # Training state
        self.current_training = None
        self.last_training_time = None

        logger.info(
            f"TrainingManager initialized with {min_training_samples} min samples"
        )

    async def check_training_readiness(self) -> Dict[str, Any]:
        """
        Check if the system is ready for training.

        Returns:
            Readiness status and details
        """
        try:
            readiness = {
                "ready": False,
                "reason": "",
                "details": {},
                "timestamp": datetime.now().isoformat(),
            }

            # Check if data collector is available
            if not self.data_collector:
                readiness["reason"] = "No data collector available"
                return readiness

            # Get training candidates
            stats = self.data_collector.get_statistics()
            training_candidates = stats.get("training_candidates", 0)

            readiness["details"]["training_candidates"] = training_candidates
            readiness["details"]["min_required"] = self.min_training_samples

            # Check minimum sample requirement
            if training_candidates < self.min_training_samples:
                readiness["reason"] = (
                    f"Insufficient training samples: {training_candidates} < {self.min_training_samples}"
                )
                logger.info(
                    f"Training readiness: False ({training_candidates} candidates)"
                )
                return readiness

            # Check if training is already in progress
            if self.current_training:
                readiness["reason"] = "Training already in progress"
                readiness["details"]["current_training"] = self.current_training
                return readiness

            # Check recent training history
            if self.last_training_time:
                time_since_last = datetime.now() - self.last_training_time
                min_interval = timedelta(hours=1)  # Minimum 1 hour between trainings

                if time_since_last < min_interval:
                    remaining = min_interval - time_since_last
                    readiness["reason"] = (
                        f"Too soon since last training. Wait {remaining}"
                    )
                    readiness["details"]["time_since_last"] = str(time_since_last)
                    return readiness

            # All checks passed
            readiness["ready"] = True
            readiness["reason"] = "Ready for training"

            logger.info(f"Training readiness: True ({training_candidates} candidates)")
            return readiness

        except Exception as e:
            logger.error(f"Error checking training readiness: {e}")
            return {
                "ready": False,
                "reason": f"Error: {str(e)}",
                "timestamp": datetime.now().isoformat(),
            }

    async def prepare_training_data(self) -> Dict[str, Any]:
        """
        Prepare training data from evolution results.

        Returns:
            Data preparation results
        """
        try:
            logger.info("Preparing training data...")

            if not self.data_collector:
                return {"success": False, "error": "No data collector available"}

            # Get training data from evolution results
            from ..evolution.training_data_builder import TrainingDataBuilder

            builder = TrainingDataBuilder()

            # Get recent evolution results
            results = self.data_collector.get_recent_results(days=7)

            if not results:
                return {
                    "success": False,
                    "error": "No recent evolution results available",
                }

            # Build training dataset
            training_data = await builder.build_training_dataset(results)

            if not training_data.get("success"):
                return {"success": False, "error": "Failed to build training dataset"}

            # Save training data
            data_file = (
                self.output_dir
                / f"training_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )

            with open(data_file, "w") as f:
                import json

                json.dump(training_data["dataset"], f, indent=2)

            logger.info(
                f"Training data prepared: {len(training_data['dataset']['examples'])} examples"
            )

            return {
                "success": True,
                "data_file": str(data_file),
                "examples_count": len(training_data["dataset"]["examples"]),
                "quality_score": training_data["dataset"]["metadata"]["quality_score"],
                "preparation_time": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error preparing training data: {e}")
            return {"success": False, "error": str(e)}

    async def run_training_cycle(self) -> Dict[str, Any]:
        """
        Run a complete training cycle.

        Returns:
            Training cycle results
        """
        try:
            cycle_start = datetime.now()
            self.current_training = {
                "start_time": cycle_start,
                "status": "running",
                "phase": "initialization",
            }

            logger.info("Starting training cycle...")

            # Phase 1: Check readiness
            self.current_training["phase"] = "readiness_check"
            readiness = await self.check_training_readiness()

            if not readiness["ready"]:
                self.current_training = None
                return {
                    "success": False,
                    "phase": "readiness_check",
                    "error": readiness["reason"],
                    "details": readiness,
                }

            # Phase 2: Prepare training data
            self.current_training["phase"] = "data_preparation"
            data_prep_results = await self.prepare_training_data()

            if not data_prep_results["success"]:
                self.current_training = None
                return {
                    "success": False,
                    "phase": "data_preparation",
                    "error": data_prep_results["error"],
                    "data_prep_results": data_prep_results,
                }

            # Phase 3: Fine-tune model
            self.current_training["phase"] = "fine_tuning"
            training_results = await self.fine_tuner.fine_tune_model(
                training_data_path=data_prep_results["data_file"],
                epochs=3,
                learning_rate=2e-4,
            )

            if not training_results["success"]:
                self.current_training = None
                return {
                    "success": False,
                    "phase": "fine_tuning",
                    "error": training_results.get("error", "Fine-tuning failed"),
                    "training_results": training_results,
                    "data_prep_results": data_prep_results,
                }

            # Phase 4: Validate model
            self.current_training["phase"] = "validation"
            model_path = training_results.get("model_save_path")
            validation_results = await self.validator.validate_model(model_path)

            # Phase 5: Version management
            self.current_training["phase"] = "versioning"
            version_info = await self.version_manager.register_version(
                training_results=training_results,
                validation_results=validation_results,
                data_prep_results=data_prep_results,
            )

            # Complete training cycle
            cycle_duration = (datetime.now() - cycle_start).total_seconds()
            self.last_training_time = datetime.now()
            self.current_training = None

            logger.info(f"Training cycle completed in {cycle_duration:.2f}s")

            return {
                "success": True,
                "cycle_duration": cycle_duration,
                "data_prep_results": data_prep_results,
                "training_results": training_results,
                "validation_results": validation_results,
                "version_info": version_info,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error in training cycle: {e}")
            self.current_training = None
            return {
                "success": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    async def get_training_status(self) -> Dict[str, Any]:
        """Get current training status."""
        status = {
            "is_training": self.current_training is not None,
            "last_training_time": (
                self.last_training_time.isoformat() if self.last_training_time else None
            ),
            "output_directory": str(self.output_dir),
            "min_training_samples": self.min_training_samples,
        }

        if self.current_training:
            status["current_training"] = {
                "start_time": self.current_training["start_time"].isoformat(),
                "status": self.current_training["status"],
                "phase": self.current_training["phase"],
                "duration": (
                    datetime.now() - self.current_training["start_time"]
                ).total_seconds(),
            }

        # Add readiness check
        readiness = await self.check_training_readiness()
        status["readiness"] = readiness

        return status

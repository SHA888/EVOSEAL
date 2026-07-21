"""
Continuous Evolution Service for EVOSEAL Bidirectional Evolution.

This service orchestrates the continuous improvement loop between EVOSEAL and its coding model,
managing the complete lifecycle of evolution data collection, fine-tuning, validation,
and deployment.
"""

import asyncio
import json
import logging
import signal
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import SEALConfig
from ..core.evolution_pipeline import EvolutionPipeline
from ..evolution import EvolutionDataCollector
from ..evolution.data_collector import create_evolution_result
from ..evolution.models import EvolutionStrategy
from ..fine_tuning import BidirectionalEvolutionManager

logger = logging.getLogger(__name__)


class ContinuousEvolutionService:
    """
    Service for continuous bidirectional evolution between EVOSEAL and its coding model.

    This service runs continuously, monitoring for evolution data, triggering
    fine-tuning when appropriate, and managing the bidirectional improvement cycle.
    """

    def __init__(
        self,
        config: SEALConfig | None = None,
        data_dir: Path | None = None,
        evolution_interval: int = 3600,  # 1 hour
        training_check_interval: int = 1800,  # 30 minutes
        min_evolution_samples: int = 50,
        pipeline: EvolutionPipeline | None = None,
        evolution_iterations: int = 1,
    ):
        """
        Initialize the continuous evolution service.

        Args:
            config: EVOSEAL configuration
            data_dir: Data directory for evolution and training data
            evolution_interval: Seconds between evolution cycles
            training_check_interval: Seconds between training readiness checks
            min_evolution_samples: Minimum samples needed to trigger training
        """
        self.config = config or SEALConfig()
        self.data_dir = data_dir or Path("data/continuous_evolution")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Timing configuration
        self.evolution_interval = timedelta(seconds=evolution_interval)
        self.training_check_interval = timedelta(seconds=training_check_interval)
        self.min_evolution_samples = min_evolution_samples
        self.evolution_iterations = evolution_iterations

        # Initialize components
        self._pipeline = pipeline
        self.data_collector = EvolutionDataCollector(data_dir=self.data_dir / "evolution_data")

        self.bidirectional_manager = BidirectionalEvolutionManager(
            data_collector=self.data_collector,
            output_dir=self.data_dir / "bidirectional",
            evolution_check_interval=evolution_interval // 60,  # Convert to minutes
            min_evolution_cycles=min_evolution_samples,
        )

        # Service state
        self.is_running = False
        self.start_time = None
        self.last_evolution_check = None
        self.last_training_check = None
        self.shutdown_event = asyncio.Event()

        # Statistics
        self.service_stats = {
            "evolution_cycles_completed": 0,
            "training_cycles_triggered": 0,
            "successful_improvements": 0,
            "total_uptime_seconds": 0,
            "last_activity": None,
        }

        # Setup signal handlers
        self._setup_signal_handlers()

        logger.info("ContinuousEvolutionService initialized")

    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating graceful shutdown...")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def start(self):
        """Start the continuous evolution service."""
        if self.is_running:
            logger.warning("Service is already running")
            return

        logger.info("🚀 Starting Continuous Evolution Service")
        self.is_running = True
        self.start_time = datetime.now()
        self.last_evolution_check = datetime.now()
        self.last_training_check = datetime.now()

        try:
            # Start main service loop
            await self._run_service_loop()

        except Exception as e:
            logger.error(f"Service error: {e}")
            raise
        finally:
            await self._cleanup()

    async def shutdown(self):
        """Gracefully shutdown the service."""
        logger.info("🛑 Shutting down Continuous Evolution Service")
        self.is_running = False
        self.shutdown_event.set()

        # Generate final report
        try:
            final_report = await self.generate_service_report()
            report_file = (
                self.data_dir
                / f"final_service_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(report_file, "w") as f:
                json.dump(final_report, f, indent=2, default=str)
            logger.info(f"Final service report saved: {report_file}")
        except Exception as e:
            logger.error(f"Error generating final report: {e}")

    async def _run_service_loop(self):
        """Main service loop for continuous evolution."""
        logger.info("📊 Starting continuous evolution monitoring loop")

        while self.is_running and not self.shutdown_event.is_set():
            try:
                current_time = datetime.now()

                # Check if it's time for evolution cycle
                if current_time - self.last_evolution_check >= self.evolution_interval:
                    await self._run_evolution_cycle()
                    self.last_evolution_check = current_time

                # Check if it's time for training readiness check
                if current_time - self.last_training_check >= self.training_check_interval:
                    await self._check_training_readiness()
                    self.last_training_check = current_time

                # Update service statistics
                self._update_service_stats()

                # Wait before next iteration (check every 60 seconds)
                try:
                    await asyncio.wait_for(self.shutdown_event.wait(), timeout=60.0)
                    break  # Shutdown requested
                except TimeoutError:
                    continue  # Normal timeout, continue loop

            except Exception as e:
                logger.error(f"Error in service loop: {e}")
                await asyncio.sleep(60)  # Wait before retrying

    def _get_pipeline(self) -> EvolutionPipeline:
        """Lazily initialise the EvolutionPipeline on first use."""
        if self._pipeline is None:
            if hasattr(self.config, "model_dump"):
                seal_config = self.config.model_dump()
            else:
                logger.warning(
                    f"Service config {type(self.config).__name__!r} has no model_dump(); "
                    "EvolutionPipeline will run with an empty seal_config"
                )
                seal_config = {}
            self._pipeline = EvolutionPipeline(config={"seal_config": seal_config})
        return self._pipeline

    async def _run_evolution_cycle(self):
        """Run an evolution cycle using the real EvolutionPipeline."""
        logger.info("🧬 Starting evolution cycle")

        try:
            pipeline = self._get_pipeline()
            results = await pipeline.run_evolution_cycle(iterations=self.evolution_iterations)

            if not isinstance(results, list):
                logger.error(
                    f"Unexpected pipeline return type {type(results).__name__} "
                    f"(expected list); skipping result processing"
                )
                return

            for result in results:
                if result.get("success"):
                    logger.info(
                        f"Evolution iteration {result.get('iteration', '?')} "
                        f"succeeded (improvement={result.get('is_improvement', False)})"
                    )
                else:
                    logger.warning(
                        f"Evolution iteration {result.get('iteration', '?')} "
                        f"failed: {result.get('error', 'unknown')}"
                    )

                # Only persist successful results with meaningful fitness.
                # Failed iterations have no useful code output for fine-tuning,
                # and counting them toward total_collected would inflate the
                # training-readiness sample count with garbage data.
                if not result.get("success"):
                    continue

                original_code = result.get("original_code", "")
                improved_code = result.get("improved_code", "")
                if not (original_code or improved_code):
                    # EvolutionPipeline doesn't return a code diff yet, so there's
                    # nothing here to fine-tune on. Skip persisting a codeless
                    # placeholder — counting it toward training readiness would
                    # let training fire on records with no actual code.
                    logger.debug(
                        f"Evolution iteration {result.get('iteration', '?')} produced no "
                        "code diff; skipping data_collector persistence"
                    )
                    continue

                metrics = result.get("metrics", {})
                if "fitness" not in metrics:
                    logger.warning(
                        f"Evolution iteration {result.get('iteration', '?')} metrics missing "
                        "'fitness'; defaulting to 0.5"
                    )
                fitness = metrics.get("fitness", 0.5)

                # Persist result to data_collector so training readiness checks see it
                try:
                    # NOTE: EvolutionPipeline has no strategy selection; using
                    # GENETIC_ALGORITHM as a placeholder label.  Revisit if the
                    # pipeline gains multi-strategy support.
                    evo_result = create_evolution_result(
                        original_code=original_code,
                        improved_code=improved_code,
                        fitness_score=fitness,
                        strategy=EvolutionStrategy.GENETIC_ALGORITHM,
                        task_description=f"Pipeline iteration {result.get('iteration', '?')}",
                        iteration=result.get("iteration", 1),
                        model_version="pipeline",
                        metadata={"pipeline_result": result},
                    )
                    await self.data_collector.collect_result(evo_result)
                except Exception as collect_err:
                    logger.warning(
                        f"Failed to persist evolution result to data_collector: {collect_err}"
                    )

            # Update statistics
            self.service_stats["evolution_cycles_completed"] += 1
            self.service_stats["last_activity"] = datetime.now()

            logger.info("✅ Evolution cycle completed")

        except Exception as e:
            logger.error(f"Error in evolution cycle: {e}")

    async def _check_training_readiness(self):
        """Check if training should be triggered."""
        logger.info("🔍 Checking training readiness")

        try:
            # Check if we have enough successful evolution data for training.
            # Use successful_count (not total_collected) so failed iterations
            # don't inflate the sample count.
            evolution_stats = self.data_collector.get_statistics()
            collection_stats = evolution_stats.get("collection_stats", {})
            total_results = collection_stats.get("successful_count", 0)

            if total_results >= self.min_evolution_samples:
                logger.info(
                    f"Training threshold met: {total_results} >= {self.min_evolution_samples}"
                )
                await self._trigger_training_cycle()
            else:
                logger.info(
                    f"Training threshold not met: {total_results} < {self.min_evolution_samples}"
                )

        except Exception as e:
            logger.error(f"Error checking training readiness: {e}")

    async def _trigger_training_cycle(self):
        """Trigger a complete training cycle."""
        logger.info("🎯 Triggering training cycle")

        try:
            # Get training manager from bidirectional manager
            training_manager = self.bidirectional_manager.training_manager

            # Check training readiness
            training_status = await training_manager.get_training_status()

            if training_status.get("ready_for_training", False):
                logger.info("🚀 Starting fine-tuning process")

                # Run training cycle
                training_result = await training_manager.run_training_cycle()

                if training_result.get("success", False):
                    logger.info("✅ Training cycle completed successfully")
                    self.service_stats["training_cycles_triggered"] += 1

                    # Check if this resulted in an improvement
                    if training_result.get("validation_results", {}).get("passed", False):
                        self.service_stats["successful_improvements"] += 1
                        logger.info("🎉 Model improvement achieved!")
                else:
                    logger.warning("⚠️ Training cycle completed with issues")
            else:
                logger.info("Training not ready yet")

        except Exception as e:
            logger.error(f"Error in training cycle: {e}")

    def _update_service_stats(self):
        """Update service statistics."""
        if self.start_time:
            self.service_stats["total_uptime_seconds"] = (
                datetime.now() - self.start_time
            ).total_seconds()

    async def generate_service_report(self) -> dict[str, Any]:
        """Generate comprehensive service report."""
        try:
            # Get bidirectional evolution report
            evolution_report = await self.bidirectional_manager.generate_evolution_report()

            # Get service statistics
            service_report = {
                "service_info": {
                    "service_name": "ContinuousEvolutionService",
                    "version": "1.0.0",
                    "start_time": (self.start_time.isoformat() if self.start_time else None),
                    "current_time": datetime.now().isoformat(),
                    "is_running": self.is_running,
                },
                "service_statistics": self.service_stats.copy(),
                "configuration": {
                    "evolution_interval_seconds": self.evolution_interval.total_seconds(),
                    "training_check_interval_seconds": self.training_check_interval.total_seconds(),
                    "min_evolution_samples": self.min_evolution_samples,
                    "data_directory": str(self.data_dir),
                },
                "evolution_report": evolution_report,
                "performance_metrics": self._calculate_performance_metrics(),
            }

            # Convert datetime objects
            for key, value in service_report["service_statistics"].items():
                if isinstance(value, datetime):
                    service_report["service_statistics"][key] = value.isoformat()

            return service_report

        except Exception as e:
            logger.error(f"Error generating service report: {e}")
            return {"error": str(e)}

    def _calculate_performance_metrics(self) -> dict[str, Any]:
        """Calculate performance metrics."""
        metrics = {}

        if self.service_stats["total_uptime_seconds"] > 0:
            uptime_hours = self.service_stats["total_uptime_seconds"] / 3600

            metrics["cycles_per_hour"] = (
                self.service_stats["evolution_cycles_completed"] / uptime_hours
            )

            metrics["training_cycles_per_day"] = self.service_stats[
                "training_cycles_triggered"
            ] / max(1, uptime_hours / 24)

            if self.service_stats["training_cycles_triggered"] > 0:
                metrics["improvement_success_rate"] = (
                    self.service_stats["successful_improvements"]
                    / self.service_stats["training_cycles_triggered"]
                )

        return metrics

    async def _cleanup(self):
        """Cleanup resources."""
        logger.info("🧹 Cleaning up service resources")
        # Add any cleanup logic here

    def get_service_status(self) -> dict[str, Any]:
        """Get current service status."""
        return {
            "is_running": self.is_running,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "uptime_seconds": self.service_stats["total_uptime_seconds"],
            "last_evolution_check": (
                self.last_evolution_check.isoformat() if self.last_evolution_check else None
            ),
            "last_training_check": (
                self.last_training_check.isoformat() if self.last_training_check else None
            ),
            "statistics": self.service_stats.copy(),
        }


async def main():
    """Main entry point for running the service."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler("continuous_evolution.log"),
            logging.StreamHandler(sys.stdout),
        ],
    )

    # Create and start service
    service = ContinuousEvolutionService()

    try:
        await service.start()
    except KeyboardInterrupt:
        logger.info("Service interrupted by user")
    except Exception as e:
        logger.error(f"Service failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

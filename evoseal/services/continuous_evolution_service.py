"""
Continuous Evolution Service for EVOSEAL Bidirectional Evolution.

This service orchestrates the continuous improvement loop between EVOSEAL and its coding model,
managing the complete lifecycle of evolution data collection, fine-tuning, validation,
and deployment.
"""

import asyncio
import difflib
import json
import logging
import math
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
            pipeline: Pre-constructed EvolutionPipeline instance.  When *None*
                (the default) the service creates one lazily on first use via
                ``_get_pipeline``.
            evolution_iterations: Number of iterations passed to
                ``EvolutionPipeline.run_evolution_cycle`` on each cycle.
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
        self._original_sigint = None
        self._original_sigterm = None
        self._shutting_down = False

        # Statistics
        self.service_stats = {
            "evolution_cycles_completed": 0,
            "evolution_cycle_errors": 0,
            "results_skipped": 0,
            "results_failed": 0,
            "training_cycles_triggered": 0,
            "successful_improvements": 0,
            "total_uptime_seconds": 0,
            "last_activity": None,
        }

        logger.info("ContinuousEvolutionService initialized")

    def _setup_signal_handlers(self) -> None:
        """Install signal handlers for graceful shutdown.

        Must be called from ``start()`` (inside a running event loop),
        not from ``__init__`` — ``signal.signal()`` only works on the
        main thread, and the handler needs a live event loop to schedule
        the ``shutdown()`` coroutine.
        """
        loop = asyncio.get_running_loop()

        def _handler(signum: int, frame: Any) -> None:
            logger.info("Received signal %s, initiating graceful shutdown...", signum)
            if loop.is_closed():
                logger.warning(
                    "Event loop already closed, cannot schedule shutdown for signal %s",
                    signum,
                )
                return
            try:
                loop.call_soon_threadsafe(asyncio.ensure_future, self.shutdown())
            except RuntimeError:
                # Loop stopped/closed between our check and the call
                logger.warning(
                    "Failed to schedule shutdown for signal %s (loop stopped)",
                    signum,
                )

        self._original_sigint = signal.signal(signal.SIGINT, _handler)
        self._original_sigterm = signal.signal(signal.SIGTERM, _handler)

    def _restore_signal_handlers(self) -> None:
        """Restore the signal handlers that were active before ``start()``."""
        if self._original_sigint is not None:
            signal.signal(signal.SIGINT, self._original_sigint)
            self._original_sigint = None
        if self._original_sigterm is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm)
            self._original_sigterm = None

    async def start(self):
        """Start the continuous evolution service."""
        if self.is_running:
            logger.warning("Service is already running")
            return

        logger.info("🚀 Starting Continuous Evolution Service")
        self._shutting_down = False
        self.is_running = True
        self.start_time = datetime.now()
        self.last_evolution_check = datetime.now()
        self.last_training_check = datetime.now()

        try:
            # Install signal handlers now that we're in an async context.
            # This is inside the try so that if signal.signal() raises (e.g.
            # off the main thread), the finally block resets is_running and
            # runs cleanup.
            self._setup_signal_handlers()

            # Start main service loop
            await self._run_service_loop()

        except Exception as e:
            logger.error(f"Service error: {e}")
            raise
        finally:
            await self._cleanup()

    async def shutdown(self):
        """Gracefully shutdown the service."""
        if self._shutting_down:
            return
        self._shutting_down = True

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
                raise TypeError(
                    f"Service config {type(self.config).__name__!r} has no model_dump(); "
                    "cannot serialize seal_config for EvolutionPipeline. "
                    "Inject a pre-built pipeline via the `pipeline` constructor "
                    "parameter, or pass a config object that implements model_dump()."
                )
            self._pipeline = EvolutionPipeline(config={"seal_config": seal_config})
        return self._pipeline

    async def _run_evolution_cycle(self):
        """Run an evolution cycle using the real EvolutionPipeline."""
        logger.info("🧬 Starting evolution cycle")

        # This try/except is scoped to pipeline construction only, so a TypeError
        # (or any other exception) raised later — in the pipeline run or result
        # loop — is a different failure mode and isn't caught here.
        try:
            pipeline = self._get_pipeline()
        except TypeError as e:
            logger.critical(
                f"Configuration error building pipeline: {e}\n"
                "Hint: inject a pre-built pipeline via the `pipeline` constructor "
                "parameter, or pass a config that implements model_dump()."
            )
            self.service_stats["evolution_cycle_errors"] += 1
            return
        except Exception as e:
            logger.critical(f"Failed to build EvolutionPipeline: {e}")
            self.service_stats["evolution_cycle_errors"] += 1
            return

        try:
            results = await pipeline.run_evolution_cycle(iterations=self.evolution_iterations)

            if not isinstance(results, (list, tuple)):
                logger.error(
                    f"Unexpected pipeline return type {type(results).__name__} "
                    f"(expected list); skipping result processing"
                )
                self.service_stats["evolution_cycle_errors"] += 1
                return

            for result in results:
                # Per-item guard: a malformed result must not abort the
                # remaining batch or corrupt cycle-level stats.
                try:
                    # Log iteration outcome inside the guard so a non-dict
                    # entry (None, str, etc.) is caught per-item instead of
                    # aborting the whole batch via AttributeError.
                    if not isinstance(result, dict):
                        logger.warning(f"Skipping non-dict pipeline result: {result!r}")
                        self.service_stats["results_skipped"] += 1
                        continue

                    success = result.get("success")
                    if success:
                        logger.info(
                            f"Evolution iteration {result.get('iteration', '?')} "
                            f"succeeded (improvement={result.get('is_improvement', False)})"
                        )
                    else:
                        logger.warning(
                            f"Evolution iteration {result.get('iteration', '?')} "
                            f"failed: {result.get('error', 'unknown')}"
                        )
                        self.service_stats["results_failed"] += 1

                    # Only persist successful results with numeric (non-bool) fitness.
                    # Failed iterations have no useful code output for fine-tuning,
                    # and counting them toward total_collected would inflate the
                    # training-readiness sample count with garbage data.
                    if not success:
                        continue

                    original_code = result.get("original_code", "")
                    improved_code = result.get("improved_code", "")
                    if not (original_code and improved_code):
                        # EvolutionPipeline doesn't return a code diff yet, so there's
                        # nothing here to fine-tune on. Skip persisting a codeless
                        # placeholder — counting it toward training readiness would
                        # let training fire on records with no actual code.
                        logger.debug(
                            f"Evolution iteration {result.get('iteration', '?')} produced no "
                            "code diff; skipping data_collector persistence"
                        )
                        self.service_stats["results_skipped"] += 1
                        continue

                    metrics = result.get("metrics", {})
                    fitness = metrics.get("fitness")
                    if (
                        isinstance(fitness, bool)
                        or not isinstance(fitness, (int, float))
                        or not math.isfinite(fitness)
                    ):
                        # No real (numeric) fitness signal to persist — defaulting one
                        # in, or trusting a non-numeric placeholder, would inject
                        # fabricated training signal, same reasoning as the
                        # codeless-result skip above.
                        logger.warning(
                            f"Evolution iteration {result.get('iteration', '?')} metrics missing "
                            f"a numeric 'fitness' (got {fitness!r}); skipping data_collector "
                            "persistence"
                        )
                        self.service_stats["results_skipped"] += 1
                        continue

                    # Persist result to data_collector so training readiness checks see it
                    try:
                        evo_result = create_evolution_result(
                            original_code=original_code,
                            improved_code=improved_code,
                            fitness_score=fitness,
                            strategy=EvolutionStrategy.PIPELINE,
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
                        self.service_stats["results_skipped"] += 1
                except Exception as item_err:
                    logger.warning(
                        f"Skipping malformed pipeline result {result!r}: {item_err}",
                        exc_info=True,
                    )
                    self.service_stats["results_skipped"] += 1

            # Update statistics
            self.service_stats["evolution_cycles_completed"] += 1
            self.service_stats["last_activity"] = datetime.now()

            logger.info("✅ Evolution cycle completed")

        except Exception as e:
            logger.error(f"Error in evolution cycle: {e}")
            self.service_stats["evolution_cycle_errors"] += 1

        # Check beta candidates AFTER the cycle runs so the metrics history
        # has grown since registration (design doc §4.2).  The `pipeline`
        # variable is still in scope from the construction block above; we
        # reuse it directly to avoid a redundant _get_pipeline() call.
        try:
            await self._check_beta_candidates(pipeline)
        except Exception as e:
            logger.warning("Failed to check beta candidates: %s", e)

    async def _check_beta_candidates(self, pipeline: "EvolutionPipeline") -> None:
        """Check and promote/reject active beta candidates (design doc §4.2).

        At the end of each evolution cycle, validate all beta candidates
        against their baseline metrics.  If clean, increment their cycle
        counter and promote to stable when the threshold is met.  If a
        regression is detected, reject the candidate and optionally roll back.

        Args:
            pipeline: The already-constructed pipeline instance (avoids a
                second _get_pipeline() call that would double-count
                construction failures).
        """
        gating = pipeline.rollout_gating
        if not gating.config.enabled:
            return

        beta_candidates = await gating.get_active_beta_candidates()
        if not beta_candidates:
            return

        logger.info("Checking %d beta rollout candidate(s)", len(beta_candidates))

        for cand in beta_candidates:
            try:
                # Use the candidate's own stored test_type so each
                # candidate is validated against its own baseline,
                # not the same global "latest two" snapshot.
                test_type = cand.baseline_metrics.get("test_type")
                current_metrics = pipeline.metrics_tracker.get_metrics_history(test_type)
                if len(current_metrics) < 2:
                    logger.debug(
                        "Beta candidate %s: not enough metrics history to validate",
                        cand.candidate_id,
                    )
                    continue

                # The baseline is always the second-to-last entry: the
                # candidate's own metric was recorded after registration
                # (inside execute_safe_evolution_step), so len-2 is the
                # pre-candidate baseline and len-1 is the candidate's metric.
                baseline_id = len(current_metrics) - 2
                comparison_id = len(current_metrics) - 1
                result = pipeline.validator.validate_improvement(
                    baseline_id, comparison_id, test_type
                )
                is_improvement = bool(result.get("is_improvement", False))

                if is_improvement:
                    await gating.record_clean_cycle(cand.candidate_id)
                    updated = await gating.get_candidate(cand.candidate_id)
                    if updated and updated.stage.value == "stable":
                        logger.info("🎉 Beta candidate %s promoted to stable", cand.candidate_id)
                else:
                    reason = (
                        f"Regression detected: score={result.get('score', 0.0)}, "
                        f"required_passed={result.get('required_passed')}"
                    )
                    await gating.reject_candidate(cand.candidate_id, reason)
                    logger.warning("⚠️ Beta candidate %s rejected: %s", cand.candidate_id, reason)
                    # Auto-rollback if configured
                    if gating.config.auto_rollback_on_regression and cand.checkpoint_path:
                        logger.info(
                            "Rollback needed for rejected candidate %s "
                            "(checkpoint=%s) but not yet implemented",
                            cand.candidate_id,
                            cand.checkpoint_path,
                        )
                        # The checkpoint restore is a no-op placeholder for now;
                        # full integration with CheckpointManager.restore_checkpoint
                        # is deferred until checkpoint_path is populated by the
                        # pipeline at registration time.

            except Exception as e:
                logger.warning(
                    "Error checking beta candidate %s: %s",
                    cand.candidate_id,
                    e,
                    exc_info=True,
                )

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
        self._restore_signal_handlers()

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

    def get_generation_diffs(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent evolution results with code diffs for the generation diff view.

        Each entry includes generation metadata, fitness metrics, and a
        ``unified_diff`` string showing the code change between the original
        and improved versions.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of generation diff dicts ordered by timestamp (newest first).
        """
        try:
            results = self.data_collector.get_recent_results(days=30)
        except Exception as e:
            logger.error(f"Error loading evolution results for generation diffs: {e}")
            return []

        # Sort newest first and cap
        results = sorted(results, key=lambda r: r.timestamp, reverse=True)
        results = results[:limit]

        diffs: list[dict[str, Any]] = []
        for result in results:
            unified_diff = self._compute_unified_diff(result.original_code, result.improved_code)
            diffs.append(
                {
                    "id": result.id,
                    "iteration": result.iteration,
                    "generation": result.generation,
                    "timestamp": result.timestamp.isoformat(),
                    "strategy": result.strategy.value,
                    "fitness_score": result.fitness_score,
                    "improvement_percentage": result.improvement_percentage,
                    "success": result.success,
                    "improvement_types": [t.value for t in result.improvement_types],
                    "task_description": result.task_description,
                    "model_version": result.model_version,
                    "original_metrics": result.original_metrics.to_dict()
                    if hasattr(result.original_metrics, "to_dict")
                    else {},
                    "improved_metrics": result.improved_metrics.to_dict()
                    if hasattr(result.improved_metrics, "to_dict")
                    else {},
                    "unified_diff": unified_diff,
                }
            )
        return diffs

    @staticmethod
    def _compute_unified_diff(original: str, improved: str, context: int = 3) -> str:
        """Compute a unified diff between *original* and *improved* code.

        Returns an empty string when the two are identical.
        """
        original = original or ""
        improved = improved or ""
        if not original and not improved:
            return ""
        original_lines = original.splitlines(keepends=True)
        improved_lines = improved.splitlines(keepends=True)
        diff = difflib.unified_diff(
            original_lines,
            improved_lines,
            fromfile="original",
            tofile="improved",
            n=context,
        )
        return "".join(diff)


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

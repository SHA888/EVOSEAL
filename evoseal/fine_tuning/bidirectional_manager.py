"""
Bidirectional evolution manager coordinating EVOSEAL ↔ local coding model improvement.

This module orchestrates the complete bidirectional evolution loop where EVOSEAL and
its discovered coding model continuously improve each other (weight-level, GPU-only).
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..evolution import EvolutionDataCollector
from .training_manager import TrainingManager

logger = logging.getLogger(__name__)


class BidirectionalEvolutionManager:
    """
    Manages the bidirectional evolution between EVOSEAL and its coding model.

    This class orchestrates the complete loop:
    1. EVOSEAL evolves using the coding model
    2. Collect successful evolution patterns
    3. Fine-tune the coding model with patterns
    4. Deploy the improved model
    5. Repeat with the better model
    """

    def __init__(
        self,
        data_collector: EvolutionDataCollector | None = None,
        training_manager: TrainingManager | None = None,
        output_dir: Path | None = None,
        evolution_check_interval: int = 60,  # minutes
        min_evolution_cycles: int = 10,
    ):
        """
        Initialize the bidirectional evolution manager.

        Args:
            data_collector: Evolution data collector instance
            training_manager: Training manager instance
            output_dir: Output directory for evolution data
            evolution_check_interval: Minutes between evolution checks
            min_evolution_cycles: Minimum evolution cycles before training
        """
        self.output_dir = output_dir or Path("data/bidirectional_evolution")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.data_collector = data_collector or EvolutionDataCollector(
            data_dir=self.output_dir / "evolution_data"
        )
        self.training_manager = training_manager or TrainingManager(
            data_collector=self.data_collector, output_dir=self.output_dir / "training"
        )

        # Evolution state
        self.evolution_check_interval = timedelta(minutes=evolution_check_interval)
        self.min_evolution_cycles = min_evolution_cycles
        self.is_running = False
        self.evolution_history: list[dict[str, Any]] = []
        self.last_check_time: datetime | None = None

        # Statistics
        self.stats = {
            "total_evolution_cycles": 0,
            "successful_training_cycles": 0,
            "model_improvements": 0,
            "start_time": None,
            "last_improvement": None,
        }

        logger.info("BidirectionalEvolutionManager initialized")

    # ------------------------------------------------------------------
    # Loop orchestration
    # ------------------------------------------------------------------

    async def run_loop_cycle(self) -> dict[str, Any]:
        """Execute one full bidirectional-evolution loop cycle.

        Sequence: check training readiness → run training cycle → deploy
        the improved model (if validation passed) → record results.

        Returns:
            Result dict with keys ``success``, ``phases``, ``cycle_id``,
            and ``error`` (when ``success`` is False).
        """
        cycle_start = datetime.now()
        cycle_record: dict[str, Any] = {
            "cycle_start": cycle_start.isoformat(),
            "results": {},
        }
        phases: dict[str, Any] = {}

        self.is_running = True
        self.stats["start_time"] = self.stats["start_time"] or cycle_start

        try:
            # --- Phase 1: Training readiness ---
            readiness = await self.training_manager.check_training_readiness()
            phases["readiness"] = readiness

            if not readiness.get("ready"):
                result = {
                    "success": True,
                    "skipped": True,
                    "reason": readiness.get("reason", "not ready"),
                    "phases": phases,
                }
                cycle_record["results"] = result
                self._record_cycle(cycle_record)
                result["cycle_id"] = len(self.evolution_history) - 1
                return result

            # --- Phase 2: Train ---
            training_result = await self.training_manager.run_training_cycle()
            phases["training"] = training_result

            if not training_result.get("success"):
                result = {
                    "success": False,
                    "phase": "training",
                    "error": training_result.get("error", "training failed"),
                    "phases": phases,
                }
                cycle_record["results"] = result
                self._record_cycle(cycle_record)
                result["cycle_id"] = len(self.evolution_history) - 1
                return result

            self.stats["successful_training_cycles"] += 1

            # --- Phase 3: Deploy (only when validation passed) ---
            validation = training_result.get("validation_results") or {}
            if validation.get("passed", False):
                deploy_result = await self._deploy_trained_model(training_result)
                phases["deploy"] = deploy_result

                if deploy_result.get("success"):
                    self.stats["model_improvements"] += 1
                    self.stats["last_improvement"] = datetime.now()
            else:
                phases["deploy"] = {"skipped": True, "reason": "validation did not pass"}

            result = {
                "success": True,
                "phases": phases,
            }
            cycle_record["results"] = result
            self._record_cycle(cycle_record)
            result["cycle_id"] = len(self.evolution_history) - 1
            return result

        except Exception as exc:
            logger.error(f"Error in bidirectional loop cycle: {exc}", exc_info=True)
            # Derive the failing phase from what was already populated in
            # ``phases`` so diagnostics are more useful than a blanket
            # "unknown".
            if "deploy" in phases:
                current_phase = "deploy"
            elif "training" in phases:
                current_phase = "training"
            else:
                current_phase = "readiness"
            result = {
                "success": False,
                "phase": current_phase,
                "error": str(exc),
                "phases": phases,
            }
            cycle_record["results"] = result
            self._record_cycle(cycle_record)
            result["cycle_id"] = len(self.evolution_history) - 1
            return result

        finally:
            self.is_running = False
            self.last_check_time = datetime.now()

    async def _deploy_trained_model(self, training_result: dict[str, Any]) -> dict[str, Any]:
        """Deploy the model produced by a successful training cycle.

        Looks up the version registered by :meth:`TrainingManager.run_training_cycle`
        and calls :meth:`ModelVersionManager.deploy_version` so the serving
        layer (Ollama) can load the fine-tuned model.

        Returns:
            ``{"success": True, ...}`` on deploy, or an error dict.
        """
        try:
            version_manager = self.training_manager.version_manager
            current = version_manager.get_current_version()
            if not current:
                return {"success": False, "error": "no current version after training"}

            version_id = current["version_id"]
            deploy_result = await version_manager.deploy_version(version_id)

            if "error" in deploy_result:
                return {"success": False, "error": deploy_result["error"]}

            return {"success": True, **deploy_result}

        except Exception as exc:
            logger.error(f"Error deploying trained model: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    def _record_cycle(self, cycle_record: dict[str, Any]) -> None:
        """Append a cycle record to history and update top-level stats.

        ``total_evolution_cycles`` counts **every** ``run_loop_cycle``
        invocation, including readiness-skip no-ops.  Use
        ``successful_training_cycles`` / ``model_improvements`` for
        activity-specific counts.
        """
        self.evolution_history.append(cycle_record)
        self.stats["total_evolution_cycles"] += 1

    # ------------------------------------------------------------------
    # Status / history / reporting
    # ------------------------------------------------------------------

    def get_evolution_status(self) -> dict[str, Any]:
        """Get current evolution status and statistics."""
        # Get component statuses
        data_stats = self.data_collector.get_statistics() if self.data_collector else {}

        status = {
            "is_running": self.is_running,
            "last_check": (self.last_check_time.isoformat() if self.last_check_time else None),
            "evolution_stats": self.stats.copy(),
            "data_collector_stats": data_stats,
            "recent_cycles": len(self.evolution_history),
            "output_directory": str(self.output_dir),
        }

        # Convert datetime objects
        for key, value in status["evolution_stats"].items():
            if isinstance(value, datetime):
                status["evolution_stats"][key] = value.isoformat()

        # Calculate success rate
        if self.stats["total_evolution_cycles"] > 0:
            status["success_rate"] = (
                self.stats["successful_training_cycles"] / self.stats["total_evolution_cycles"]
            )

        # Calculate improvement rate
        if self.stats["successful_training_cycles"] > 0:
            status["improvement_rate"] = (
                self.stats["model_improvements"] / self.stats["successful_training_cycles"]
            )

        return status

    def get_evolution_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """
        Get recent evolution history.

        Args:
            limit: Maximum number of recent cycles to return

        Returns:
            List of recent evolution cycle records
        """
        return self.evolution_history[-limit:] if self.evolution_history else []

    async def generate_evolution_report(self) -> dict[str, Any]:
        """Generate a comprehensive evolution report."""
        try:
            # Get current status
            status = self.get_evolution_status()

            # Get training manager status
            training_status = await self.training_manager.get_training_status()

            # Calculate runtime statistics
            runtime_stats = {}
            if self.stats["start_time"]:
                runtime = datetime.now() - self.stats["start_time"]
                runtime_stats = {
                    "total_runtime_hours": runtime.total_seconds() / 3600,
                    "cycles_per_hour": (
                        self.stats["total_evolution_cycles"]
                        / max(1, runtime.total_seconds() / 3600)
                    ),
                    "improvements_per_day": (
                        self.stats["model_improvements"] / max(1, runtime.total_seconds() / 86400)
                    ),
                }

            # Analyze evolution trends
            trends = self._analyze_evolution_trends()

            report = {
                "report_timestamp": datetime.now().isoformat(),
                "evolution_status": status,
                "training_status": training_status,
                "runtime_statistics": runtime_stats,
                "evolution_trends": trends,
                "recent_history": self.get_evolution_history(5),
                "recommendations": self._generate_recommendations(),
            }

            # Save report
            report_file = (
                self.output_dir
                / f"evolution_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            )
            with open(report_file, "w") as f:
                json.dump(report, f, indent=2, default=str)

            logger.info(f"Evolution report generated: {report_file}")
            return report

        except Exception as e:
            logger.error(f"Error generating evolution report: {e}")
            return {"error": str(e)}

    def _analyze_evolution_trends(self) -> dict[str, Any]:
        """Analyze trends in evolution performance."""
        if len(self.evolution_history) < 2:
            return {"insufficient_data": True}

        # Extract validation scores over time
        scores = []
        timestamps = []

        for cycle in self.evolution_history:
            if cycle["results"].get("success"):
                score = cycle["results"].get("validation_results", {}).get("overall_score")
                if score is not None:
                    scores.append(score)
                    timestamps.append(cycle["cycle_start"])

        if len(scores) < 2:
            return {"insufficient_validation_data": True}

        # Calculate trends
        trends = {
            "total_cycles_analyzed": len(scores),
            "average_score": sum(scores) / len(scores),
            "best_score": max(scores),
            "worst_score": min(scores),
            "latest_score": scores[-1],
            "score_improvement": scores[-1] - scores[0] if len(scores) >= 2 else 0,
            "trending_upward": scores[-1] > scores[0] if len(scores) >= 2 else None,
        }

        return trends

    def _generate_recommendations(self) -> list[str]:
        """Generate recommendations based on evolution performance."""
        recommendations = []

        # Check evolution frequency
        if self.stats["total_evolution_cycles"] == 0:
            recommendations.append(
                "No evolution cycles completed yet. Ensure EVOSEAL is generating evolution data."
            )

        # Check success rate
        if self.stats["total_evolution_cycles"] > 0:
            success_rate = (
                self.stats["successful_training_cycles"] / self.stats["total_evolution_cycles"]
            )
            if success_rate < 0.5:
                recommendations.append(
                    f"Low training success rate ({success_rate:.1%}). Review training data quality and model configuration."
                )

        # Check improvement rate
        if self.stats["successful_training_cycles"] > 0:
            improvement_rate = (
                self.stats["model_improvements"] / self.stats["successful_training_cycles"]
            )
            if improvement_rate < 0.3:
                recommendations.append(
                    f"Low improvement rate ({improvement_rate:.1%}). Consider adjusting training parameters or data collection criteria."
                )

        # Check recent activity
        if self.last_check_time:
            time_since_check = datetime.now() - self.last_check_time
            if time_since_check > timedelta(hours=2):
                recommendations.append(
                    "No recent evolution activity. Check if the system is running properly."
                )

        # Positive recommendations
        if self.stats["model_improvements"] > 0:
            recommendations.append(
                f"System has achieved {self.stats['model_improvements']} model improvements. Bidirectional evolution is working!"
            )

        if not recommendations:
            recommendations.append("Evolution system appears to be functioning normally.")

        return recommendations

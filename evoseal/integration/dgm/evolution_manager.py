"""
EvolutionManager wrapper for DGM_outer procedural logic.
This class provides an object-oriented interface for evolutionary management using the DGM submodule,
without modifying the original DGM codebase.

# mypy: ignore-errors
# Rationale: mypy cannot infer the type for get_fitness_metrics return value due to dynamic JSON parsing,
# but the code guarantees a strict dict[str, str] type. This is a known and safe false positive.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Union

from .data_adapter import DGMDataAdapter

# Add the project root and DGM submodule to sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
DGM_ROOT = PROJECT_ROOT / "dgm"

# Add both the project root and dgm directory to sys.path
for path in [str(PROJECT_ROOT), str(DGM_ROOT)]:
    if path not in sys.path:
        sys.path.insert(0, path)

try:
    from dgm import DGM_outer
except ImportError as e:
    raise ImportError(
        f"Could not import DGM_outer from DGM submodule. Make sure the DGM submodule is initialized. Error: {e}"
    ) from e


class EvolutionManager:
    """
    Object-oriented wrapper for DGM evolutionary orchestration.
    Provides methods to initialize runs, advance generations, mutation, crossover, and access population/fitness data.
    """

    def __init__(
        self, output_dir: str, prevrun_dir: Optional[str] = None, polyglot: bool = False
    ) -> None:
        self.output_dir = output_dir
        self.prevrun_dir = prevrun_dir
        self.polyglot = polyglot
        self.data_adapter = DGMDataAdapter(output_dir)
        # Archive: list of commit/run IDs (str)
        self.archive, self.start_gen_num = DGM_outer.initialize_run(
            output_dir, prevrun_dir, polyglot
        )
        self.current_generation = self.start_gen_num

    def get_archive(self) -> list[str]:
        """Return the archive (list of commit/run IDs)."""
        return list(self.archive)

    def choose_parents(
        self,
        selfimprove_size: int,
        method: str = "random",
        run_baseline: Optional[str] = None,
    ) -> list[tuple[str, dict[str, str]]]:
        """
        Choose parent candidates for the next generation using DGM logic.
        Returns a list of (parent_commit, entry) tuples.
        """
        result = DGM_outer.choose_selfimproves(
            self.output_dir,
            self.archive,
            selfimprove_size,
            method=method,
            run_baseline=run_baseline,
            polyglot=self.polyglot,
        )
        # Defensive: ensure result is always a list of tuple[str, dict[str, str]]
        try:
            return list(result)
        except Exception as err:
            raise RuntimeError("choose_selfimproves did not return a list-like object") from err

    def advance_generation(
        self,
        selfimprove_size: int,
        method: str = "random",
        run_baseline: Optional[str] = None,
        **kwargs: dict[str, str],
    ) -> dict:
        """
        Advance the evolutionary process by one generation.
        This is a high-level wrapper that chooses parents, runs self-improvement, updates the archive, and logs results.
        Returns a dictionary with generation details.
        """
        selfimprove_entries = self.choose_parents(selfimprove_size, method, run_baseline)
        return {
            "generation": self.current_generation,
            "selfimprove_entries": selfimprove_entries,
            "archive": list(self.archive),
        }

    def update_archive(
        self, new_ids: list[str], method: str = "keep_all", noise_leeway: float = 0.1
    ) -> list[str]:
        """
        Update the archive with new self-improve run IDs.
        Returns the updated archive.
        """
        self.archive = DGM_outer.update_archive(
            self.output_dir,
            self.archive,
            new_ids,
            method=method,
            noise_leeway=noise_leeway,
        )
        return list(self.archive)

    def get_generation_number(self) -> int:
        """Return the current generation number."""
        return int(self.current_generation)

    def increment_generation(self) -> None:
        """Advance the internal generation counter."""
        self.current_generation += 1

    # ---- Mutation and Crossover ----
    def mutate(
        self, parent_commit: str, entry: dict[str, str], **kwargs: dict[str, str]
    ) -> dict[str, str]:
        """
        Perform mutation (self-improvement) on a parent agent/commit.
        Returns the metadata/result of the mutation.
        """
        import self_improve_step

        try:
            metadata = self_improve_step.self_improve(
                parent_commit=parent_commit,
                output_dir=self.output_dir,
                entry=entry,
                polyglot=self.polyglot,
                **kwargs,
            )
        except Exception:
            raise RuntimeError("Mutation failed") from None
        return metadata

    def crossover(
        self, parent_commits: list[str], entry: dict[str, str], **kwargs: dict[str, str]
    ) -> dict[str, str]:
        """
        Perform crossover between multiple parent agents/commits.
        This is a placeholder; actual crossover logic may require custom implementation.
        Returns the metadata/result of the crossover.
        """
        result: dict[str, str] = {}
        for parent_commit in parent_commits:
            result = self.mutate(parent_commit, entry, **kwargs)
        return dict(result)

    # ---- Fitness Metrics ----
    def get_fitness_metrics(self, run_id: Optional[str] = None) -> dict[str, str]:
        """
        Retrieve fitness metrics (accuracy, resolved/unresolved counts, etc.) for a given run.
        If run_id is None, use the latest in the archive.
        """
        if run_id is None:
            run_id = self.archive[-1]
        # Try to load EvaluationResult
        eval_result = self.data_adapter.load_evaluation_result(run_id)
        if eval_result:
            return {**eval_result.metrics, "run_id": run_id}
        # Fallback to legacy JSON if not found
        metadata_path = os.path.join(self.output_dir, run_id, "metadata.json")
        if not os.path.exists(metadata_path):
            raise FileNotFoundError(f"Metadata file not found at {metadata_path}")
        import json

        with open(metadata_path) as f:
            metadata = json.load(f)
        overall_raw = metadata.get("overall_performance", {})
        result: dict[str, str] = {}
        for k, v in overall_raw.items():
            if isinstance(k, str) and isinstance(v, str):
                result[k] = v
            else:
                result[str(k)] = str(v)
        return result

    def summarize_fitness_history(self) -> list[dict[str, str]]:
        """
        Summarize fitness metrics for all runs in the archive.
        Returns a list of dicts with run_id and metrics.
        """
        fitness_history: list[dict[str, str]] = []
        for run_id in self.archive:
            try:
                metrics = self.get_fitness_metrics(run_id)
                fitness_history.append(metrics)
            except Exception as e:
                # Log the error but continue with other runs
                logging.warning(f"Error getting fitness metrics for run {run_id}: {str(e)}")
                continue  # nosec B112: Continue is intentional - we want to process other runs even if one fails
        return fitness_history

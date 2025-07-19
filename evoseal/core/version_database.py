"""
VersionDatabase for storing and retrieving code variants, their sources, test results,
evaluation scores, and lineage. Enhanced with experiment tracking integration.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

# Type definitions
VariantID = str
VariantInfo = dict[str, Any]
LineageInfo = dict[VariantID, list[VariantID]]
VariantHistory = list[VariantID]
VariantMetadata = dict[str, Any]  # Type alias for variant metadata

# Configure logger
logger = logging.getLogger(__name__)


class VersionDatabase:
    def __init__(self) -> None:
        # variant_id -> variant info
        self.variants: dict[str, dict[str, Any]] = {}
        # variant_id -> list of parent_ids
        self.lineage: dict[str, list[str]] = {}
        # chronological list of variant_ids
        self.history: list[str] = []
        # experiment tracking
        self.experiment_variants: dict[str, list[str]] = {}  # experiment_id -> variant_ids
        self.variant_experiments: dict[str, str] = {}  # variant_id -> experiment_id

    def add_variant(
        self,
        variant_id: str,
        source: str,
        test_results: Any,
        eval_score: float,
        parent_ids: list[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        experiment_id: Optional[str] = None,
    ) -> None:
        """Store a new code variant and its associated data."""
        variant_data = {
            "variant_id": variant_id,
            "source": source,
            "test_results": test_results,
            "eval_score": eval_score,
            "parent_ids": parent_ids or [],
            "metadata": metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "experiment_id": experiment_id,
        }

        self.variants[variant_id] = variant_data
        self.lineage[variant_id] = parent_ids or []
        self.history.append(variant_id)

        # Track experiment association
        if experiment_id:
            if experiment_id not in self.experiment_variants:
                self.experiment_variants[experiment_id] = []
            self.experiment_variants[experiment_id].append(variant_id)
            self.variant_experiments[variant_id] = experiment_id

    def get_variant(self, variant_id: str) -> dict[str, Any] | None:
        """Retrieve a variant and its data by ID.

        Args:
            variant_id: The ID of the variant to retrieve

        Returns:
            The variant data dictionary, or None if not found
        """
        return self.variants.get(variant_id)

    def get_variant_metadata(self, variant_id: VariantID) -> VariantMetadata | None:
        """Retrieve metadata for a specific variant.

        Args:
            variant_id: The ID of the variant to retrieve metadata for

        Returns:
            The variant's metadata dictionary, or None if the variant doesn't exist
        """
        variant = self.variants.get(variant_id)
        return variant.get("metadata") if variant else None

    def query_variants(self, criteria: dict[str, Any]) -> list[dict[str, Any]]:
        """Return all variants matching the given criteria (AND match)."""
        results = []
        for v in self.variants.values():
            if all(v.get(k) == val for k, val in criteria.items()):
                results.append(v)
        return results

    def get_lineage(self, variant_id: str) -> list[str]:
        """Return parent IDs for a given variant."""
        return self.lineage.get(variant_id, [])

    def get_evolution_history(self) -> list[str]:
        """Return the chronological list of all variant IDs added."""
        return list(self.history)

    def get_experiment_variants(self, experiment_id: str) -> list[str]:
        """Get all variants associated with an experiment.

        Args:
            experiment_id: The experiment ID

        Returns:
            List of variant IDs for the experiment
        """
        return self.experiment_variants.get(experiment_id, [])

    def get_variant_experiment(self, variant_id: str) -> Optional[str]:
        """Get the experiment ID associated with a variant.

        Args:
            variant_id: The variant ID

        Returns:
            Experiment ID if found, None otherwise
        """
        return self.variant_experiments.get(variant_id)

    def get_best_variants(
        self, experiment_id: Optional[str] = None, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get the best variants by evaluation score.

        Args:
            experiment_id: Optional experiment ID to filter by
            limit: Maximum number of variants to return

        Returns:
            List of best variants sorted by eval_score (descending)
        """
        variants_to_consider = []

        if experiment_id:
            variant_ids = self.get_experiment_variants(experiment_id)
            variants_to_consider = [
                self.variants[vid] for vid in variant_ids if vid in self.variants
            ]
        else:
            variants_to_consider = list(self.variants.values())

        # Sort by evaluation score (descending)
        sorted_variants = sorted(
            variants_to_consider, key=lambda v: v.get("eval_score", float('-inf')), reverse=True
        )

        return sorted_variants[:limit]

    def get_variant_statistics(self, experiment_id: Optional[str] = None) -> dict[str, Any]:
        """Get statistics about variants.

        Args:
            experiment_id: Optional experiment ID to filter by

        Returns:
            Dictionary with variant statistics
        """
        if experiment_id:
            variant_ids = self.get_experiment_variants(experiment_id)
            variants = [self.variants[vid] for vid in variant_ids if vid in self.variants]
        else:
            variants = list(self.variants.values())

        if not variants:
            return {
                "total_variants": 0,
                "best_score": None,
                "worst_score": None,
                "average_score": None,
                "score_distribution": {},
            }

        scores = [v.get("eval_score", 0) for v in variants]

        return {
            "total_variants": len(variants),
            "best_score": max(scores),
            "worst_score": min(scores),
            "average_score": sum(scores) / len(scores),
            "score_distribution": self._calculate_score_distribution(scores),
        }

    def _calculate_score_distribution(self, scores: list[float]) -> dict[str, int]:
        """Calculate score distribution in bins.

        Args:
            scores: List of evaluation scores

        Returns:
            Dictionary with score ranges and counts
        """
        if not scores:
            return {}

        min_score = min(scores)
        max_score = max(scores)

        if min_score == max_score:
            return {f"{min_score:.2f}": len(scores)}

        # Create 5 bins
        bin_size = (max_score - min_score) / 5
        distribution = {}

        for i in range(5):
            bin_start = min_score + i * bin_size
            bin_end = min_score + (i + 1) * bin_size

            if i == 4:  # Last bin includes max value
                count = sum(1 for s in scores if bin_start <= s <= bin_end)
            else:
                count = sum(1 for s in scores if bin_start <= s < bin_end)

            bin_label = f"{bin_start:.2f}-{bin_end:.2f}"
            distribution[bin_label] = count

        return distribution

    def export_variants(
        self, experiment_id: Optional[str] = None, file_path: Optional[Path] = None
    ) -> Union[str, None]:
        """Export variants to JSON format.

        Args:
            experiment_id: Optional experiment ID to filter by
            file_path: Optional file path to save to

        Returns:
            JSON string if no file_path provided, None otherwise
        """
        if experiment_id:
            variant_ids = self.get_experiment_variants(experiment_id)
            variants_to_export = {
                vid: self.variants[vid] for vid in variant_ids if vid in self.variants
            }
        else:
            variants_to_export = self.variants.copy()

        export_data = {
            "variants": variants_to_export,
            "lineage": {
                vid: self.lineage[vid] for vid in variants_to_export.keys() if vid in self.lineage
            },
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "experiment_id": experiment_id,
        }

        json_data = json.dumps(export_data, indent=2, default=str)

        if file_path:
            with open(file_path, 'w') as f:
                f.write(json_data)
            logger.info(f"Exported variants to {file_path}")
            return None
        else:
            return json_data

    def import_variants(self, json_data: Union[str, Path]) -> int:
        """Import variants from JSON format.

        Args:
            json_data: JSON string or path to JSON file

        Returns:
            Number of variants imported
        """
        if isinstance(json_data, (str, Path)) and Path(json_data).exists():
            with open(json_data, 'r') as f:
                data = json.load(f)
        else:
            data = json.loads(str(json_data))

        imported_count = 0

        for variant_id, variant_data in data.get("variants", {}).items():
            if variant_id not in self.variants:
                self.variants[variant_id] = variant_data
                self.history.append(variant_id)

                # Import experiment association
                experiment_id = variant_data.get("experiment_id")
                if experiment_id:
                    if experiment_id not in self.experiment_variants:
                        self.experiment_variants[experiment_id] = []
                    self.experiment_variants[experiment_id].append(variant_id)
                    self.variant_experiments[variant_id] = experiment_id

                imported_count += 1

        # Import lineage
        for variant_id, parents in data.get("lineage", {}).items():
            if variant_id in self.variants:
                self.lineage[variant_id] = parents

        logger.info(f"Imported {imported_count} variants")
        return imported_count

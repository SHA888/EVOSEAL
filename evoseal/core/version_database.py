"""
VersionDatabase for storing and retrieving code variants, their sources, test results,
evaluation scores, and lineage. Efficient in-memory implementation with extensibility
for persistence.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, TypedDict

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

    def add_variant(
        self,
        variant_id: str,
        source: str,
        test_results: Any,
        eval_score: float,
        parent_ids: list[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        """Store a new code variant and its associated data."""
        self.variants[variant_id] = {
            "variant_id": variant_id,
            "source": source,
            "test_results": test_results,
            "eval_score": eval_score,
            "parent_ids": parent_ids or [],
            "metadata": metadata or {},
        }
        self.lineage[variant_id] = parent_ids or []
        self.history.append(variant_id)

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

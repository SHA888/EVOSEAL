"""
VersionDatabase for storing and retrieving code variants, their sources, test results,
evaluation scores, and lineage. Efficient in-memory implementation with extensibility
for persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict, Union

# Type definitions
VariantID = str
VariantInfo = Dict[str, Any]
LineageInfo = Dict[VariantID, List[VariantID]]
VariantHistory = List[VariantID]

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
        parent_ids: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
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

    def get_variant(self, variant_id: str) -> Optional[dict[str, Any]]:
        """Retrieve a variant and its data by ID."""
        return self.variants.get(variant_id)

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

"""Progressive rollout gating for self-modification candidates.

Instead of immediately adopting every change that passes regression tests,
candidates progress through stability stages (candidate → beta → stable)
before permanent adoption.  See ``docs/architecture/progressive_rollout_gating.md``
for the full design.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

#: Default location for the rollout registry file.
DEFAULT_REGISTRY_DIR = Path("data/rollout")


class RolloutStage(str, Enum):
    """Lifecycle stages for a rollout candidate."""

    CANDIDATE = "candidate"
    BETA = "beta"
    STABLE = "stable"
    REJECTED = "rejected"


@dataclass
class RolloutCandidate:
    """Tracks a single self-modification candidate through the rollout pipeline."""

    candidate_id: str
    stage: RolloutStage = RolloutStage.CANDIDATE
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_to_beta_at: str | None = None
    promoted_to_stable_at: str | None = None
    clean_cycles: int = 0
    baseline_metrics: dict[str, Any] = field(default_factory=dict)
    checkpoint_path: str | None = None
    rejection_reason: str | None = None
    rejected_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RolloutCandidate:
        data = data.copy()
        data["stage"] = RolloutStage(data["stage"])
        return cls(**data)


@dataclass
class RolloutGatingConfig:
    """Configuration for rollout gating, loaded from ``configs/safety.yaml``."""

    enabled: bool = True
    beta_cycles_required: int = 3
    auto_rollback_on_regression: bool = False
    prefer_stable_for_generation: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RolloutGatingConfig:
        return cls(
            enabled=data.get("enabled", True),
            beta_cycles_required=data.get("beta_cycles_required", 3),
            auto_rollback_on_regression=data.get("auto_rollback_on_regression", False),
            prefer_stable_for_generation=data.get("prefer_stable_for_generation", True),
        )


class RolloutGatingManager:
    """Manages the rollout gating lifecycle for self-modification candidates.

    Stores candidate state in a JSON registry file (``rollout_registry.json``)
    alongside the configured data directory.  All public mutation methods
    acquire an ``asyncio.Lock`` and delegate to a private ``_impl`` method
    to avoid reentrant deadlock when called from an async context.
    """

    def __init__(
        self,
        registry_dir: Path | None = None,
        config: RolloutGatingConfig | None = None,
    ) -> None:
        self.registry_dir = registry_dir or DEFAULT_REGISTRY_DIR
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self.registry_file = self.registry_dir / "rollout_registry.json"
        self.config = config or RolloutGatingConfig()
        self._lock = asyncio.Lock()
        self._candidates: dict[str, RolloutCandidate] = {}
        self._load_registry()

    # ── persistence ──────────────────────────────────────────────

    def _load_registry(self) -> None:
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)
                for cid, cdata in data.get("candidates", {}).items():
                    try:
                        self._candidates[cid] = RolloutCandidate.from_dict(cdata)
                    except Exception:
                        logger.exception("Skipping corrupted rollout candidate %s", cid)
                logger.info(
                    "Loaded %d rollout candidates from %s",
                    len(self._candidates),
                    self.registry_file,
                )
            except Exception:
                logger.exception("Error loading rollout registry; starting empty")
                self._candidates = {}
        else:
            self._candidates = {}

    def _save_registry(self) -> None:
        """Atomically persist the registry to disk."""
        try:
            payload = {
                "candidates": {cid: c.to_dict() for cid, c in self._candidates.items()},
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(
                dir=self.registry_file.parent,
                suffix=".tmp",
                prefix=".rollout_registry_",
            )
            try:
                with os.fdopen(fd, "w") as f:
                    json.dump(payload, f, indent=2)
                os.replace(tmp, self.registry_file)
            except BaseException:
                os.unlink(tmp)
                raise
        except Exception:
            logger.exception("Failed to save rollout registry")

    # ── public API ───────────────────────────────────────────────

    async def register_candidate(
        self,
        candidate_id: str,
        baseline_metrics: dict[str, Any],
        checkpoint_path: str | None = None,
    ) -> RolloutCandidate:
        """Register a new candidate and immediately promote it to beta.

        Called after ``_validate_improvement`` accepts a change.  The
        candidate passes the validation gate, so it skips the candidate
        dwell period and goes straight to beta (per design doc §4.1).
        """
        async with self._lock:
            return self._register_candidate_impl(candidate_id, baseline_metrics, checkpoint_path)

    def _register_candidate_impl(
        self,
        candidate_id: str,
        baseline_metrics: dict[str, Any],
        checkpoint_path: str | None,
    ) -> RolloutCandidate:
        existing = self._candidates.get(candidate_id)
        if existing is not None and existing.stage != RolloutStage.CANDIDATE:
            logger.warning(
                "Candidate %s already in stage %s; refusing to re-register",
                candidate_id,
                existing.stage.value,
            )
            return existing
        now = datetime.now(timezone.utc).isoformat()
        candidate = RolloutCandidate(
            candidate_id=candidate_id,
            stage=RolloutStage.BETA,
            created_at=now,
            promoted_to_beta_at=now,
            clean_cycles=0,
            baseline_metrics=baseline_metrics,
            checkpoint_path=checkpoint_path,
        )
        self._candidates[candidate_id] = candidate
        self._save_registry()
        logger.info(
            "Registered rollout candidate %s → beta (checkpoint=%s)",
            candidate_id,
            checkpoint_path,
        )
        return candidate

    async def record_clean_cycle(self, candidate_id: str) -> RolloutCandidate | None:
        """Record that a beta candidate survived one more cycle without regression.

        If ``clean_cycles`` reaches the configured threshold the candidate
        is promoted to stable.
        """
        async with self._lock:
            return self._record_clean_cycle_impl(candidate_id)

    def _record_clean_cycle_impl(self, candidate_id: str) -> RolloutCandidate | None:
        cand = self._candidates.get(candidate_id)
        if cand is None or cand.stage != RolloutStage.BETA:
            return None
        cand.clean_cycles += 1
        if cand.clean_cycles >= self.config.beta_cycles_required:
            cand.stage = RolloutStage.STABLE
            cand.promoted_to_stable_at = datetime.now(timezone.utc).isoformat()
            logger.info(
                "Rollout candidate %s promoted to stable after %d clean cycles",
                candidate_id,
                cand.clean_cycles,
            )
        else:
            logger.info(
                "Rollout candidate %s: clean cycle %d/%d",
                candidate_id,
                cand.clean_cycles,
                self.config.beta_cycles_required,
            )
        self._save_registry()
        return cand

    async def reject_candidate(self, candidate_id: str, reason: str) -> RolloutCandidate | None:
        """Mark a candidate as rejected due to regression."""
        async with self._lock:
            return self._reject_candidate_impl(candidate_id, reason)

    def _reject_candidate_impl(self, candidate_id: str, reason: str) -> RolloutCandidate | None:
        cand = self._candidates.get(candidate_id)
        if cand is None:
            return None
        cand.stage = RolloutStage.REJECTED
        cand.rejection_reason = reason
        cand.rejected_at = datetime.now(timezone.utc).isoformat()
        self._save_registry()
        logger.info("Rollout candidate %s rejected: %s", candidate_id, reason)
        return cand

    async def get_candidate(self, candidate_id: str) -> RolloutCandidate | None:
        """Retrieve a candidate by id."""
        return self._candidates.get(candidate_id)

    async def get_active_beta_candidates(self) -> list[RolloutCandidate]:
        """Return all candidates currently in the beta stage."""
        return [c for c in self._candidates.values() if c.stage == RolloutStage.BETA]

    async def get_all_candidates(self) -> list[RolloutCandidate]:
        """Return all tracked candidates regardless of stage."""
        return list(self._candidates.values())

    async def get_stats(self) -> dict[str, Any]:
        """Return summary statistics for the rollout registry."""
        stage_counts: dict[str, int] = {}
        for c in self._candidates.values():
            stage_counts[c.stage.value] = stage_counts.get(c.stage.value, 0) + 1
        return {
            "total_candidates": len(self._candidates),
            "stage_counts": stage_counts,
            "config": {
                "enabled": self.config.enabled,
                "beta_cycles_required": self.config.beta_cycles_required,
                "auto_rollback_on_regression": self.config.auto_rollback_on_regression,
            },
        }

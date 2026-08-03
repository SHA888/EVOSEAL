"""Tests for progressive rollout gating (design doc §3-§4).

Covers:
- RolloutCandidate dataclass serialization round-trip
- RolloutGatingConfig defaults and from_dict
- RolloutGatingManager: register → record_clean_cycle → promote to stable
- RolloutGatingManager: regression rejection at beta stage
- RolloutGatingManager: idempotent registry persistence
- RolloutGatingManager: get_active_beta_candidates filtering
- RolloutGatingManager: stats aggregation
- RolloutGatingManager: concurrent mutation safety (asyncio.Lock)
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from pathlib import Path

import pytest

from evoseal.core.rollout_gating import (
    RolloutCandidate,
    RolloutGatingConfig,
    RolloutGatingManager,
    RolloutStage,
)

# ---------------------------------------------------------------------------
# RolloutCandidate
# ---------------------------------------------------------------------------


class TestRolloutCandidate:
    def test_defaults(self):
        cand = RolloutCandidate(candidate_id="test-1")
        assert cand.stage == RolloutStage.CANDIDATE
        assert cand.clean_cycles == 0
        assert cand.baseline_metrics == {}
        assert cand.checkpoint_path is None
        assert cand.rejection_reason is None
        assert cand.rejected_at is None

    def test_to_dict_round_trip(self):
        cand = RolloutCandidate(
            candidate_id="rt-1",
            stage=RolloutStage.BETA,
            clean_cycles=2,
            baseline_metrics={"fitness": 0.85},
            checkpoint_path="/tmp/cp",
        )
        d = cand.to_dict()
        restored = RolloutCandidate.from_dict(d)
        assert restored.candidate_id == cand.candidate_id
        assert restored.stage == RolloutStage.BETA
        assert restored.clean_cycles == 2
        assert restored.baseline_metrics == {"fitness": 0.85}
        assert restored.checkpoint_path == "/tmp/cp"

    def test_stage_enum_values(self):
        assert RolloutStage.CANDIDATE.value == "candidate"
        assert RolloutStage.BETA.value == "beta"
        assert RolloutStage.STABLE.value == "stable"
        assert RolloutStage.REJECTED.value == "rejected"


# ---------------------------------------------------------------------------
# RolloutGatingConfig
# ---------------------------------------------------------------------------


class TestRolloutGatingConfig:
    def test_defaults(self):
        cfg = RolloutGatingConfig()
        assert cfg.enabled is True
        assert cfg.beta_cycles_required == 3
        assert cfg.auto_rollback_on_regression is True
        assert cfg.prefer_stable_for_generation is True

    def test_from_dict(self):
        cfg = RolloutGatingConfig.from_dict(
            {
                "enabled": False,
                "beta_cycles_required": 5,
                "auto_rollback_on_regression": False,
                "prefer_stable_for_generation": False,
            }
        )
        assert cfg.enabled is False
        assert cfg.beta_cycles_required == 5
        assert cfg.auto_rollback_on_regression is False
        assert cfg.prefer_stable_for_generation is False

    def test_from_dict_partial(self):
        cfg = RolloutGatingConfig.from_dict({"beta_cycles_required": 1})
        assert cfg.beta_cycles_required == 1
        assert cfg.enabled is True  # default

    def test_from_dict_empty(self):
        cfg = RolloutGatingConfig.from_dict({})
        assert cfg.beta_cycles_required == 3


# ---------------------------------------------------------------------------
# RolloutGatingManager
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_registry(tmp_path: Path) -> Path:
    return tmp_path / "rollout"


@pytest.fixture
def manager(tmp_registry: Path) -> RolloutGatingManager:
    return RolloutGatingManager(registry_dir=tmp_registry)


class TestRolloutGatingManager:
    @pytest.mark.asyncio
    async def test_register_candidate_goes_to_beta(self, manager: RolloutGatingManager):
        cand = await manager.register_candidate("c1", {"fitness": 0.9})
        assert cand.stage == RolloutStage.BETA
        assert cand.candidate_id == "c1"
        assert cand.baseline_metrics == {"fitness": 0.9}
        assert cand.promoted_to_beta_at is not None
        assert cand.clean_cycles == 0

    @pytest.mark.asyncio
    async def test_register_persists_to_disk(
        self, manager: RolloutGatingManager, tmp_registry: Path
    ):
        await manager.register_candidate("c2", {"score": 80.0})
        reg_file = tmp_registry / "rollout_registry.json"
        assert reg_file.exists()
        data = json.loads(reg_file.read_text())
        assert "c2" in data["candidates"]
        assert data["candidates"]["c2"]["stage"] == "beta"

    @pytest.mark.asyncio
    async def test_record_clean_cycle_increments(self, manager: RolloutGatingManager):
        await manager.register_candidate("c3", {"fitness": 0.8})
        updated = await manager.record_clean_cycle("c3")
        assert updated is not None
        assert updated.clean_cycles == 1
        assert updated.stage == RolloutStage.BETA  # not yet stable (need 3)

    @pytest.mark.asyncio
    async def test_promotion_to_stable_after_n_cycles(self, manager: RolloutGatingManager):
        """After beta_cycles_required clean cycles, candidate promotes to stable."""
        await manager.register_candidate("c4", {"fitness": 0.7})
        for i in range(1, 4):
            updated = await manager.record_clean_cycle("c4")
            assert updated is not None
            if i < 3:
                assert updated.stage == RolloutStage.BETA
            else:
                assert updated.stage == RolloutStage.STABLE
                assert updated.promoted_to_stable_at is not None

    @pytest.mark.asyncio
    async def test_custom_beta_cycles_required(self, tmp_registry: Path):
        cfg = RolloutGatingConfig(beta_cycles_required=2)
        mgr = RolloutGatingManager(registry_dir=tmp_registry, config=cfg)
        await mgr.register_candidate("c5", {"fitness": 0.6})
        await mgr.record_clean_cycle("c5")
        updated = await mgr.record_clean_cycle("c5")
        assert updated.stage == RolloutStage.STABLE

    @pytest.mark.asyncio
    async def test_reject_candidate(self, manager: RolloutGatingManager):
        await manager.register_candidate("c6", {"fitness": 0.5})
        rejected = await manager.reject_candidate("c6", "regression detected")
        assert rejected is not None
        assert rejected.stage == RolloutStage.REJECTED
        assert rejected.rejection_reason == "regression detected"
        # rejected_at records *when* the regression was detected — without it a
        # rejected candidate cannot be correlated with the cycle that caused it.
        assert rejected.rejected_at is not None
        datetime.fromisoformat(rejected.rejected_at)  # parses as a valid ISO timestamp

    @pytest.mark.asyncio
    async def test_rejected_at_persists_across_reload(self, tmp_registry: Path):
        """A reloaded registry keeps rejected_at, and entries predating it still load."""
        mgr = RolloutGatingManager(registry_dir=tmp_registry)
        await mgr.register_candidate("c6p", {"fitness": 0.5})
        rejected = await mgr.reject_candidate("c6p", "regression")

        restored = await RolloutGatingManager(registry_dir=tmp_registry).get_candidate("c6p")
        assert restored is not None
        assert restored.rejected_at == rejected.rejected_at

        # A registry written before rejected_at existed must still load.
        reg_file = tmp_registry / "rollout_registry.json"
        data = json.loads(reg_file.read_text())
        del data["candidates"]["c6p"]["rejected_at"]
        reg_file.write_text(json.dumps(data))

        legacy = await RolloutGatingManager(registry_dir=tmp_registry).get_candidate("c6p")
        assert legacy is not None
        assert legacy.rejected_at is None

    @pytest.mark.asyncio
    async def test_rejected_candidate_not_overwritten(self, manager: RolloutGatingManager):
        """Registering a candidate that was already rejected preserves the REJECTED state."""
        await manager.register_candidate("c6dup", {"fitness": 0.5})
        rejected = await manager.reject_candidate("c6dup", "regression")
        assert rejected.stage == RolloutStage.REJECTED
        # Re-register same ID — should NOT overwrite the terminal REJECTED state
        re_registered = await manager.register_candidate("c6dup", {"fitness": 0.9})
        assert re_registered.stage == RolloutStage.REJECTED
        assert re_registered.rejection_reason == "regression"

    @pytest.mark.asyncio
    async def test_beta_candidate_not_overwritten(self, manager: RolloutGatingManager):
        """Registering an ID already in BETA preserves the existing record."""
        await manager.register_candidate("beta-no-overwrite", {"fitness": 0.8})
        await manager.record_clean_cycle("beta-no-overwrite")
        cand = await manager.get_candidate("beta-no-overwrite")
        assert cand is not None
        assert cand.clean_cycles == 1
        # Re-register — must NOT reset clean_cycles to 0
        re_registered = await manager.register_candidate("beta-no-overwrite", {"fitness": 0.99})
        assert re_registered.clean_cycles == 1
        assert re_registered.stage == RolloutStage.BETA

    @pytest.mark.asyncio
    async def test_stable_candidate_not_overwritten(self, manager: RolloutGatingManager):
        """Registering an ID already in STABLE preserves the existing record."""
        await manager.register_candidate("stable-no-overwrite", {"fitness": 0.7})
        for _ in range(3):
            await manager.record_clean_cycle("stable-no-overwrite")
        cand = await manager.get_candidate("stable-no-overwrite")
        assert cand is not None
        assert cand.stage == RolloutStage.STABLE
        # Re-register — must NOT reset to BETA
        re_registered = await manager.register_candidate("stable-no-overwrite", {"fitness": 0.99})
        assert re_registered.stage == RolloutStage.STABLE
        assert re_registered.clean_cycles == 3

    @pytest.mark.asyncio
    async def test_reject_nonexistent_returns_none(self, manager: RolloutGatingManager):
        result = await manager.reject_candidate("no-such-id", "reason")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_clean_cycle_on_rejected_is_noop(self, manager: RolloutGatingManager):
        await manager.register_candidate("c7", {})
        await manager.reject_candidate("c7", "bad")
        result = await manager.record_clean_cycle("c7")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_clean_cycle_on_nonexistent_is_noop(self, manager: RolloutGatingManager):
        result = await manager.record_clean_cycle("ghost")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_active_beta_candidates(self, manager: RolloutGatingManager):
        await manager.register_candidate("b1", {})
        await manager.register_candidate("b2", {})
        await manager.register_candidate("b3", {})
        await manager.reject_candidate("b2", "fail")

        betas = await manager.get_active_beta_candidates()
        beta_ids = {c.candidate_id for c in betas}
        assert beta_ids == {"b1", "b3"}

    @pytest.mark.asyncio
    async def test_get_all_candidates(self, manager: RolloutGatingManager):
        await manager.register_candidate("a1", {})
        await manager.register_candidate("a2", {})
        all_cands = await manager.get_all_candidates()
        assert len(all_cands) == 2

    @pytest.mark.asyncio
    async def test_get_candidate(self, manager: RolloutGatingManager):
        await manager.register_candidate("g1", {"x": 1})
        cand = await manager.get_candidate("g1")
        assert cand is not None
        assert cand.candidate_id == "g1"
        assert await manager.get_candidate("nope") is None

    @pytest.mark.asyncio
    async def test_stats(self, manager: RolloutGatingManager):
        await manager.register_candidate("s1", {})
        await manager.register_candidate("s2", {})
        await manager.reject_candidate("s2", "r")
        await manager.register_candidate("s3", {})
        for _ in range(3):
            await manager.record_clean_cycle("s3")

        stats = await manager.get_stats()
        assert stats["total_candidates"] == 3
        assert stats["stage_counts"]["beta"] == 1
        assert stats["stage_counts"]["stable"] == 1
        assert stats["stage_counts"]["rejected"] == 1

    @pytest.mark.asyncio
    async def test_registry_survives_reload(self, tmp_registry: Path):
        """Registry state persists across manager instances."""
        mgr1 = RolloutGatingManager(registry_dir=tmp_registry)
        await mgr1.register_candidate("persist-1", {"fitness": 0.95})
        await mgr1.record_clean_cycle("persist-1")

        # New instance loads from disk
        mgr2 = RolloutGatingManager(registry_dir=tmp_registry)
        cand = await mgr2.get_candidate("persist-1")
        assert cand is not None
        assert cand.clean_cycles == 1
        assert cand.stage == RolloutStage.BETA

    @pytest.mark.asyncio
    async def test_corrupted_registry_file(self, tmp_registry: Path):
        """Manager starts with empty state when registry is corrupted."""
        reg_file = tmp_registry / "rollout_registry.json"
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        reg_file.write_text("NOT VALID JSON {{{")

        mgr = RolloutGatingManager(registry_dir=tmp_registry)
        all_cands = await mgr.get_all_candidates()
        assert all_cands == []

    @pytest.mark.asyncio
    async def test_partial_corruption_skips_bad_entry(self, tmp_registry: Path):
        """One corrupt candidate entry doesn't discard the rest."""
        import json as json_mod

        reg_file = tmp_registry / "rollout_registry.json"
        reg_file.parent.mkdir(parents=True, exist_ok=True)
        # Write one valid and one invalid entry
        data = {
            "candidates": {
                "good": {
                    "candidate_id": "good",
                    "stage": "beta",
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "promoted_to_beta_at": "2026-01-01T00:00:00+00:00",
                    "promoted_to_stable_at": None,
                    "clean_cycles": 0,
                    "baseline_metrics": {},
                    "checkpoint_path": None,
                    "rejection_reason": None,
                },
                "bad": {
                    "candidate_id": "bad",
                    "stage": "INVALID_STAGE",  # will fail deserialization
                },
            },
            "updated_at": "2026-01-01T00:00:00+00:00",
        }
        reg_file.write_text(json_mod.dumps(data))

        mgr = RolloutGatingManager(registry_dir=tmp_registry)
        # The valid entry should load; the bad one is skipped
        all_cands = await mgr.get_all_candidates()
        assert len(all_cands) == 1
        assert all_cands[0].candidate_id == "good"

    @pytest.mark.asyncio
    async def test_checkpoint_path_stored(self, manager: RolloutGatingManager):
        cand = await manager.register_candidate(
            "cp1", {"fitness": 0.5}, checkpoint_path="/checkpoints/cp1"
        )
        assert cand.checkpoint_path == "/checkpoints/cp1"

    @pytest.mark.asyncio
    async def test_concurrent_registrations(self, manager: RolloutGatingManager):
        """Multiple concurrent registrations don't corrupt state."""
        tasks = [manager.register_candidate(f"concurrent-{i}", {"i": i}) for i in range(10)]
        await asyncio.gather(*tasks)
        all_cands = await manager.get_all_candidates()
        assert len(all_cands) == 10

    @pytest.mark.asyncio
    async def test_stable_candidate_ignores_further_cycles(self, manager: RolloutGatingManager):
        """Once stable, record_clean_cycle is a no-op."""
        await manager.register_candidate("stab1", {})
        for _ in range(3):
            await manager.record_clean_cycle("stab1")
        cand = await manager.get_candidate("stab1")
        assert cand.stage == RolloutStage.STABLE
        # Further calls return None (not beta anymore)
        result = await manager.record_clean_cycle("stab1")
        assert result is None
